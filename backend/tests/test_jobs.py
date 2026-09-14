import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from src.export.jobs import JobStore


class JobStoreTests(unittest.TestCase):
    def test_job_lifecycle_and_file_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(root, max_age=3600, prefix="test")
            owner = "session-a"
            job_id = store.create(owner)

            self.assertEqual(store.get(job_id, owner)["status"], "waiting")
            self.assertEqual(Path(store.temp_path(job_id)).parent, root)

            store.start(job_id, owner, 2)
            self.assertEqual(store.advance(job_id, owner), (1, 2))
            self.assertEqual(
                store.get(job_id, owner),
                {"status": "running", "done": 1, "total": 2, "error": ""},
            )

            path = root / "result.zip"
            path.touch()
            store.finish(job_id, owner, str(path))
            self.assertEqual(store.path(job_id, owner), str(path))
            with self.assertRaises(HTTPException) as finished:
                store.advance(job_id, owner)
            self.assertEqual(finished.exception.status_code, 409)

            with self.assertRaises(HTTPException):
                store.get(job_id, "session-b")

            store.remove(job_id, owner)
            self.assertFalse(path.exists())
            with self.assertRaises(HTTPException) as caught:
                store.get(job_id, owner)

        self.assertEqual(caught.exception.status_code, 404)


    def test_cancel_marks_job_and_ignores_late_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp), max_age=3600, prefix="test")
            owner = "session-a"
            job_id = store.create(owner)
            store.start(job_id, owner, 2)
            path = Path(store.temp_path(job_id))
            path.touch()

            store.cancel(job_id, owner)

            self.assertFalse(path.exists())
            self.assertEqual(
                store.get(job_id, owner),
                {
                    "status": "canceled",
                    "done": 0,
                    "total": 2,
                    "error": "export canceled",
                },
            )
            store.fail(job_id, owner, "late worker failure")
            self.assertEqual(store.get(job_id, owner)["status"], "canceled")


if __name__ == "__main__":
    unittest.main()
