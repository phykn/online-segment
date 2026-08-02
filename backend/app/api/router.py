from collections.abc import Iterator
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import ValidationError
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app import actions
from app.api.schema import (
    ApplyRequest,
    ExportArchiveRequest,
    ExportRequest,
    Mask,
    PredRequest,
    PredResponse,
    RefineRequest,
    SessionResponse,
)
from app.data.image import read as read_image
from app.data.mask import decode, encode
from app.export import files as export_files
from app.export.jobs import jobs
from app.refine import train as refine
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
        actions.apply(payload.images, session.segmenter, session.refiner)


@router.post("/predict", response_model=PredResponse, tags=["model"])
def predict(payload: PredRequest, session: SessionDep) -> PredResponse:
    image = read_image(payload.image)
    selected = decode(payload.labels) if payload.labels else None
    with session.lock:
        mask, uncertain = actions.infer(
            image,
            session.segmenter,
            session.refiner,
            selected=selected,
        )
    return PredResponse(mask=encode(mask), uncertain=encode(uncertain))


@router.post("/refine", status_code=status.HTTP_204_NO_CONTENT, tags=["model"])
def refine_model(payload: RefineRequest, session: SessionDep) -> None:
    with session.lock:
        refine.fit(
            payload.images,
            payload.target,
            session.segmenter,
            session.refiner,
        )


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
def create_job(session: SessionDep) -> dict[str, str]:
    return {"id": jobs.create(session.id)}


@router.post(
    "/export/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["export"],
)
def run_job(
    job_id: str,
    session: SessionDep,
    width: int = Form(gt=0),
    files: list[UploadFile] = File(min_length=1),
    labels: list[str] | None = Form(default=None),
) -> None:
    items = [(file.filename or "image", file.file) for file in files]
    if labels is not None and len(labels) != len(files):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="file and mask counts differ.",
        )

    try:
        selected = [
            None if value == "null" else decode(Mask.model_validate_json(value))
            for value in labels or ["null"] * len(files)
        ]
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid mask RLE.",
        ) from error

    export_files.make_archive(job_id, width, items, selected, session)


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
