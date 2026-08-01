from pathlib import Path
from tempfile import gettempdir
from threading import Lock
from time import time
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import config


class JobStore:
    def __init__(self, root: Path, max_age: int, prefix: str):
        self.root = root
        self.max_age = max_age
        self.prefix = prefix
        self.lock = Lock()
        self._jobs = {}

    def create(self) -> str:
        with self.lock:
            self._clean()
            job_id = uuid4().hex
            self._jobs[job_id] = {
                "created": time(),
                "status": "waiting",
                "done": 0,
                "total": 0,
                "error": "",
                "path": "",
            }
        return job_id

    def start(self, job_id: str, total: int) -> None:
        with self.lock:
            self._get(job_id).update(status="running", total=total, done=0)

    def update(self, job_id: str, done: int) -> None:
        with self.lock:
            self._get(job_id)["done"] = done

    def finish(self, job_id: str, path: str) -> None:
        with self.lock:
            job = self._get(job_id)
            job.update(status="ready", done=job["total"], path=path)

    def fail(self, job_id: str, message: str) -> None:
        with self.lock:
            self._get(job_id).update(status="error", error=message)

    def get(self, job_id: str) -> dict:
        with self.lock:
            job = self._get(job_id)
            return {key: job[key] for key in ("status", "done", "total", "error")}

    def path(self, job_id: str) -> str:
        with self.lock:
            job = self._get(job_id)
            if job["status"] != "ready" or not job["path"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="export is not ready.",
                )
            return job["path"]

    def remove(self, job_id: str) -> None:
        with self.lock:
            job = self._jobs.pop(job_id, None)
        if job and job["path"]:
            Path(job["path"]).unlink(missing_ok=True)

    def temp_path(self, job_id: str) -> str:
        return str(self.root / f"{self.prefix}-{job_id}.zip")

    def _clean(self) -> None:
        now = time()
        expired = [
            key
            for key, job in self._jobs.items()
            if now - job["created"] > self.max_age
        ]
        for key in expired:
            path = self._jobs.pop(key).get("path")
            if path:
                Path(path).unlink(missing_ok=True)

    def _get(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="export job was not found.",
            )
        return job


jobs = JobStore(
    Path(gettempdir()),
    config.export.max_age,
    config.export.temp_prefix,
)
