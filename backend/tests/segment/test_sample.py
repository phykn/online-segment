import unittest

import numpy as np

from app.segment import sample


class SampleTests(unittest.TestCase):
    def test_quotas_spread_points_across_images(self) -> None:
        values = sample.quotas([100, 100, 2], 12)

        self.assertEqual(sum(values), 12)
        self.assertEqual(values, [5, 5, 2])

    def test_spatial_covers_the_image(self) -> None:
        mask = np.ones((8, 8), dtype=bool)

        indices = sample.spatial(mask, 4)
        y, x = np.unravel_index(indices, mask.shape)
        quadrants = set(zip(y // 4, x // 4))

        self.assertEqual(len(indices), 4)
        self.assertEqual(quadrants, {(0, 0), (0, 1), (1, 0), (1, 1)})

    def test_guided_reserves_samples_for_strong_edges(self) -> None:
        mask = np.ones((10, 10), dtype=bool)
        score = np.zeros((10, 10), dtype=np.float32)
        score[:, 4:6] = 1.0

        indices = sample.guided(mask, score, 10, 0.5, 0.75)
        _, x = np.unravel_index(indices, mask.shape)

        self.assertEqual(indices.size, 10)
        self.assertGreaterEqual(np.sum((x >= 4) & (x < 6)), 5)

    def test_guided_falls_back_when_scores_are_flat(self) -> None:
        mask = np.ones((8, 8), dtype=bool)
        score = np.zeros((8, 8), dtype=np.float32)

        guided = sample.guided(mask, score, 4, 0.5, 0.75)

        self.assertTrue(np.array_equal(guided, sample.spatial(mask, 4)))


if __name__ == "__main__":
    unittest.main()
