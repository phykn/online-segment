import unittest
import numpy as np
from src.segment.sample import spatial, quotas


class SampleTests(unittest.TestCase):
    def test_dense_regions_are_capped_even_below_class_budget(self):
        for side in (90, 300):
            mask = np.zeros((1024, 1024), bool)
            mask[20:20+side, 20:20+side] = True
            mask[800:810, 800:810] = True
            indices = spatial(mask, 10000)
            y = indices // 1024
            self.assertLessEqual(np.count_nonzero(y < 800), 256)
            self.assertGreaterEqual(np.count_nonzero(y >= 800), 4)
            self.assertTrue(mask.ravel()[indices].all())
            self.assertEqual(len(indices), len(np.unique(indices)))
            np.testing.assert_array_equal(indices, spatial(mask, 10000))

    def test_sparse_examples_survive_next_to_dense_labels(self):
        mask = np.zeros((256, 256), bool)
        mask[:128, :128] = True
        mask[200, [190, 200, 210]] = True
        indices = spatial(mask, 10000)
        self.assertTrue(set(200*256+np.array([190, 200, 210])).issubset(indices))
        mask[200, 200] = False
        self.assertNotIn(200*256+200, spatial(mask, 10000))

    def test_each_grid_cell_has_bounded_density(self):
        mask = np.ones((129, 131), bool)
        indices = spatial(mask, 10000)
        y, x = np.divmod(indices, 131)
        _, counts = np.unique((y//8)*17+x//8, return_counts=True)
        self.assertLessEqual(counts.max(), 4)
        self.assertTrue((y < 32).any() and (y > 96).any())
        self.assertTrue((x < 32).any() and (x > 96).any())

    def test_budget_is_shared_across_disconnected_regions(self):
        mask = np.zeros((64, 64), bool)
        mask[2:10, 2:10] = True
        mask[32:60, 32:60] = True
        indices = spatial(mask, 8)
        y = indices//64
        self.assertEqual(np.count_nonzero(y < 16), 4)
        self.assertEqual(np.count_nonzero(y >= 16), 4)
        self.assertEqual(len(spatial(mask, 0)), 0)
        self.assertEqual(len(spatial(np.zeros_like(mask), 100)), 0)
        np.testing.assert_array_equal(quotas([2, 1000, 1000], 12), [2, 5, 5])
