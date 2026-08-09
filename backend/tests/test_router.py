import unittest
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from app.api.dependencies import read_session
from app.api.export import cancel_job
from app.api.model import apply_model, predict
from app.api.router import create_session, health_check
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
                "/api/sessions",
            },
        )

    def test_old_apply_path_is_removed(self) -> None:
        paths = set(app.openapi()["paths"])

        self.assertNotIn("/api/training-data", paths)

    def test_apply_uses_the_session_model(self) -> None:
        session = SimpleNamespace(
            lock=RLock(),
            segmenter=object(),
        )
        payload = SimpleNamespace(images=[object()])

        with patch("app.api.model.training.apply") as apply:
            apply_model(payload, session)

        apply.assert_called_once_with(payload.images, session.segmenter)

    def test_predict_keeps_the_public_mask_schema(self) -> None:
        session = SimpleNamespace(lock=RLock(), segmenter=object())
        payload = SimpleNamespace(image="encoded")
        labels = np.array([[0, 0, 1]], dtype=np.int8)
        uncertain = np.array([[0, 1, 1]], dtype=np.int8)

        with (
            patch("app.api.model.read_image", return_value=object()),
            patch(
                "app.api.model.prediction.infer",
                return_value=(labels, uncertain),
            ),
        ):
            response = predict(payload, session)

        self.assertEqual(response.mask.model_dump(), {
            "width": 3,
            "height": 1,
            "runs": [(0, 2), (1, 1)],
        })
        self.assertEqual(response.uncertain.runs, [(0, 1), (1, 2)])

    def test_cancel_job_uses_session_owner(self) -> None:
        session = SimpleNamespace(id="session-a")

        with patch("app.api.export.jobs.cancel") as cancel:
            cancel_job("job-a", session)

        cancel.assert_called_once_with("job-a", "session-a")


if __name__ == "__main__":
    unittest.main()
