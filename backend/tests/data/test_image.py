import unittest

import numpy as np

from app.data.image import resize_width


class ImageTests(unittest.TestCase):
    def test_resize_width_preserves_aspect_ratio(self) -> None:
        image = np.zeros((3, 6, 3), dtype=np.uint8)

        resized = resize_width(image, 4)

        self.assertEqual(resized.shape, (2, 4, 3))

    def test_resize_width_keeps_original_when_width_is_missing(self) -> None:
        image = np.zeros((3, 6, 3), dtype=np.uint8)

        self.assertIs(resize_width(image, None), image)

    def test_resize_width_keeps_original_when_width_is_unchanged(self) -> None:
        image = np.zeros((3, 6, 3), dtype=np.uint8)

        self.assertIs(resize_width(image, 6), image)


if __name__ == "__main__":
    unittest.main()
