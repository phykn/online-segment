import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

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

        with (
            patch.object(actions.segmenter, "prob", return_value=probs) as prob,
            patch.object(
                actions.refiner,
                "adjust",
                return_value=refined,
            ) as adjust,
        ):
            result = actions.predict(image, classifier)

        prob.assert_called_once_with(image, classifier)
        adjust.assert_called_once_with(
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

        with (
            patch.object(actions.segmenter, "prob", return_value=probs),
            patch.object(actions.refiner, "adjust", return_value=probs),
        ):
            mask, uncertain = actions.infer(image, classifier)

        self.assertEqual(mask.tolist(), [[0, 0]])
        self.assertEqual(uncertain.tolist(), [[0, 1]])


if __name__ == "__main__":
    unittest.main()
