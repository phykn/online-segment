import unittest

import numpy as np
from fastapi import HTTPException

from app.segment import feature
from app.session import SessionStore


class SessionTests(unittest.TestCase):
    def test_models_are_isolated_between_sessions(self) -> None:
        store = SessionStore(max_age=3600, prefix="online-segment-test")
        first = store.create()
        second = store.create()
        x = np.zeros((4, feature.COUNT), dtype=np.float32)
        x[2:] = 1.0
        y = np.array([0, 0, 1, 1], dtype=np.int8)

        try:
            first_segmenter = first.segmenter
            second_segmenter = second.segmenter
            first_model = first_segmenter.fit(x, y)
            with self.assertRaises(HTTPException):
                second_segmenter.load()

            second_model = second_segmenter.fit(x, y)
            self.assertIs(first_segmenter.load(), first_model)
            self.assertIs(second_segmenter.load(), second_model)
            self.assertIsNot(first_segmenter.load(), second_segmenter.load())
        finally:
            store.close()

    def test_unknown_session_is_rejected(self) -> None:
        store = SessionStore(max_age=3600, prefix="online-segment-test")
        try:
            with self.assertRaises(HTTPException) as caught:
                with store.acquire("missing"):
                    pass
        finally:
            store.close()

        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
