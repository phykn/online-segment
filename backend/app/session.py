from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock, RLock
from time import monotonic
from typing import Iterator
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import config
from app.refine.model import Refiner
from app.segment.model import Segmenter


class ModelSession:
    def __init__(self, session_id: str, prefix: str):
        self.id = session_id
        self.tmp = TemporaryDirectory(prefix=f"{prefix}-")
        root = Path(self.tmp.name)
        self.segmenter = Segmenter(root / config.model.file)
        self.refiner = Refiner(root / config.refine.file)
        self.lock = RLock()
        self.touched = monotonic()
        self.active = 0

    def close(self) -> None:
        self.tmp.cleanup()


class SessionStore:
    def __init__(self, max_age: int, prefix: str):
        self.max_age = max_age
        self.prefix = prefix
        self.lock = Lock()
        self._sessions: dict[str, ModelSession] = {}

    def create(self) -> ModelSession:
        with self.lock:
            self._clean()
            session_id = uuid4().hex
            session = ModelSession(session_id, self.prefix)
            self._sessions[session_id] = session
            return session

    @contextmanager
    def acquire(self, session_id: str) -> Iterator[ModelSession]:
        with self.lock:
            self._clean()
            session = self._sessions.get(session_id)
            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="session was not found.",
                )
            session.active += 1
            session.touched = monotonic()

        try:
            yield session
        finally:
            with self.lock:
                session.active -= 1
                session.touched = monotonic()

    def close(self) -> None:
        with self.lock:
            values = list(self._sessions.values())
            self._sessions.clear()
        for session in values:
            session.close()

    def _clean(self) -> None:
        now = monotonic()
        expired = [
            key
            for key, session in self._sessions.items()
            if session.active == 0 and now - session.touched > self.max_age
        ]
        for key in expired:
            self._sessions.pop(key).close()


sessions = SessionStore(config.session.max_age, config.session.temp_prefix)
