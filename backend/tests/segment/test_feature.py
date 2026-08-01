import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from app import ROOT
from app.segment import feature


class FeatureTests(unittest.TestCase):
    def test_sample_shape_and_values(self) -> None:
        path = ROOT.parent / "frontend" / "asset" / "sample_1.jpg"
        image = np.asarray(Image.open(path).convert("RGB"))

        stack = feature.make(image)

        self.assertEqual(stack.shape, (*image.shape[:2], feature.COUNT))
        self.assertEqual(stack.dtype, np.float32)
        self.assertTrue(np.isfinite(stack).all())

    def test_constant_image_is_zero(self) -> None:
        image = np.full((16, 20, 3), 128, dtype=np.uint8)

        stack = feature.make(image)

        self.assertTrue(np.array_equal(stack, np.zeros_like(stack)))

    def test_reduced_features_keep_edges_and_curvature(self) -> None:
        image = np.zeros((65, 65, 3), dtype=np.uint8)
        image[28:37, 28:37] = 255

        stack = feature.make(image)

        self.assertEqual(feature.COUNT, 15)
        self.assertEqual(feature.cfg.hessian_factors, (1.0, 2.0, 4.0))
        self.assertEqual(feature.cfg.log_factors, (2.0, 4.0))
        self.assertNotIn("cache_mb", feature.config())
        self.assertGreater(float(np.max(np.abs(stack[..., 2:]))), 0.0)

    def test_cached_reuses_features_for_same_image(self) -> None:
        image = np.zeros((8, 9, 3), dtype=np.uint8)
        stack = np.zeros((8, 9, feature.COUNT), dtype=np.float32)
        feature.cache.clear()

        with patch.object(feature, "make", return_value=stack) as make:
            first = feature.cached(image)
            second = feature.cached(image.copy())

        self.assertIs(first, second)
        make.assert_called_once()

    def test_cached_separates_changed_images(self) -> None:
        first = np.zeros((8, 9, 3), dtype=np.uint8)
        second = first.copy()
        second[0, 0] = 1
        feature.cache.clear()

        with patch.object(feature, "make", wraps=feature.make) as make:
            feature.cached(first)
            feature.cached(second)

        self.assertEqual(make.call_count, 2)


if __name__ == "__main__":
    unittest.main()
