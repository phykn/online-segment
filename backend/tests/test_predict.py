import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from app import actions


class PredictTests(unittest.TestCase):
    def test_predict_uses_random_forest_probabilities(self) -> None:
        image = np.zeros((2, 3, 3), dtype=np.uint8)
        probs = np.zeros((2, 3, 2), dtype=np.float32)
        probs[..., 0] = 1.0
        classifier = SimpleNamespace(
            classes_=np.array([0, 1], dtype=np.int8),
        )
        segmenter = Mock()
        segmenter.prob.return_value = probs

        result = actions.predict(image, segmenter, classifier)

        segmenter.prob.assert_called_once_with(image, classifier)
        self.assertTrue((result == 0).all())

    def test_predict_features_uses_precomputed_stack(self) -> None:
        stack = np.zeros((2, 3, 4), dtype=np.float32)
        probs = np.zeros((2, 3, 2), dtype=np.float32)
        probs[..., 1] = 1.0
        classifier = SimpleNamespace(
            classes_=np.array([0, 1], dtype=np.int8),
        )
        segmenter = Mock()
        segmenter.prob_features.return_value = probs

        result = actions.predict_features(stack, segmenter, classifier)

        segmenter.prob_features.assert_called_once_with(stack, classifier)
        self.assertTrue((result == 1).all())

    def test_predict_features_uses_gpu_labels_when_available(self) -> None:
        stack = np.zeros((2, 3, 4), dtype=np.float32)
        expected = np.ones((2, 3), dtype=np.int8)
        predictor = Mock()
        predictor.predict.return_value = expected
        segmenter = Mock()

        result = actions.predict_features(
            stack,
            segmenter,
            Mock(),
            predictor,
        )

        self.assertIs(result, expected)
        predictor.predict.assert_called_once_with(stack)
        segmenter.prob_features.assert_not_called()

    def test_predict_features_falls_back_when_gpu_declines(self) -> None:
        stack = np.zeros((2, 3, 4), dtype=np.float32)
        probs = np.zeros((2, 3, 2), dtype=np.float32)
        probs[..., 1] = 1.0
        classifier = SimpleNamespace(
            classes_=np.array([0, 1], dtype=np.int8),
        )
        predictor = Mock()
        predictor.predict.return_value = None
        segmenter = Mock()
        segmenter.prob_features.return_value = probs

        result = actions.predict_features(
            stack,
            segmenter,
            classifier,
            predictor,
        )

        predictor.predict.assert_called_once_with(stack)
        segmenter.prob_features.assert_called_once_with(
            stack,
            classifier,
        )
        self.assertTrue((result == 1).all())

    def test_infer_marks_low_confidence_pixels(self) -> None:
        image = np.zeros((1, 2, 3), dtype=np.uint8)
        probs = np.array([[[0.8, 0.2], [0.6, 0.4]]], dtype=np.float32)
        classifier = SimpleNamespace(
            classes_=np.array([0, 1], dtype=np.int8),
        )
        segmenter = Mock()
        segmenter.prob.return_value = probs

        mask, uncertain = actions.infer(image, segmenter, classifier)

        self.assertEqual(mask.tolist(), [[0, 0]])
        self.assertEqual(uncertain.tolist(), [[0, 1]])

if __name__ == "__main__":
    unittest.main()
