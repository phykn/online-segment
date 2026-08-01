import unittest
from unittest.mock import Mock, patch

import numpy as np

from app import actions


class ApplyTests(unittest.TestCase):
    def test_make_data_balances_classes(self) -> None:
        image = np.zeros((4, 4, 3), dtype=np.uint8)
        mask = np.array(
            [
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                [1, -1, 1, -1],
                [1, -1, 1, -1],
            ],
            dtype=np.int8,
        )
        stack = np.arange(
            4 * 4 * 3,
            dtype=np.float32,
        ).reshape(4, 4, 3)

        with (
            patch.object(actions, "read_item", return_value=(image, mask)),
            patch.object(actions.feature, "cached", return_value=stack),
            patch.object(
                actions.feature,
                "edge_score",
                return_value=np.zeros(image.shape[:2], dtype=np.float32),
            ),
            patch.object(actions.feature, "COUNT", 3),
        ):
            x, y = actions.make_data([object()])

        self.assertEqual(x.shape, (8, 3))
        self.assertEqual(np.bincount(y).tolist(), [4, 4])

    def test_apply_resets_refine_model_after_rf_training(self) -> None:
        x = np.zeros((4, 3), dtype=np.float32)
        y = np.array([0, 0, 1, 1], dtype=np.int8)
        segmenter = Mock()
        refiner = Mock()

        with patch.object(actions, "make_data", return_value=(x, y)):
            actions.apply([], segmenter, refiner)

        segmenter.fit.assert_called_once_with(x, y)
        refiner.reset.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
