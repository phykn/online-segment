import unittest
from unittest.mock import patch

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier

from app.segment import cuda_forest


class TieForest:
    def __init__(self) -> None:
        x = np.asarray([[-1.0], [1.0]], dtype=np.float32)
        first = DecisionTreeClassifier(max_depth=1, random_state=0)
        second = DecisionTreeClassifier(max_depth=1, random_state=1)
        first.fit(x, np.asarray([0, 1], dtype=np.int8))
        second.fit(x, np.asarray([1, 0], dtype=np.int8))
        self.estimators_ = [first, second]
        self.classes_ = np.asarray([0, 1], dtype=np.int8)
        self.n_features_in_ = 1
        self.predict_calls = 0

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        self.predict_calls += 1
        return sum(
            estimator.predict_proba(x)
            for estimator in self.estimators_
        ) / len(self.estimators_)


class CudaForestTests(unittest.TestCase):
    def setUp(self) -> None:
        cuda_forest._CUDA_DISABLED = False

    def tearDown(self) -> None:
        cuda_forest._CUDA_DISABLED = False

    def test_cutoffs_match_float32_values_compared_to_float64(self) -> None:
        lower = np.asarray([0.1, -0.1, 1.0, -1.0], dtype=np.float32)
        upper = np.nextafter(lower, np.float32(np.inf))
        thresholds = (
            lower.astype(np.float64) * 0.25
            + upper.astype(np.float64) * 0.75
        )
        cutoffs = cuda_forest._float32_cutoffs(thresholds)
        candidates = np.stack(
            (
                np.nextafter(cutoffs, np.float32(-np.inf)),
                cutoffs,
                np.nextafter(cutoffs, np.float32(np.inf)),
            ),
            axis=1,
        )

        expected = candidates.astype(np.float64) <= thresholds[:, None]
        actual = candidates <= cutoffs[:, None]
        naive = candidates <= thresholds.astype(np.float32)[:, None]

        np.testing.assert_array_equal(actual, expected)
        self.assertTrue(np.any(naive != expected))

    def test_missing_torch_disables_only_the_optional_predictor(self) -> None:
        classifier = TieForest()

        with patch.object(cuda_forest, "_load_torch", return_value=None):
            predictor = cuda_forest.make_predictor(classifier)

        self.assertIsNone(predictor)
        self.assertFalse(cuda_forest._CUDA_DISABLED)

    def test_torch_runtime_import_error_is_an_optional_failure(self) -> None:
        with patch.object(
            cuda_forest,
            "import_module",
            side_effect=RuntimeError("CUDA DLL could not be loaded"),
        ):
            torch = cuda_forest._load_torch()

        self.assertIsNone(torch)
        self.assertFalse(cuda_forest._CUDA_DISABLED)

    def test_gpu_matches_sklearn_probabilities_argmax(self) -> None:
        torch = cuda_forest._load_torch()
        if torch is None or not torch.cuda.is_available():
            self.skipTest("CUDA is not available")

        rng = np.random.default_rng(12)
        x = rng.normal(size=(4_000, 8)).astype(np.float32)
        y = rng.integers(0, 4, size=x.shape[0], dtype=np.int8)
        classifier = RandomForestClassifier(
            n_estimators=24,
            max_depth=6,
            min_samples_leaf=2,
            random_state=3,
            n_jobs=-1,
        ).fit(x, y)
        stack = rng.normal(size=(48, 64, 8)).astype(np.float32)
        expected = classifier.classes_[
            np.argmax(
                classifier.predict_proba(stack.reshape(-1, 8)),
                axis=1,
            )
        ].astype(np.int8)

        predictor = cuda_forest.make_predictor(classifier)
        self.assertIsNotNone(predictor)
        actual = predictor.predict(stack)

        np.testing.assert_array_equal(actual, expected.reshape(48, 64))

    def test_staged_exit_stays_close_to_full_forest(self) -> None:
        torch = cuda_forest._load_torch()
        if torch is None or not torch.cuda.is_available():
            self.skipTest("CUDA is not available")

        rng = np.random.default_rng(19)
        x = rng.normal(size=(12_000, 8)).astype(np.float32)
        y = (
            (x[:, 0] > 0).astype(np.int8)
            + 2 * (x[:, 1] > 0).astype(np.int8)
        )
        classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=2,
            random_state=5,
            n_jobs=-1,
        ).fit(x, y)
        stack = rng.normal(size=(64, 64, 8)).astype(np.float32)
        expected = classifier.classes_[
            np.argmax(
                classifier.predict_proba(stack.reshape(-1, 8)),
                axis=1,
            )
        ].reshape(64, 64)

        predictor = cuda_forest.make_predictor(classifier)
        self.assertIsNotNone(predictor)
        with patch.object(
            predictor,
            "_staged_chunk",
            wraps=predictor._staged_chunk,
        ) as staged:
            actual = predictor.predict(stack)

        self.assertGreater(staged.call_count, 0)
        self.assertEqual(predictor.probabilities.dtype, torch.float32)
        self.assertLessEqual(float(np.mean(actual != expected)), 0.001)


    def test_exact_ties_keep_first_class_without_cpu_round_trip(self) -> None:
        torch = cuda_forest._load_torch()
        if torch is None or not torch.cuda.is_available():
            self.skipTest("CUDA is not available")

        classifier = TieForest()
        stack = np.asarray([[[-1.0], [1.0]]], dtype=np.float32)
        expected = np.zeros((1, 2), dtype=np.int8)

        predictor = cuda_forest.make_predictor(classifier)
        self.assertIsNotNone(predictor)
        actual = predictor.predict(stack)

        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(classifier.predict_calls, 0)

    def test_runtime_error_disables_cuda_and_signals_cpu_fallback(self) -> None:
        torch = cuda_forest._load_torch()
        if torch is None or not torch.cuda.is_available():
            self.skipTest("CUDA is not available")

        predictor = cuda_forest.make_predictor(TieForest())
        self.assertIsNotNone(predictor)
        stack = np.zeros((1, 1, 1), dtype=np.float32)

        with patch.object(
            predictor,
            "_predict_locked",
            side_effect=RuntimeError("CUDA failed"),
        ):
            actual = predictor.predict(stack)

        self.assertIsNone(actual)
        self.assertTrue(cuda_forest._CUDA_DISABLED)


if __name__ == "__main__":
    unittest.main()
