from collections.abc import Iterator
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Response,
    UploadFile,
    status,
)
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app import actions
from app.api.schema import (
    ApplyRequest,
    ExportArchiveRequest,
    ExportJobRequest,
    ExportRequest,
    PredRequest,
    PredResponse,
    SessionResponse,
)
from app.data.image import read as read_image
from app.data.mask import decode, encode
from app.export import files as export_files
from app.export.jobs import jobs
from app.session import ModelSession, sessions


router = APIRouter(prefix="/api")


def read_session(
    session_id: Annotated[str, Header(alias="X-Session-ID")],
) -> Iterator[ModelSession]:
    with sessions.acquire(session_id) as session:
        yield session


SessionDep = Annotated[ModelSession, Depends(read_session)]


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/sessions", response_model=SessionResponse, tags=["session"])
def create_session() -> SessionResponse:
    return SessionResponse(id=sessions.create().id)


@router.post("/apply", status_code=status.HTTP_204_NO_CONTENT, tags=["model"])
def apply_model(payload: ApplyRequest, session: SessionDep) -> None:
    with session.lock:
        actions.apply(payload.images, session.segmenter)


@router.post("/predict", response_model=PredResponse, tags=["model"])
def predict(payload: PredRequest, session: SessionDep) -> PredResponse:
    image = read_image(payload.image)
    with session.lock:
        mask, uncertain = actions.infer(image, session.segmenter)
    return PredResponse(mask=encode(mask), uncertain=encode(uncertain))


@router.post("/export", tags=["export"])
def export_mask(payload: ExportRequest) -> Response:
    mask = decode(payload.mask)
    png = export_files.make_png(mask, payload.width, payload.height)
    return Response(content=png, media_type="image/png")


@router.post("/export/archive", tags=["export"])
def export_archive(payload: ExportArchiveRequest) -> Response:
    files = [(item.name, decode(item.mask)) for item in payload.files]
    archive = export_files.make_mask_archive(
        files,
        payload.width,
        payload.height,
    )
    return Response(content=archive, media_type="application/zip")


@router.post("/export/jobs", tags=["export"])
def create_job(payload: ExportJobRequest, session: SessionDep) -> dict[str, str]:
    job_id = jobs.create(session.id)
    jobs.start(job_id, session.id, payload.total)
    return {"id": job_id}


@router.post(
    "/export/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["export"],
)
def run_job(
    job_id: str,
    session: SessionDep,
    width: int | None = Form(default=None, gt=0),
    files: list[UploadFile] = File(min_length=1),
) -> None:
    export_files.append_archive_batch(
        job_id,
        width,
        [(file.filename or "image", file.file) for file in files],
        session,
    )


@router.delete(
    "/export/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["export"],
)
def cancel_job(job_id: str, session: SessionDep) -> None:
    jobs.cancel(job_id, session.id)


@router.get("/export/jobs/{job_id}", tags=["export"])
def get_job(job_id: str, session: SessionDep) -> dict:
    return jobs.get(job_id, session.id)


@router.get("/export/jobs/{job_id}/file", tags=["export"])
def get_file(job_id: str, session: SessionDep) -> FileResponse:
    return FileResponse(
        jobs.path(job_id, session.id),
        media_type="application/zip",
        filename="masks.zip",
        background=BackgroundTask(jobs.remove, job_id, session.id),
    )
