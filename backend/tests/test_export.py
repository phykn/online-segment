import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

import numpy as np
from PIL import Image

from app.export.files import append_archive_batch, make_mask_archive, make_png
from app.export.jobs import JobStore


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

    def test_archive_is_built_one_image_at_a_time(self) -> None:
        source = BytesIO()
        Image.new("RGB", (2, 1), "white").save(source, format="PNG")
        image_bytes = source.getvalue()

        with TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp), max_age=3600, prefix="test")
            job_id = store.create("session-a")
            store.start(job_id, "session-a", 2)
            session = SimpleNamespace(
                id="session-a",
                lock=RLock(),
                segmenter=SimpleNamespace(load=Mock(return_value=object())),
                refiner=object(),
            )

            with (
                patch("app.export.files.jobs", store),
                patch(
                    "app.export.files.actions.predict",
                    return_value=np.zeros((1, 2), dtype=np.int8),
                ),
            ):
                append_archive_batch(
                    job_id,
                    2,
                    [
                        ("same.png", BytesIO(image_bytes)),
                        ("same.png", BytesIO(image_bytes)),
                    ],
                    [None, None],
                    session,
                )

            self.assertEqual(store.get(job_id, session.id)["status"], "ready")
            with ZipFile(store.path(job_id, session.id)) as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["same_mask.png", "same_mask_2.png"],
                )
            self.assertEqual(session.segmenter.load.call_count, 1)


if __name__ == "__main__":
    unittest.main()
