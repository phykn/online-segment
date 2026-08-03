import unittest

from app.api.router import create_session, health_check, read_session
from app.api.schema import RefineRequest
from app.main import app
from app.session import sessions


class RouterTests(unittest.TestCase):
    def test_health(self) -> None:
        self.assertEqual(health_check(), {"status": "ok"})

    def test_session_is_created_and_resolved(self) -> None:
        created = create_session()
        dependency = read_session(created.id)
        try:
            resolved = next(dependency)
            self.assertEqual(resolved.id, created.id)
            self.assertEqual(len(created.id), 32)
        finally:
            dependency.close()
            sessions.close()

    def test_api_paths(self) -> None:
        paths = set(app.openapi()["paths"])

        self.assertEqual(
            paths,
            {
                "/api/apply",
                "/api/export",
                "/api/export/archive",
                "/api/export/jobs",
                "/api/export/jobs/{job_id}",
                "/api/export/jobs/{job_id}/file",
                "/api/health",
                "/api/predict",
                "/api/refine",
                "/api/sessions",
            },
        )

    def test_old_apply_path_is_removed(self) -> None:
        paths = set(app.openapi()["paths"])

        self.assertNotIn("/api/training-data", paths)

    def test_refine_accepts_unlabeled_images_without_a_target(self) -> None:
        payload = RefineRequest.model_validate(
            {"images": [{"image": "encoded", "mask": None}]}
        )

        self.assertIsNone(payload.images[0].mask)
        self.assertNotIn("target", payload.model_dump())


if __name__ == "__main__":
    unittest.main()
