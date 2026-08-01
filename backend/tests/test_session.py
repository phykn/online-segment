import unittest

import numpy as np
from fastapi import HTTPException

from app.session import SessionStore


class SessionTests(unittest.TestCase):
    def test_models_are_isolated_between_sessions(self) -> None:
        store = SessionStore(max_age=3600, prefix="online-segment-test")
        first = store.create()
        second = store.create()
        x = np.zeros((4, 15), dtype=np.float32)
        x[2:] = 1.0
        y = np.array([0, 0, 1, 1], dtype=np.int8)

        try:
            first_model = first.segmenter.fit(x, y)
            with self.assertRaises(HTTPException):
                second.segmenter.load()

            second.segmenter.fit(x, y)
            self.assertEqual(
                first.segmenter.load().model_id_,
                first_model.model_id_,
            )
            self.assertNotEqual(
                first.segmenter.load().model_id_,
                second.segmenter.load().model_id_,
            )
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
