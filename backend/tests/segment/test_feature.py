import unittest
import cv2
import numpy as np
from src.segment.cache import Cache
from src.segment.encoder import Tokens
from src.segment.feature import image_features, luminance, size_features


class FeatureTests(unittest.TestCase):
    def test_luminance_ignores_gain_offset_and_gamma(self):
        rng = np.random.default_rng(0)
        field = cv2.GaussianBlur(rng.normal(size=(96, 128)).astype(np.float32), (0, 0), 6)
        gray = np.select([field < -.05, field < .05], [.1, .4], .85) + rng.normal(0, .02, field.shape)
        image = lambda g: np.repeat(np.rint(np.clip(g, 0, 1)*255).astype(np.uint8)[..., None], 3, -1)
        base = luminance(image(gray))
        self.assertLess(np.abs(luminance(image(.2 + .6*gray)) - base).mean(), .005)
        for gamma in (.7, 1.5):
            self.assertLess(np.abs(luminance(image(np.clip(gray, 0, 1)**gamma)) - base).mean(), .02)
        # The linear stretch it replaced moved by far more under the same gamma.
        stretch = lambda g: np.clip((g - np.percentile(g, 1)) / (np.percentile(g, 99) - np.percentile(g, 1)), 0, 1)
        self.assertGreater(np.abs(stretch(np.clip(gray, 0, 1)**1.5) - stretch(gray)).mean(), .05)

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
            size = size_features(np.zeros(shape, np.uint8))
            self.assertEqual(size.shape, (*shape[:2], 7))
            self.assertTrue(np.isfinite(size).all())

    def test_size_channels_keep_a_large_particle_bright_to_its_rim(self):
        image = np.zeros((128, 128, 3), np.uint8)
        cv2.circle(image, (40, 64), 24, (200, 200, 200), -1)
        for y in (24, 64, 104):
            cv2.circle(image, (104, y), 5, (200, 200, 200), -1)
        size, gray = size_features(image), luminance(image)
        bright, dark = gray[64, 40], gray[0, 0]
        # Widest disk (radius 8 at this image size): the big particle's rim, 2 px inside its edge,
        # keeps its brightness, while a grain of radius 5 sinks to the background.
        self.assertLess(abs(size[64, 18, -1] - bright), .1*(bright-dark))
        self.assertLess(abs(size[64, 104, -1] - dark), .1*(bright-dark))
        self.assertLess(abs(size[64, 104, 0] - bright), .1*(bright-dark))

    def test_small_images_keep_distinct_filter_scales(self):
        image = np.random.default_rng(0).integers(0, 256, (128, 128, 3), dtype=np.uint8)
        features = image_features(image)
        self.assertFalse(np.array_equal(features[..., 1:5], features[..., 5:9]))
        self.assertFalse(np.array_equal(features[..., 5:9], features[..., 9:13]))

    def test_lru_limit_replacement_and_oversize(self):
        cache = Cache(1)
        a = np.zeros(600000, np.uint8); b = a.copy()
        cache.put('a', a); cache.put('b', b)
        self.assertIsNone(cache.get('a')); self.assertIs(cache.get('b'), b)
        cache.put('b', np.zeros(12, np.uint8)); self.assertEqual(cache.size, 12)
        cache.put('large', np.zeros(2000000, np.uint8)); self.assertEqual(cache.size, 12)

    def test_optional_texture_measures_local_variation_without_proposals(self):
        image = np.full((128, 128, 3), 128, np.uint8)
        image[:, 64:] = (np.indices((128, 64)).sum(axis=0)[..., None] % 2)*255
        baseline = image_features(image)
        textured = image_features(image, texture=True)
        self.assertEqual(textured.shape[-1], 19)
        np.testing.assert_array_equal(textured[..., :16], baseline)
        self.assertTrue(np.isfinite(textured).all())
        self.assertLess(textured[64, 16, 16:].max(), .001)
        self.assertGreater(textured[64, 112, 16:].min(), .1)
