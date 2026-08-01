import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch

from app.refine import train
from app.refine.model import Refiner


class TrainTests(unittest.TestCase):
    def test_fit_caps_and_downweights_pseudo_labels(self) -> None:
        target = SimpleNamespace(image="target")
        image = np.zeros((4, 5, 3), dtype=np.uint8)
        mask = np.full((4, 5), -1, dtype=np.int8)
        mask[0, 0] = 0
        mask[3, 4] = 1
        probs = np.full((4, 5, 2), 0.5, dtype=np.float32)
        classifier = SimpleNamespace(
            classes_=np.array([0, 1], dtype=np.int8),
            model_id_="rf-id",
        )

        with (
            patch.object(train.segmenter, "load", return_value=classifier),
            patch.object(train, "read_item", return_value=(image, mask)),
            patch.object(train.segmenter, "prob", return_value=probs),
            patch.object(
                train,
                "_select",
                return_value=(
                    np.array([5, 15]),
                    np.array([0, 1], dtype=np.int8),
                ),
            ) as select,
            patch.object(train, "_learn") as learn,
        ):
            train.fit([target], target)

        self.assertEqual(select.call_args.args[3], {0: 1, 1: 1})
        data, classes, rf_id = learn.call_args.args
        labels = data[0][2].ravel()
        weights = data[0][3].ravel()
        manual = data[0][4].ravel()
        self.assertEqual(labels[0], 0)
        self.assertEqual(labels[19], 1)
        self.assertEqual(labels[5], 0)
        self.assertEqual(labels[15], 1)
        self.assertEqual(weights[0], 1.0)
        self.assertEqual(weights[19], 1.0)
        self.assertEqual(weights[5], train.cfg.pseudo_weight)
        self.assertEqual(weights[15], train.cfg.pseudo_weight)
        self.assertTrue(manual[0])
        self.assertTrue(manual[19])
        self.assertFalse(manual[5])
        self.assertFalse(manual[15])
        self.assertTrue(np.array_equal(classes, classifier.classes_))
        self.assertEqual(rf_id, "rf-id")

    def test_focal_loss_only_changes_manual_pixels(self) -> None:
        logits = torch.zeros((1, 2, 1, 2))
        targets = torch.zeros((1, 1, 2), dtype=torch.long)
        weights = torch.ones((1, 1, 2))
        manual = torch.tensor([[[True, False]]])

        mixed = train._loss(
            logits,
            targets,
            weights,
            manual,
        )
        pseudo = train._loss(
            logits,
            targets,
            weights,
            torch.zeros_like(manual),
        )
        all_manual = train._loss(
            logits,
            targets,
            weights,
            torch.ones_like(manual),
        )

        self.assertLess(float(all_manual), float(mixed))
        self.assertLess(float(mixed), float(pseudo))

    def test_learned_model_adjusts_probabilities(self) -> None:
        image = np.zeros((32, 32, 3), dtype=np.uint8)
        image[:, 16:] = 255
        probs = np.full((32, 32, 2), 0.5, dtype=np.float32)
        targets = np.full((32, 32), -1, dtype=np.int64)
        weights = np.zeros((32, 32), dtype=np.float32)
        manual = np.zeros((32, 32), dtype=bool)
        for y, x, label, is_manual in (
            (8, 8, 0, True),
            (24, 24, 1, True),
            (8, 24, 1, False),
            (24, 8, 0, False),
        ):
            targets[y, x] = label
            weights[y, x] = 1.0 if is_manual else train.cfg.pseudo_weight
            manual[y, x] = is_manual
        classes = np.array([0, 1], dtype=np.int8)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "refine.pt"
            refiner = Refiner(path)
            cfg = train.cfg.model_copy(update={"patch": 32, "first_steps": 1})
            with (
                patch.object(train, "cfg", cfg),
                patch.object(train, "refiner", refiner),
            ):
                result = train._learn(
                    [(image, probs, targets, weights, manual)],
                    classes,
                    "rf-id",
                )
                adjusted = refiner.adjust(
                    image,
                    probs,
                    classes,
                    "rf-id",
                )

        self.assertEqual(result["steps"], 1)
        self.assertEqual(adjusted.shape, probs.shape)
        np.testing.assert_allclose(adjusted.sum(axis=2), 1.0, atol=1e-5)

    def test_select_caps_each_label_and_skips_manual_pixels(self) -> None:
        mask = np.full((8, 10), -1, dtype=np.int8)
        mask[0, 0] = 0
        classes = np.array([0, 1], dtype=np.int8)
        probs = np.empty((mask.size, 2), dtype=np.float32)
        probs[:, 0] = 0.99
        probs[:, 1] = 0.01
        probs[40:, 0] = 0.01
        probs[40:, 1] = 0.99

        indices, labels = train._select(
            probs,
            classes,
            mask,
            {0: 3, 1: 2},
        )

        self.assertEqual(np.sum(labels == 0), 3)
        self.assertEqual(np.sum(labels == 1), 2)
        self.assertNotIn(0, indices)

    def test_select_caps_all_labels_together(self) -> None:
        mask = np.full((4, 5), -1, dtype=np.int8)
        classes = np.array([0, 1], dtype=np.int8)
        probs = np.empty((mask.size, 2), dtype=np.float32)
        probs[:, 0] = 0.99
        probs[:, 1] = 0.01

        cfg = train.cfg.model_copy(update={"max_total": 3})
        with patch.object(train, "cfg", cfg):
            indices, labels = train._select(
                probs,
                classes,
                mask,
                {0: 20, 1: 20},
            )

        self.assertEqual(indices.size, 3)
        self.assertEqual(labels.size, 3)

    def test_select_balances_labels(self) -> None:
        mask = np.full((10, 20), -1, dtype=np.int8)
        classes = np.array([0, 1], dtype=np.int8)
        probs = np.empty((mask.size, 2), dtype=np.float32)
        probs[:, 0] = 0.99
        probs[:, 1] = 0.01
        probs[100:, 0] = 0.01
        probs[100:, 1] = 0.99

        cfg = train.cfg.model_copy(update={"max_total": 10})
        with patch.object(train, "cfg", cfg):
            _, labels = train._select(
                probs,
                classes,
                mask,
                {0: 100, 1: 100},
            )

        self.assertEqual(np.sum(labels == 0), 5)
        self.assertEqual(np.sum(labels == 1), 5)

    def test_select_balances_three_labels(self) -> None:
        mask = np.full((10, 30), -1, dtype=np.int8)
        classes = np.array([0, 1, 2], dtype=np.int8)
        probs = np.full((*mask.shape, classes.size), 0.005, dtype=np.float32)
        probs[:, :10, 0] = 0.99
        probs[:, 10:20, 1] = 0.99
        probs[:, 20:, 2] = 0.99
        probs = probs.reshape(mask.size, classes.size)

        cfg = train.cfg.model_copy(update={"max_total": 10})
        with patch.object(train, "cfg", cfg):
            _, labels = train._select(
                probs,
                classes,
                mask,
                {0: 100, 1: 100, 2: 100},
            )

        self.assertEqual(np.sum(labels == 0), 4)
        self.assertEqual(np.sum(labels == 1), 3)
        self.assertEqual(np.sum(labels == 2), 3)

    def test_core_excludes_prediction_boundary(self) -> None:
        labels = np.zeros((9, 9), dtype=np.int8)
        labels[:, 5:] = 1

        core = train._core(labels).reshape(labels.shape)

        self.assertFalse(core[:, 4:6].any())
        self.assertTrue(core[:, :2].all())
        self.assertTrue(core[:, 8].all())


if __name__ == "__main__":
    unittest.main()
