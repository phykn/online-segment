import unittest
from io import BytesIO

import numpy as np
from PIL import Image

from app.export.files import make_png


class ExportTests(unittest.TestCase):
    def test_ignore_label_is_saved_as_255(self) -> None:
        mask = np.array([[-1, 0], [1, 2]], dtype=np.int8)

        with Image.open(BytesIO(make_png(mask, 2, 2))) as image:
            self.assertEqual(image.mode, "P")
            self.assertEqual(list(image.getdata()), [255, 0, 1, 2])


if __name__ == "__main__":
    unittest.main()
