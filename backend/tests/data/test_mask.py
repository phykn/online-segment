import unittest

import numpy as np
from fastapi import HTTPException

from app.api.schema import Mask
from app.data.mask import (
    MAX_DECODED_PIXELS,
    _decoded_size,
    decode,
    encode,
    resize,
)


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

    def test_rle_rejects_malicious_lengths(self) -> None:
        masks = [
            Mask(width=1, height=1, runs=[]),
            Mask(width=1, height=1, runs=[(0, 0), (1, 1)]),
            Mask(width=1, height=1, runs=[(0, -1), (1, 2)]),
            Mask(width=1, height=1, runs=[(0, 2**63)]),
        ]

        for mask in masks:
            with self.subTest(runs=mask.runs):
                with self.assertRaises(HTTPException) as caught:
                    decode(mask)
                self.assertEqual(caught.exception.status_code, 422)

    def test_rle_rejects_oversized_decoded_masks(self) -> None:
        self.assertEqual(
            _decoded_size(MAX_DECODED_PIXELS, 1),
            MAX_DECODED_PIXELS,
        )

        masks = [
            Mask(
                width=MAX_DECODED_PIXELS + 1,
                height=1,
                runs=[(0, MAX_DECODED_PIXELS + 1)],
            ),
            Mask(
                width=2**63,
                height=1,
                runs=[(0, 2**63)],
            ),
        ]
        for mask in masks:
            with self.subTest(width=mask.width):
                with self.assertRaises(HTTPException) as caught:
                    decode(mask)
                self.assertEqual(caught.exception.status_code, 422)

    def test_encode_preserves_run_boundaries(self) -> None:
        source = np.array([[0, 0, 1], [1, -1, -1]], dtype=np.int8)

        encoded = encode(source)

        self.assertEqual(encoded.runs, [(0, 2), (1, 2), (-1, 2)])

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
