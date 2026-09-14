import unittest
import cv2
import numpy as np
from src.segment.cache import Cache
from src.segment.encoder import Tokens
from src.segment.feature import image_features
from src.segment.sample import spatial, quotas


class FeatureTests(unittest.TestCase):
    def test_projection_coordinates_match_resize_overlap_and_padding(self):
        from cellpose.transforms import average_tiles
        rng = np.random.default_rng(4)
        tiles = [rng.normal(size=(4, 4, 3)).astype(np.float32) for _ in range(4)]
        regions = [(0, 0), (0, 16), (16, 0), (16, 16)]
        tokens = Tokens(tiles, (39, 41), regions, (4, 5, 3, 4), 32)
        resized = np.stack([cv2.resize(t, (32, 32), interpolation=cv2.INTER_LINEAR).transpose(2, 0, 1) for t in tiles])
        expected = average_tiles(resized, [[y, y+32] for y, x in regions], [[x, x+32] for y, x in regions], 48, 48)
        expected = expected[:, 4:43, 3:44].transpose(1, 2, 0).reshape(-1, 3)
        indices = np.arange(39*41)
        np.testing.assert_allclose(tokens.pixels(indices), expected, atol=5e-7)
        chunks = np.concatenate([tokens.pixels(indices[i:i+77]) for i in range(0, len(indices), 77)])
        np.testing.assert_array_equal(chunks, tokens.pixels(indices))

    def test_diameter_resampling_matches_dense_resize_after_unpadding_and_blending(self):
        from dataclasses import replace
        rng = np.random.default_rng(2)
        tokens = Tokens([rng.normal(size=(4, 4, 3)).astype(np.float32) for _ in range(4)],
                        (39, 41), [(0, 0), (0, 16), (16, 0), (16, 16)], (4, 5, 3, 4), 32)
        dense = tokens.pixels(np.arange(39*41)).reshape(39, 41, 3)
        for shape in ((19, 21), (79, 83)):
            resized = replace(tokens, output_shape=shape)
            expected = cv2.resize(dense, (shape[1], shape[0])).reshape(-1, 3)
            indices = np.arange(np.prod(shape))
            np.testing.assert_allclose(resized.pixels(indices), expected, atol=5e-7)
            chunks = np.concatenate([resized.pixels(indices[i:i+77]) for i in range(0, len(indices), 77)])
            np.testing.assert_array_equal(chunks, resized.pixels(indices))

    def test_image_features_are_finite_for_tiny_constant_images(self):
        for shape in [(1, 1, 3), (3, 7, 3), (33, 17, 3)]:
            features = image_features(np.zeros(shape, np.uint8))
            self.assertEqual(features.shape, (*shape[:2], 16))
            self.assertTrue(np.isfinite(features).all())

    def test_lru_limit_replacement_and_oversize(self):
        cache = Cache(1)
        a = np.zeros(600000, np.uint8); b = a.copy()
        cache.put('a', a); cache.put('b', b)
        self.assertIsNone(cache.get('a')); self.assertIs(cache.get('b'), b)
        cache.put('b', np.zeros(12, np.uint8)); self.assertEqual(cache.size, 12)
        cache.put('large', np.zeros(2000000, np.uint8)); self.assertEqual(cache.size, 12)

    def test_sampling_is_bounded_balanced_and_spatial(self):
        self.assertEqual(quotas([2, 1000, 1000], 12).tolist(), [2, 5, 5])
        mask = np.ones((100, 100), bool)
        indices = spatial(mask, 100)
        self.assertEqual(len(np.unique(indices)), 100)
        y, x = np.divmod(indices, 100)
        self.assertEqual(len(np.unique(y//10*10+x//10)), 100)
        self.assertEqual(len(spatial(mask, 0)), 0)
