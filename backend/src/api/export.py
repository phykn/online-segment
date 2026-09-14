from fastapi import APIRouter, File, Form, Response, UploadFile, status, HTTPException
from pydantic import TypeAdapter, ValidationError
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from src.api.dependencies import SessionDep
from src.api.schema import ExportArchiveRequest, ExportJobRequest, ExportRequest, Mask
from src.data.mask import decode
from src.export import archive, pipeline
from src.export.jobs import jobs


router = APIRouter(prefix="/export", tags=["export"])


@router.post("")
def export_mask(payload: ExportRequest) -> Response:
    mask = decode(payload.mask)
    png = archive.make_png(mask, payload.width, payload.height)
    return Response(content=png, media_type="image/png")


@router.post("/archive")
def export_archive(payload: ExportArchiveRequest) -> Response:
    files = [(item.name, decode(item.mask)) for item in payload.files]
    content = archive.make_mask_archive(
        files,
        payload.width,
        payload.height,
    )
    return Response(content=content, media_type="application/zip")


@router.post("/jobs")
def create_job(payload: ExportJobRequest, session: SessionDep) -> dict[str, str]:
    job_id = jobs.create(session.id)
    jobs.start(job_id, session.id, payload.total)
    return {"id": job_id}


@router.post(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def run_job(
    job_id: str,
    session: SessionDep,
    width: int | None = Form(default=None, gt=0),
    files: list[UploadFile] = File(min_length=1),
    diameter: float | None = Form(default=None, gt=0, allow_inf_nan=False),
    edits: str | None = Form(default=None),
) -> None:
    corrections = None
    if edits is not None:
        try:
            corrections = TypeAdapter(list[Mask | None]).validate_json(edits)
        except ValidationError as error:
            raise HTTPException(422, 'invalid edit masks.') from error
        if len(corrections) != len(files):
            raise HTTPException(422, 'edit masks must match uploaded files.')
    pipeline.append_archive_batch(
        job_id,
        width,
        [(file.filename or "image", file.file) for file in files],
        session,
        diameter,
        corrections,
    )


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_job(job_id: str, session: SessionDep) -> None:
    jobs.cancel(job_id, session.id)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, session: SessionDep) -> dict:
    return jobs.get(job_id, session.id)


@router.get("/jobs/{job_id}/file")
def get_file(job_id: str, session: SessionDep) -> FileResponse:
    return FileResponse(
        jobs.path(job_id, session.id),
        media_type="application/zip",
        filename="masks.zip",
        background=BackgroundTask(jobs.remove, job_id, session.id),
    )
