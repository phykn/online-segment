from fastapi import APIRouter, File, Form, Response, UploadFile, status
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app import actions
from app.api.schema import (
    ApplyRequest,
    ExportRequest,
    PredRequest,
    PredResponse,
    RefineRequest,
)
from app.data.image import read as read_image
from app.data.mask import decode, encode
from app.export import files as export_files
from app.export.jobs import jobs
from app.refine import train as refine


router = APIRouter(prefix="/api")


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/apply", status_code=status.HTTP_204_NO_CONTENT, tags=["model"])
def apply_model(payload: ApplyRequest) -> None:
    actions.apply(payload.images)


@router.post("/predict", response_model=PredResponse, tags=["model"])
def predict(payload: PredRequest) -> PredResponse:
    image = read_image(payload.image)
    mask, uncertain = actions.infer(image)
    return PredResponse(mask=encode(mask), uncertain=encode(uncertain))


@router.post("/refine", status_code=status.HTTP_204_NO_CONTENT, tags=["model"])
def refine_model(payload: RefineRequest) -> None:
    refine.fit(payload.images, payload.target)


@router.post("/export", tags=["export"])
def export_mask(payload: ExportRequest) -> Response:
    mask = decode(payload.mask)
    png = export_files.make_png(mask, payload.width, payload.height)
    return Response(content=png, media_type="image/png")


@router.post("/export/jobs", tags=["export"])
def create_job() -> dict[str, str]:
    return {"id": jobs.create()}


@router.post(
    "/export/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["export"],
)
def run_job(
    job_id: str,
    width: int = Form(gt=0),
    files: list[UploadFile] = File(min_length=1),
) -> None:
    items = [(file.filename or "image", file.file) for file in files]
    export_files.make_archive(job_id, width, items)


@router.get("/export/jobs/{job_id}", tags=["export"])
def get_job(job_id: str) -> dict:
    return jobs.get(job_id)


@router.get("/export/jobs/{job_id}/file", tags=["export"])
def get_file(job_id: str) -> FileResponse:
    return FileResponse(
        jobs.path(job_id),
        media_type="application/zip",
        filename="masks.zip",
        background=BackgroundTask(jobs.remove, job_id),
    )
