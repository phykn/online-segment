import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.export.jobs import JobStore


class JobStoreTests(unittest.TestCase):
    def test_job_lifecycle_and_file_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(root, max_age=3600, prefix="test")
            job_id = store.create()

            self.assertEqual(store.get(job_id)["status"], "waiting")
            self.assertEqual(Path(store.temp_path(job_id)).parent, root)

            store.start(job_id, 2)
            store.update(job_id, 1)
            self.assertEqual(
                store.get(job_id),
                {"status": "running", "done": 1, "total": 2, "error": ""},
            )

            path = root / "result.zip"
            path.touch()
            store.finish(job_id, str(path))
            self.assertEqual(store.path(job_id), str(path))

            store.remove(job_id)
            self.assertFalse(path.exists())
            with self.assertRaises(HTTPException) as caught:
                store.get(job_id)

        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
