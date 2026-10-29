from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from pathlib import Path
from threading import Barrier
from unittest import TestCase
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException

from src.config import config
from src.export.jobs import JobStore
from src.segment.prediction import infer
from src.session import SessionStore


class IsolationTests(TestCase):
    def test_concurrent_users_train_opposite_labels_on_identical_pixels(self):
        store = SessionStore(3600)
        a, b = store.create(), store.create()
        image = np.zeros((32, 32, 3), np.uint8)
        image[:, 16:] = 255
        labels = np.zeros((32, 32), np.int8)
        labels[:, 16:] = 1
        barrier = Barrier(2)

        def train(session, edits):
            with store.acquire(session.id) as acquired, acquired.lock:
                barrier.wait(timeout=5)
                acquired.segmenter.fit([(image, edits)])
                return infer(image, acquired.segmenter, train=False)[0]

        try:
            with patch.object(config.feature, 'kind', 'image'), ThreadPoolExecutor(2) as pool:
                first = pool.submit(train, a, labels)
                second = pool.submit(train, b, 1-labels)
                np.testing.assert_array_equal(first.result(), labels)
                np.testing.assert_array_equal(second.result(), 1-labels)
                self.assertIsNot(a.segmenter.classifier.model, b.segmenter.classifier.model)
                self.assertIsNot(a.segmenter.features, b.segmenter.features)
                a.segmenter.fit([])
                self.assertIsNone(a.segmenter.classifier.model)
                np.testing.assert_array_equal(infer(image, b.segmenter, train=False)[0], 1-labels)
        finally:
            store.close()

    def test_export_owner_is_checked_and_paths_do_not_collide(self):
        with TemporaryDirectory() as root:
            store = JobStore(Path(root), 3600, 'test')
            a, b = store.create('alice'), store.create('bob')
            store.start(a, 'alice', 1)
            path = store.temp_path(a)
            Path(path).write_bytes(b'zip')
            store.finish(a, 'alice', path)
            self.assertNotEqual(path, store.temp_path(b))
            for action in (store.get, store.path, store.cancel):
                with self.assertRaises(HTTPException) as caught:
                    action(a, 'bob')
                self.assertEqual(caught.exception.status_code, 404)
            self.assertTrue(Path(path).exists())
            self.assertEqual(store.path(a, 'alice'), path)

    def test_process_local_stores_cannot_resolve_each_others_sessions(self):
        first, second = SessionStore(3600), SessionStore(3600)
        session = first.create()
        try:
            with self.assertRaises(HTTPException) as caught:
                with second.acquire(session.id):
                    pass
            self.assertEqual(caught.exception.status_code, 404)
        finally:
            first.close(); second.close()
