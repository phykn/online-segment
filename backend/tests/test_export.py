import unittest
from io import BytesIO
from zipfile import ZipFile

import numpy as np
from PIL import Image

from app.export.files import make_mask_archive, make_png


class ExportTests(unittest.TestCase):
    def test_ignore_label_is_saved_as_255(self) -> None:
        mask = np.array([[-1, 0], [1, 2]], dtype=np.int8)

        png = make_png(mask, 2, 2)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")

        with Image.open(BytesIO(png)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "P")
            self.assertEqual(list(image.getdata()), [255, 0, 1, 2])

    def test_mask_archive_contains_lossless_png_files(self) -> None:
        result = np.array([[0, 1]], dtype=np.int8)
        drawn = np.array([[-1, 2]], dtype=np.int8)

        data = make_mask_archive(
            [
                ("photo_result_mask.png", result),
                ("photo_drawn_mask.png", drawn),
            ],
            2,
            1,
        )

        with ZipFile(BytesIO(data)) as archive:
            self.assertEqual(
                archive.namelist(),
                ["photo_result_mask.png", "photo_drawn_mask.png"],
            )
            for name in archive.namelist():
                self.assertEqual(archive.read(name)[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
