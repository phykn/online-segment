from fastapi import APIRouter, status

from app.api.dependencies import SessionDep
from app.api.schema import ApplyRequest, Mask, PredRequest, PredResponse
from app.data.image import read as read_image
from app.data.mask import encode
from app.segment import prediction, training


router = APIRouter(tags=["model"])


@router.post("/apply", status_code=status.HTTP_204_NO_CONTENT)
def apply_model(payload: ApplyRequest, session: SessionDep) -> None:
    with session.lock:
        training.apply(payload.images, session.segmenter)


@router.post("/predict", response_model=PredResponse)
def predict(payload: PredRequest, session: SessionDep) -> PredResponse:
    image = read_image(payload.image)
    with session.lock:
        labels, uncertain = prediction.infer(image, session.segmenter)
    return PredResponse(
        mask=Mask.model_validate(encode(labels), from_attributes=True),
        uncertain=Mask.model_validate(encode(uncertain), from_attributes=True),
    )
