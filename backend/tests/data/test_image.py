import unittest
from io import BytesIO

import numpy as np
from PIL import Image

from app.data.image import read_bytes, resize_width


class ImageTests(unittest.TestCase):
    def test_read_bytes_applies_exif_orientation(self) -> None:
        source = Image.new("RGB", (2, 3))
        exif = Image.Exif()
        exif[274] = 6

        for image_format in ("JPEG", "TIFF"):
            with self.subTest(image_format=image_format):
                output = BytesIO()
                source.save(output, format=image_format, exif=exif)
                image = read_bytes(output.getvalue())

                self.assertEqual(image.shape, (2, 3, 3))

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
