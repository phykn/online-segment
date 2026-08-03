import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
from fastapi import HTTPException

from app.segment import feature
from app.segment.model import Segmenter


class FakeModel:
    def __init__(self) -> None:
        self.weights = None

    def fit(self, x, y, sample_weight=None) -> None:
        self.weights = sample_weight


class ModelTests(unittest.TestCase):
    def test_make_uses_configured_rf_settings(self) -> None:
        classifier = Segmenter(Path("unused.joblib"))._make()

        self.assertEqual(classifier.max_features, 3)
        self.assertEqual(classifier.min_samples_leaf, 2)

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
        self.assertIsInstance(loaded.model_id_, str)

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

    def test_old_model_type_requires_retraining(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.joblib"
            joblib.dump(
                {
                    "model": None,
                    "kind": "lightgbm",
                    "features": feature.config(),
                },
                path,
            )

            with self.assertRaises(HTTPException) as caught:
                Segmenter(path).load()

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(
            caught.exception.detail,
            "model must be retrained for the current model type.",
        )


if __name__ == "__main__":
    unittest.main()
