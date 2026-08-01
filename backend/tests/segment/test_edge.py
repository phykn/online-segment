import unittest

import numpy as np

from app.segment import edge


class EdgeTests(unittest.TestCase):
    def test_constant_prediction_is_unchanged(self) -> None:
        image = np.zeros((10, 12, 3), dtype=np.uint8)
        probs = np.zeros((10, 12, 2), dtype=np.float32)
        probs[..., 0] = 1.0

        adjusted = edge.adjust(image, probs)

        self.assertIs(adjusted, probs)

    def test_prediction_moves_to_strong_edge(self) -> None:
        image = np.zeros((24, 24, 3), dtype=np.uint8)
        image[:, 10:] = 255
        probs = np.empty((24, 24, 2), dtype=np.float32)
        probs[..., 0] = 0.95
        probs[..., 1] = 0.05
        probs[:, 10:12, 0] = 0.55
        probs[:, 10:12, 1] = 0.45
        probs[:, 12:, 0] = 0.05
        probs[:, 12:, 1] = 0.95

        adjusted = edge.adjust(image, probs)
        labels = np.argmax(adjusted, axis=2)

        self.assertTrue((labels[:, :10] == 0).all())
        self.assertTrue((labels[:, 10:] == 1).all())


if __name__ == "__main__":
    unittest.main()
