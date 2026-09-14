from fastapi import APIRouter

from src.api import export, image, model
from src.api.schema import SessionResponse
from src.session import sessions


router = APIRouter(prefix="/api")


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/sessions", response_model=SessionResponse, tags=["session"])
def create_session() -> SessionResponse:
    return SessionResponse(id=sessions.create().id)


router.include_router(model.router)
router.include_router(export.router)
router.include_router(image.router)
