import unittest
from unittest.mock import patch
import numpy as np
from fastapi import HTTPException
from src.session import SessionStore
from src.config import config


class SessionTests(unittest.TestCase):
    def test_feature_caches_are_isolated_and_released(self):
        store = SessionStore(max_age=3600); first, second = store.create(), store.create()
        image = np.zeros((2, 2, 3), np.uint8)
        with patch.object(config.feature, 'kind', 'image'), patch.object(config.feature, 'cellpose', 'none'):
            first.segmenter.feature(image)
            self.assertEqual(second.segmenter.features.size, 0)
            second.segmenter.feature(image)
        store.close()
        self.assertEqual(first.segmenter.features.size, 0)
        self.assertEqual(second.segmenter.features.size, 0)

    def test_unknown_session_is_rejected(self):
        store = SessionStore(max_age=3600)
        try:
            with self.assertRaises(HTTPException) as caught:
                with store.acquire('missing'): pass
            self.assertEqual(caught.exception.status_code, 404)
        finally: store.close()
