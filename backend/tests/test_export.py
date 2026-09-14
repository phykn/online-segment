import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, RLock
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

import numpy as np
from PIL import Image

from src.export.archive import make_mask_archive, make_png
from src.export.jobs import JobStore
from src.export.pipeline import append_archive_batch


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

    def test_batch_preserves_order_size_threshold_and_edits(self):
        sources=[]
        for color in ('black','white'):
            buf=BytesIO();Image.new('RGB',(4,2),color).save(buf,format='PNG');sources.append(buf.getvalue())
        with TemporaryDirectory() as tmp:
            store=JobStore(Path(tmp),3600,'test')
            job=store.create('a');store.start(job,'a',2)
            session=SimpleNamespace(id='a',lock=RLock(),segmenter=object())
            from src.api.schema import Mask
            edits=[Mask(width=2,height=1,runs=[(-1,1),(3,1)]),None]
            with patch('src.export.pipeline.jobs',store), patch('src.export.pipeline.prediction.predict',
                    return_value=np.array([[0,3]],np.int8)) as run:
                append_archive_batch(job,2, [('same.png',BytesIO(b)) for b in sources],session,19,edits)
            self.assertEqual(run.call_count,2)
            self.assertEqual(run.call_args_list[0].args[0].shape,(1,2,3))
            self.assertEqual(run.call_args_list[0].args[2:4],(19,4))
            np.testing.assert_array_equal(run.call_args_list[0].args[4],[[-1,3]])
            self.assertIsNone(run.call_args_list[1].args[4])
            with ZipFile(store.path(job,'a')) as archive:
                self.assertEqual(archive.namelist(),['same.png','same_2.png'])
                with Image.open(BytesIO(archive.read('same.png'))) as im:
                    self.assertEqual(im.size,(4,2))
                    self.assertEqual(list(im.get_flattened_data()),[0,0,3,3,0,0,3,3])

    def test_failure_removes_partial_archive(self):
        buf=BytesIO();Image.new('RGB',(2,1)).save(buf,format='PNG')
        with TemporaryDirectory() as tmp:
            store=JobStore(Path(tmp),3600,'test');job=store.create('a');store.start(job,'a',2)
            session=SimpleNamespace(id='a',lock=RLock(),segmenter=object())
            with patch('src.export.pipeline.jobs',store),patch('src.export.pipeline.prediction.predict',
                    side_effect=[np.zeros((1,2),np.int8),RuntimeError('inference failed')]):
                with self.assertRaisesRegex(RuntimeError,'inference failed'):
                    append_archive_batch(job,None,[('a',BytesIO(buf.getvalue())),('b',BytesIO(buf.getvalue()))],session)
            self.assertEqual(store.get(job,'a')['status'],'error')
            self.assertEqual(store.get(job,'a')['done'],1)
            self.assertFalse(Path(store.temp_path(job)).exists())

    def test_cancellation_is_checked_during_inference(self):
        buf=BytesIO();Image.new('RGB',(2,1)).save(buf,format='PNG')
        with TemporaryDirectory() as tmp:
            store=JobStore(Path(tmp),3600,'test');job=store.create('a');store.start(job,'a',1)
            session=SimpleNamespace(id='a',lock=RLock(),segmenter=object())
            def cancel(image,segmenter,diameter,width,edits,check):
                store.cancel(job,'a');check()
            with patch('src.export.pipeline.jobs',store),patch('src.export.pipeline.prediction.predict',side_effect=cancel):
                from fastapi import HTTPException
                with self.assertRaises(HTTPException):
                    append_archive_batch(job,None,[('a',BytesIO(buf.getvalue()))],session)
            self.assertEqual(store.get(job,'a')['status'],'canceled')
            self.assertFalse(Path(store.temp_path(job)).exists())

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
                segmenter=object(),
            )

            with (
                patch("src.export.pipeline.jobs", store),
                patch(
                    "src.export.pipeline.prediction.predict",
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
