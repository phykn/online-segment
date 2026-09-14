import unittest
from unittest.mock import patch
import numpy as np
from src.config import config
from src.segment.context import extract, NAMES
from src.segment.model import Segmenter


class ContextTests(unittest.TestCase):
    def test_size_and_distance_use_original_pixels_but_ratios_do_not_scale(self):
        image = np.full((11, 19, 3), 128, np.uint8)
        masks = np.zeros((11, 19), np.int32)
        masks[1:4, 1:4] = 1000000; masks[1:8, 8:15] = 2000000
        context = extract(image, masks, np.zeros(masks.shape, np.float32))
        indices = np.array([2*19+2, 4*19+11, 0])
        one, two = context.pixels(indices), context.pixels(indices, scale=2)
        self.assertEqual(one.shape[1], len(NAMES))
        self.assertGreater(one[1, 3], one[0, 3])
        np.testing.assert_allclose(two[:, 2:6], one[:, 2:6]*2)
        np.testing.assert_array_equal(two[:, 6:-1], one[:, 6:-1])
        np.testing.assert_array_equal(one[:, -1], [9, 49, 0])
        np.testing.assert_array_equal(two[:, -1], one[:, -1]*4)
        # Every pixel of the same particle shares its area, including its edge.
        self.assertEqual(context.pixels(np.array([1*19+1]))[0, -1], one[0, -1])
        self.assertLess(one[2, 2], 0)
        self.assertTrue((one[2, 3:] == 0).all())
        # Sparse upstream instance IDs must not allocate a giant lookup table.
        self.assertEqual(context.table.shape[0], 3)

    def test_touching_particles_have_separate_boundaries(self):
        image = np.zeros((9, 11, 3), np.uint8)
        masks = np.zeros((9, 11), np.int32); masks[1:8, 1:5] = 3; masks[1:8, 5:10] = 7
        context = extract(image, masks, np.zeros(masks.shape, np.float32))
        self.assertEqual(context.distance[4, 4], 1)
        self.assertEqual(context.distance[4, 5], 1)
        self.assertEqual(context.distance[4, 7], 3)

    def test_empty_and_full_masks_are_finite_and_keep_soft_foreground_evidence(self):
        image = np.zeros((1, 3, 3), np.uint8)
        logits = np.array([[-20, 0, 20]], np.float32)
        for value in (0, 100):
            context = extract(image, np.full((1, 3), value, np.int32), logits)
            values = context.pixels(np.arange(3))
            self.assertTrue(np.isfinite(values).all())
            self.assertLess(values[0, 0], values[1, 0]); self.assertLess(values[1, 0], values[2, 0])
            np.testing.assert_array_equal(values[:, :1], context.pixels(np.arange(3), mode='foreground'))
            if value: self.assertTrue((context.distance == 1).all())

    def test_scale_is_part_of_feature_and_training_identity(self):
        image = np.zeros((9, 11, 3), np.uint8); masks = np.ones((9, 11), np.int32)
        model = Segmenter(); labels = np.zeros(masks.shape, np.int8); labels[:, 5:] = 1
        with patch.object(config.feature, 'kind', 'image'), patch.object(config.feature, 'cellpose', 'statistics'), patch('src.segment.model.runtime.run', return_value=(masks, np.zeros(masks.shape, np.float32), None)) as run:
            one = model.feature(image); two = model.feature(image, scale=2)
            self.assertIsNot(one, two)
            self.assertIs(one.context, two.context)
            model.fit([(image, labels, 1.), (image, 1-labels, 2.)])
            self.assertEqual(len(model.training), 2)
            self.assertEqual(run.call_count, 1)
