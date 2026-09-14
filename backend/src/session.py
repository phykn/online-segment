from contextlib import contextmanager
from threading import Lock, RLock
from time import monotonic
from typing import Iterator
from uuid import uuid4

from fastapi import HTTPException, status

from src.config import config
from src.segment.model import Segmenter


class ModelSession:
    def __init__(self, session_id: str):
        self.id = session_id
        self.segmenter = Segmenter()
        self.lock = RLock()
        self.touched = monotonic()
        self.active = 0

    def close(self) -> None:
        self.segmenter.clear()

class SessionStore:
    def __init__(self, max_age: int):
        self.max_age = max_age
        self.lock = Lock()
        self._sessions: dict[str, ModelSession] = {}

    def create(self) -> ModelSession:
        with self.lock:
            self._clean()
            session_id = uuid4().hex
            session = ModelSession(session_id)
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


sessions = SessionStore(config.session.max_age)
