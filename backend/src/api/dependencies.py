from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header

from src.session import ModelSession, sessions


def read_session(
    session_id: Annotated[str, Header(alias="X-Session-ID")],
) -> Iterator[ModelSession]:
    with sessions.acquire(session_id) as session:
        yield session


SessionDep = Annotated[ModelSession, Depends(read_session)]
