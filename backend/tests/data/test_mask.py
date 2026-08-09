import unittest

import numpy as np
from fastapi import HTTPException

from app.api.schema import Mask
from app.data.mask import decode, encode, resize


class MaskTests(unittest.TestCase):
    def test_rle_round_trip_keeps_row_order(self) -> None:
        source = np.array(
            [
                [0, 0, 1, 1],
                [-1, 2, 2, 3],
            ],
            dtype=np.int8,
        )

        encoded = encode(source)
        decoded = decode(encoded)

        self.assertTrue(np.array_equal(decoded, source))

    def test_rle_rejects_wrong_total(self) -> None:
        mask = Mask(width=3, height=2, runs=[(0, 5)])

        with self.assertRaises(HTTPException) as caught:
            decode(mask)

        self.assertEqual(caught.exception.status_code, 422)

    def test_resize_uses_nearest_labels(self) -> None:
        source = np.array([[0, 1], [2, 3]], dtype=np.int8)

        resized = resize(source, 4, 4)

        self.assertEqual(
            resized.tolist(),
            [
                [0, 0, 1, 1],
                [0, 0, 1, 1],
                [2, 2, 3, 3],
                [2, 2, 3, 3],
            ],
        )


if __name__ == "__main__":
    unittest.main()
