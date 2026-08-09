import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from app import ROOT
from app.segment import feature


class FeatureTests(unittest.TestCase):
    def test_sample_shape_and_values(self) -> None:
        path = ROOT.parent / "frontend" / "asset" / "sample1.png"
        image = np.asarray(Image.open(path).convert("RGB"))

        stack = feature.make(image)

        self.assertEqual(stack.shape, (*image.shape[:2], feature.COUNT))
        self.assertEqual(stack.dtype, np.float32)
        self.assertTrue(np.isfinite(stack).all())

    def test_constant_image_is_zero(self) -> None:
        image = np.full((16, 20, 3), 128, dtype=np.uint8)

        stack = feature.make(image)

        self.assertTrue(np.array_equal(stack, np.zeros_like(stack)))

    def test_parallel_make_preserves_serial_feature_order(self) -> None:
        image = np.random.default_rng(7).integers(
            0,
            256,
            size=(160, 192, 3),
            dtype=np.uint8,
        )
        gray = feature.normalize(image)
        values = [gray]
        for factor, sigma in zip(
            feature.cfg.factors,
            feature.sigmas(image.shape),
            strict=True,
        ):
            values.extend(feature._scale_features(gray, factor, sigma))
        values.extend(
            feature._context_features(
                gray,
                feature.context_windows(image.shape),
            )
        )

        expected = np.stack(values, axis=-1).astype(np.float32, copy=False)
        np.testing.assert_array_equal(feature.make(image), expected)

    def test_reduced_features_keep_edges_curvature_and_context(self) -> None:
        image = np.zeros((65, 65, 3), dtype=np.uint8)
        image[28:37, 28:37] = 255

        stack = feature.make(image)

        self.assertEqual(feature.COUNT, 16)
        self.assertEqual(feature.cfg.hessian_factors, (1.0, 2.0, 4.0))
        self.assertEqual(feature.cfg.context_factors, (8.0, 16.0, 32.0))
        self.assertNotIn("cache_mb", feature.config())
        self.assertGreater(float(np.max(np.abs(stack[..., 2:]))), 0.0)

    def test_context_features_distinguish_same_color_by_size(self) -> None:
        height = width = 257
        y, x = np.ogrid[:height, :width]
        image = np.zeros((height, width, 3), dtype=np.uint8)
        small = (x - 64) ** 2 + (y - 128) ** 2 <= 8**2
        large = (x - 192) ** 2 + (y - 128) ** 2 <= 32**2
        image[small | large] = 255

        stack = feature.make(image)
        small_center = stack[128, 64]
        large_center = stack[128, 192]

        self.assertEqual(float(small_center[0]), float(large_center[0]))
        self.assertLess(
            float(
                np.max(
                    np.abs(
                        small_center[: feature.CONTEXT_START]
                        - large_center[: feature.CONTEXT_START]
                    )
                )
            ),
            0.01,
        )
        self.assertGreater(
            float(
                np.max(
                    np.abs(
                        small_center[feature.CONTEXT_START :]
                        - large_center[feature.CONTEXT_START :]
                    )
                )
            ),
            0.2,
        )

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
