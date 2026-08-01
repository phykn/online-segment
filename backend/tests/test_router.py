import unittest

from app.api.router import health_check
from app.main import app


class RouterTests(unittest.TestCase):
    def test_health(self) -> None:
        self.assertEqual(health_check(), {"status": "ok"})

    def test_api_paths(self) -> None:
        paths = set(app.openapi()["paths"])

        self.assertEqual(
            paths,
            {
                "/api/apply",
                "/api/export",
                "/api/export/jobs",
                "/api/export/jobs/{job_id}",
                "/api/export/jobs/{job_id}/file",
                "/api/health",
                "/api/predict",
                "/api/refine",
            },
        )

    def test_old_apply_path_is_removed(self) -> None:
        paths = set(app.openapi()["paths"])

        self.assertNotIn("/api/training-data", paths)


if __name__ == "__main__":
    unittest.main()
