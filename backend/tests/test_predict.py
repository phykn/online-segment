import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from fastapi import HTTPException

from app import actions


class PredictTests(unittest.TestCase):
    def test_rf_probabilities_are_refined_before_labeling(self) -> None:
        image = np.zeros((2, 3, 3), dtype=np.uint8)
        probs = np.zeros((2, 3, 2), dtype=np.float32)
        probs[..., 0] = 1.0
        refined = probs[..., ::-1].copy()
        classifier = SimpleNamespace(
            classes_=np.array([0, 1], dtype=np.int8),
            model_id_="rf-id",
        )

        segmenter = Mock()
        segmenter.prob.return_value = probs
        refiner = Mock()
        refiner.adjust.return_value = refined
        result = actions.predict(image, segmenter, refiner, classifier)

        segmenter.prob.assert_called_once_with(image, classifier)
        refiner.adjust.assert_called_once_with(
            image,
            probs,
            classifier.classes_,
            "rf-id",
        )
        self.assertTrue((result == 1).all())

    def test_infer_marks_low_confidence_pixels(self) -> None:
        image = np.zeros((1, 2, 3), dtype=np.uint8)
        probs = np.array([[[0.8, 0.2], [0.6, 0.4]]], dtype=np.float32)
        classifier = SimpleNamespace(
            classes_=np.array([0, 1], dtype=np.int8),
            model_id_="rf-id",
        )

        segmenter = Mock()
        segmenter.prob.return_value = probs
        refiner = Mock()
        refiner.adjust.return_value = probs
        mask, uncertain = actions.infer(
            image,
            segmenter,
            refiner,
            classifier,
        )

        self.assertEqual(mask.tolist(), [[0, 0]])
        self.assertEqual(uncertain.tolist(), [[0, 1]])

    def test_infer_forces_selected_labels_after_model_prediction(self) -> None:
        image = np.zeros((1, 3, 3), dtype=np.uint8)
        probs = np.array(
            [[[0.9, 0.1], [0.9, 0.1], [0.6, 0.4]]],
            dtype=np.float32,
        )
        selected = np.array([[-1, 1, -1]], dtype=np.int8)
        classifier = SimpleNamespace(
            classes_=np.array([0, 1], dtype=np.int8),
            model_id_="rf-id",
        )

        segmenter = Mock()
        segmenter.prob.return_value = probs
        refiner = Mock()
        refiner.adjust.return_value = probs
        mask, uncertain = actions.infer(
            image,
            segmenter,
            refiner,
            classifier,
            selected,
        )

        self.assertEqual(mask.tolist(), [[0, 1, 0]])
        self.assertEqual(uncertain.tolist(), [[0, 0, 1]])

    def test_infer_rejects_selected_labels_with_a_different_size(self) -> None:
        image = np.zeros((1, 2, 3), dtype=np.uint8)
        probs = np.ones((1, 2, 1), dtype=np.float32)
        classifier = SimpleNamespace(
            classes_=np.array([0], dtype=np.int8),
            model_id_="rf-id",
        )
        segmenter = Mock()
        segmenter.prob.return_value = probs
        refiner = Mock()
        refiner.adjust.return_value = probs

        with self.assertRaisesRegex(HTTPException, "image and mask sizes differ"):
            actions.infer(
                image,
                segmenter,
                refiner,
                classifier,
                np.full((2, 2), -1, dtype=np.int8),
            )


if __name__ == "__main__":
    unittest.main()
