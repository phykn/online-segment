import tempfile
import unittest
from pathlib import Path
import numpy as np

from app.refine import net, train
from app.refine.model import Refiner


class ModelTests(unittest.TestCase):
    def test_input_is_channel_first_float32(self) -> None:
        image = np.zeros((8, 9, 3), dtype=np.uint8)
        probs = np.full((8, 9, 2), 0.5, dtype=np.float32)

        value = net.input(image, probs)

        self.assertEqual(value.shape, (4, 8, 9))
        self.assertEqual(value.dtype, np.float32)

    def test_input_gradient_marks_image_edge(self) -> None:
        image = np.zeros((8, 9, 3), dtype=np.uint8)
        image[:, 5:] = 255
        probs = np.full((8, 9, 2), 0.5, dtype=np.float32)

        value = net.input(image, probs)

        self.assertGreater(float(value[1].max()), 0.0)
        self.assertEqual(float(value[1, :, :3].max()), 0.0)

    def test_adjust_without_model_keeps_rf_probabilities(self) -> None:
        image = np.zeros((8, 9, 3), dtype=np.uint8)
        probs = np.full((8, 9, 2), 0.5, dtype=np.float32)
        classes = np.array([0, 1], dtype=np.int8)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "refine.pt"
            adjusted = Refiner(path).adjust(image, probs, classes, "rf-id")

        self.assertIs(adjusted, probs)

    def test_prepare_keeps_manual_and_pseudo_weights(self) -> None:
        image = np.zeros((12, 14, 3), dtype=np.uint8)
        probs = np.full((12, 14, 2), 0.5, dtype=np.float32)
        target = np.full((12, 14), -1, dtype=np.int64)
        weights = np.zeros((12, 14), dtype=np.float32)
        manual = np.zeros((12, 14), dtype=bool)
        target[3, 4] = 0
        weights[3, 4] = 1.0
        manual[3, 4] = True
        target[8, 9] = 1
        weights[8, 9] = 0.25

        ready, groups = train._prepare(
            [(image, probs, target, weights, manual)]
        )

        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0][0].shape[0], 4)
        self.assertEqual(groups[True][0][0][1].tolist(), [[3, 4]])
        self.assertEqual(groups[False][1][0][1].tolist(), [[8, 9]])

    def test_batch_uses_three_manual_centers_and_one_pseudo(self) -> None:
        image = np.zeros((8, 8, 3), dtype=np.uint8)
        probs = np.full((8, 8, 2), 0.5, dtype=np.float32)
        data = []
        for label, is_manual in ((0, True), (1, False)):
            target = np.full((8, 8), -1, dtype=np.int64)
            weights = np.zeros((8, 8), dtype=np.float32)
            manual = np.zeros((8, 8), dtype=bool)
            target[4, 4] = label
            weights[4, 4] = 1.0 if is_manual else 0.25
            manual[4, 4] = is_manual
            data.append((image, probs, target, weights, manual))

        ready, groups = train._prepare(data)
        _, targets, _, manuals = train._batch(
            ready,
            groups,
            np.random.default_rng(0),
            0,
        )
        labels = [int(values[values >= 0][0]) for values in targets]
        sources = [bool(values.any()) for values in manuals]

        self.assertEqual(labels, [0, 0, 0, 1])
        self.assertEqual(sources, [True, True, True, False])


if __name__ == "__main__":
    unittest.main()
