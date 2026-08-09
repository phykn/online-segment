import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event, RLock
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

import numpy as np
from PIL import Image

from app.config import config
from app.export.archive import make_mask_archive, make_png
from app.export.jobs import JobStore
from app.export.pipeline import append_archive_batch


class ExportTests(unittest.TestCase):
    def test_ignore_label_is_saved_as_255(self) -> None:
        mask = np.array([[-1, 0], [1, 2]], dtype=np.int8)

        png = make_png(mask, 2, 2)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")

        with Image.open(BytesIO(png)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "P")
            self.assertEqual(
                list(image.get_flattened_data()),
                [255, 0, 1, 2],
            )

    def test_spatial_mask_png_is_compressed(self) -> None:
        mask = np.zeros((512, 512), dtype=np.int8)
        mask[128:384, 128:384] = 1

        png = make_png(mask, 512, 512)

        self.assertLess(len(png), mask.nbytes // 8)

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

    def test_archive_preserves_order_with_feature_lookahead(self) -> None:
        image_bytes = []
        for color in ("black", "white"):
            source = BytesIO()
            Image.new("RGB", (2, 1), color).save(source, format="PNG")
            image_bytes.append(source.getvalue())

        with TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp), max_age=3600, prefix="test")
            job_id = store.create("session-a")
            store.start(job_id, "session-a", 2)
            session = SimpleNamespace(
                id="session-a",
                lock=RLock(),
                segmenter=SimpleNamespace(
                    load=Mock(return_value=object()),
                    features=Mock(
                        side_effect=lambda image, cached: (image[..., :1] > 0)
                    ),
                ),
            )

            with (
                patch("app.export.pipeline.jobs", store),
                patch(
                    "app.export.pipeline.prediction.predict_features",
                    side_effect=lambda stack, segmenter, model: stack[
                        ..., 0
                    ].astype(np.int8),
                ) as predict,
            ):
                append_archive_batch(
                    job_id,
                    None,
                    [
                        ("same.png", BytesIO(image_bytes[0])),
                        ("same.png", BytesIO(image_bytes[1])),
                    ],
                    session,
                )

            self.assertEqual(store.get(job_id, session.id)["status"], "ready")
            with ZipFile(store.path(job_id, session.id)) as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["same.png", "same_2.png"],
                )
                with Image.open(BytesIO(archive.read("same.png"))) as first:
                    self.assertEqual(list(first.get_flattened_data()), [0, 0])
                with Image.open(BytesIO(archive.read("same_2.png"))) as second:
                    self.assertEqual(list(second.get_flattened_data()), [1, 1])
            self.assertEqual(session.segmenter.load.call_count, 1)
            self.assertEqual(session.segmenter.features.call_count, 2)
            self.assertEqual(predict.call_count, 2)
            self.assertTrue(
                all(
                    call.kwargs == {"cached": False}
                    for call in session.segmenter.features.call_args_list
                )
            )

    def test_next_features_overlap_current_prediction(self) -> None:
        source = BytesIO()
        Image.new("RGB", (2, 1), "white").save(source, format="PNG")
        image_bytes = source.getvalue()
        second_started = Event()
        release_second = Event()
        feature_calls = 0

        def make_features(image, cached=True):
            nonlocal feature_calls
            feature_calls += 1
            if feature_calls == 2:
                second_started.set()
                if not release_second.wait(5):
                    raise AssertionError(
                        "second feature extraction was not released"
                    )
            return np.zeros((1, 2, 1))

        def predict_features(stack, segmenter, classifier):
            if not second_started.wait(5):
                raise AssertionError("next feature extraction did not overlap")
            release_second.set()
            return np.zeros((1, 2), dtype=np.int8)

        with TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp), max_age=3600, prefix="test")
            job_id = store.create("session-a")
            store.start(job_id, "session-a", 2)
            session = SimpleNamespace(
                id="session-a",
                lock=RLock(),
                segmenter=SimpleNamespace(
                    load=Mock(return_value=object()),
                    features=make_features,
                ),
            )

            with (
                patch("app.export.pipeline.jobs", store),
                patch(
                    "app.export.pipeline.prediction.predict_features",
                    side_effect=predict_features,
                ),
            ):
                append_archive_batch(
                    job_id,
                    None,
                    [
                        ("first.png", BytesIO(image_bytes)),
                        ("second.png", BytesIO(image_bytes)),
                    ],
                    session,
                )

            self.assertEqual(store.get(job_id, session.id)["status"], "ready")

    def test_large_export_builds_gpu_during_feature_lookahead(self) -> None:
        source = BytesIO()
        Image.new("RGB", (2, 1), "white").save(source, format="PNG")
        image_bytes = source.getvalue()
        second_started = Event()
        release_second = Event()
        feature_calls = 0
        predictor = object()
        model = object()

        def make_features(image, cached=True):
            nonlocal feature_calls
            feature_calls += 1
            if feature_calls == 2:
                second_started.set()
                if not release_second.wait(5):
                    raise AssertionError(
                        "GPU initialization did not release lookahead"
                    )
            return np.zeros((1, 2, 1))

        def make_predictor(classifier):
            if not second_started.wait(5):
                raise AssertionError(
                    "GPU initialization started before feature lookahead"
                )
            release_second.set()
            return predictor

        with TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp), max_age=3600, prefix="test")
            job_id = store.create("session-a")
            store.start(job_id, "session-a", 2)
            session = SimpleNamespace(
                id="session-a",
                lock=RLock(),
                segmenter=SimpleNamespace(
                    load=Mock(return_value=model),
                    features=make_features,
                    batch_predictor=Mock(side_effect=make_predictor),
                ),
            )

            with (
                patch("app.export.pipeline.jobs", store),
                patch.object(
                    config.performance.export,
                    "gpu_min_pixels",
                    4,
                ),
                patch(
                    "app.export.pipeline.prediction.predict_features",
                    return_value=np.zeros((1, 2), dtype=np.int8),
                ) as predict,
            ):
                append_archive_batch(
                    job_id,
                    None,
                    [
                        ("first.png", BytesIO(image_bytes)),
                        ("second.png", BytesIO(image_bytes)),
                    ],
                    session,
                )

            session.segmenter.batch_predictor.assert_called_once_with(model)
            self.assertEqual(predict.call_count, 2)
            self.assertTrue(
                all(
                    call.kwargs == {"predictor": predictor}
                    for call in predict.call_args_list
                )
            )

    def test_feature_lookahead_error_removes_partial_archive(self) -> None:
        source = BytesIO()
        Image.new("RGB", (2, 1), "white").save(source, format="PNG")
        image_bytes = source.getvalue()
        feature_calls = 0

        def make_features(image, cached=True):
            nonlocal feature_calls
            feature_calls += 1
            if feature_calls == 2:
                raise RuntimeError("feature preparation failed")
            return np.zeros((1, 2, 1))

        with TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp), max_age=3600, prefix="test")
            job_id = store.create("session-a")
            store.start(job_id, "session-a", 2)
            session = SimpleNamespace(
                id="session-a",
                lock=RLock(),
                segmenter=SimpleNamespace(
                    load=Mock(return_value=object()),
                    features=make_features,
                ),
            )

            with (
                patch("app.export.pipeline.jobs", store),
                patch(
                    "app.export.pipeline.prediction.predict_features",
                    return_value=np.zeros((1, 2), dtype=np.int8),
                ),
                self.assertRaisesRegex(
                    RuntimeError,
                    "feature preparation failed",
                ),
            ):
                append_archive_batch(
                    job_id,
                    None,
                    [
                        ("first.png", BytesIO(image_bytes)),
                        ("second.png", BytesIO(image_bytes)),
                    ],
                    session,
                )

            state = store.get(job_id, session.id)
            self.assertEqual(state["status"], "error")
            self.assertEqual(state["done"], 1)
            self.assertFalse(Path(store.temp_path(job_id)).exists())

    def test_concurrent_duplicate_batch_preserves_completed_archive(self) -> None:
        source = BytesIO()
        Image.new("RGB", (2, 1), "white").save(source, format="PNG")
        image_bytes = source.getvalue()

        class ContendedLock:
            def __init__(self) -> None:
                self.barrier = Barrier(2)
                self.lock = RLock()

            def __enter__(self):
                self.barrier.wait(timeout=5)
                self.lock.acquire()
                return self

            def __exit__(self, *_) -> None:
                self.lock.release()

        with TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp), max_age=3600, prefix="test")
            job_id = store.create("session-a")
            store.start(job_id, "session-a", 1)
            session = SimpleNamespace(
                id="session-a",
                lock=ContendedLock(),
                segmenter=SimpleNamespace(
                    load=Mock(return_value=object()),
                    features=Mock(
                        return_value=np.zeros((1, 2, 1), dtype=np.float32)
                    ),
                ),
            )

            with (
                patch("app.export.pipeline.jobs", store),
                patch(
                    "app.export.pipeline.prediction.predict_features",
                    return_value=np.zeros((1, 2), dtype=np.int8),
                ),
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                futures = [
                    pool.submit(
                        append_archive_batch,
                        job_id,
                        None,
                        [(f"{idx}.png", BytesIO(image_bytes))],
                        session,
                    )
                    for idx in range(2)
                ]
                errors = []
                for future in futures:
                    try:
                        future.result(timeout=5)
                    except Exception as error:
                        errors.append(error)

            state = store.get(job_id, session.id)
            self.assertEqual(state["status"], "ready")
            self.assertEqual(state["done"], 1)
            self.assertTrue(Path(store.path(job_id, session.id)).exists())
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].status_code, 409)

if __name__ == "__main__":
    unittest.main()
