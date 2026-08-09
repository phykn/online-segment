import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import joblib
import numpy as np
from fastapi import HTTPException
from sklearn.ensemble import RandomForestClassifier

from app.segment import feature
from app.segment.model import Segmenter


class FakeModel:
    def __init__(self) -> None:
        self.weights = None

    def fit(self, x, y, sample_weight=None) -> None:
        self.weights = sample_weight


class ModelTests(unittest.TestCase):
    def test_make_uses_configured_rf_settings(self) -> None:
        forest = Segmenter(Path("unused.joblib"))._make()

        self.assertIsInstance(forest, RandomForestClassifier)
        self.assertEqual(forest.max_features, 3)
        self.assertEqual(forest.min_samples_leaf, 2)

    def test_prob_returns_raw_random_forest_probabilities(self) -> None:
        image = np.zeros((2, 3, 3), dtype=np.uint8)
        stack = np.zeros((2, 3, feature.COUNT), dtype=np.float32)
        expected = np.arange(12, dtype=np.float64).reshape(2, 3, 2)
        classifier = Mock()
        classifier.predict_proba.return_value = expected.reshape(6, 2)
        segmenter = Segmenter(Path("unused.joblib"))

        with patch("app.segment.model.feature.cached", return_value=stack):
            actual = segmenter.prob(image, classifier)

        np.testing.assert_array_equal(actual, expected)

    def test_features_can_bypass_cache_for_batch_prediction(self) -> None:
        image = np.zeros((2, 3, 3), dtype=np.uint8)
        stack = np.zeros((2, 3, feature.COUNT), dtype=np.float32)
        segmenter = Segmenter(Path("unused.joblib"))

        with (
            patch("app.segment.model.feature.cached") as cached,
            patch("app.segment.model.feature.make", return_value=stack) as make,
        ):
            actual = segmenter.features(image, cached=False)

        self.assertIs(actual, stack)
        cached.assert_not_called()
        make.assert_called_once_with(image)

    def test_batch_predictor_cache_tracks_classifier_identity(self) -> None:
        segmenter = Segmenter(Path("unused.joblib"))
        first_classifier = Mock()
        second_classifier = Mock()
        available = object()

        with patch(
            "app.segment.model.cuda_forest.make_predictor",
            side_effect=[None, available],
        ) as make:
            self.assertIsNone(segmenter.batch_predictor(first_classifier))
            self.assertIsNone(segmenter.batch_predictor(first_classifier))
            self.assertIs(
                segmenter.batch_predictor(second_classifier),
                available,
            )
            self.assertIs(
                segmenter.batch_predictor(second_classifier),
                available,
            )

        self.assertEqual(make.call_count, 2)
        self.assertIs(
            make.call_args_list[0].args[0],
            first_classifier,
        )
        self.assertIs(
            make.call_args_list[1].args[0],
            second_classifier,
        )

    def test_saving_new_model_releases_batch_predictor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            segmenter = Segmenter(Path(tmp) / "model.joblib")
            classifier = segmenter._make()
            segmenter._cache.update(
                batch_predictor_model=object(),
                batch_predictor=object(),
            )

            segmenter._save(classifier)

        self.assertNotIn("batch_predictor_model", segmenter._cache)
        self.assertNotIn("batch_predictor", segmenter._cache)
        self.assertIs(segmenter._cache["model"], classifier)

    def test_loading_changed_model_releases_batch_predictor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.joblib"
            writer = Segmenter(path)
            classifier = writer._make()
            writer._save(classifier)
            segmenter = Segmenter(path)
            segmenter._cache.update(
                stamp=-1,
                model=object(),
                batch_predictor_model=object(),
                batch_predictor=object(),
            )
            loaded = segmenter.load()

        self.assertIsInstance(loaded, RandomForestClassifier)
        self.assertNotIn("batch_predictor_model", segmenter._cache)
        self.assertNotIn("batch_predictor", segmenter._cache)

    def test_rf_separates_same_color_particles_by_size(self) -> None:
        height, width = 360, 520
        y, x = np.ogrid[:height, :width]
        image = np.zeros((height, width, 3), dtype=np.uint8)
        small_centers = [(70, 70), (70, 230), (70, 390)]
        large_centers = [(230, 70), (230, 230), (230, 390)]

        for center_y, center_x in small_centers:
            disk = (x - center_x) ** 2 + (y - center_y) ** 2 <= 8**2
            image[disk] = 255
        for center_y, center_x in large_centers:
            disk = (x - center_x) ** 2 + (y - center_y) ** 2 <= 32**2
            image[disk] = 255

        stack = feature.make(image)
        samples = []
        labels = []
        for label, centers in ((1, small_centers[:2]), (2, large_centers[:2])):
            for center_y, center_x in centers:
                brush = (x - center_x) ** 2 + (y - center_y) ** 2 <= 3**2
                samples.append(stack[brush])
                labels.append(np.full(brush.sum(), label, dtype=np.int8))

        background = np.zeros((height, width), dtype=bool)
        background[300:315, 230:245] = True
        samples.append(stack[background])
        labels.append(np.zeros(background.sum(), dtype=np.int8))

        test = np.stack(
            (
                stack[small_centers[-1]],
                stack[large_centers[-1]],
                stack[320, 400],
            )
        )

        classifier = Segmenter(Path("unused.joblib"))._make()
        classifier.fit(np.concatenate(samples), np.concatenate(labels))
        self.assertEqual(classifier.predict(test).tolist(), [1, 2, 0])

    def test_fit_and_load_preserve_four_labels(self) -> None:
        rng = np.random.default_rng(4)
        x = rng.random((40, feature.COUNT), dtype=np.float32)
        y = np.repeat(np.arange(4, dtype=np.int8), 10)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.joblib"
            segmenter = Segmenter(path)
            fitted = segmenter.fit(x, y)
            loaded = segmenter.load()

        self.assertEqual(fitted.classes_.tolist(), [0, 1, 2, 3])
        self.assertEqual(loaded.classes_.tolist(), [0, 1, 2, 3])
        self.assertEqual(loaded.n_features_in_, feature.COUNT)

    def test_fit_passes_weights(self) -> None:
        x = np.arange(60, dtype=np.float32).reshape(10, 6)
        y = np.repeat(np.array([0, 1], dtype=np.int8), 5)
        weights = np.linspace(0.25, 1.0, y.size, dtype=np.float32)
        made = FakeModel()
        segmenter = Segmenter(Path("unused.joblib"))

        with (
            patch.object(segmenter, "_make", return_value=made),
            patch.object(segmenter, "_save"),
        ):
            result = segmenter.fit(x, y, weights)

        self.assertIs(result, made)
        self.assertTrue(np.array_equal(made.weights, weights))

    def test_load_reuses_unchanged_model(self) -> None:
        rng = np.random.default_rng(8)
        x = rng.random((20, feature.COUNT), dtype=np.float32)
        y = np.repeat(np.array([0, 1], dtype=np.int8), 10)

        with tempfile.TemporaryDirectory() as tmp:
            segmenter = Segmenter(Path(tmp) / "model.joblib")
            fitted = segmenter.fit(x, y)
            with patch("app.segment.model.joblib.load") as load:
                self.assertIs(segmenter.load(), fitted)
                self.assertIs(segmenter.load(), fitted)

        load.assert_not_called()

    def test_old_feature_config_requires_retraining(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.joblib"
            old = feature.config() | {"factors": [1.0]}
            joblib.dump(
                {"model": None, "features": old},
                path,
            )

            with self.assertRaises(HTTPException) as caught:
                Segmenter(path).load()

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(
            caught.exception.detail,
            "model must be retrained for the current features.",
        )

if __name__ == "__main__":
    unittest.main()
