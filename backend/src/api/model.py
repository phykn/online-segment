from fastapi import APIRouter
from src.api.dependencies import SessionDep
from src.api.schema import Mask, PredRequest, PredResponse
from src.data.image import read as read_image, resize_width
from src.data.mask import decode, encode, resize
from src.segment import prediction

router = APIRouter(tags=['model'])

@router.get('/predict/status')
def progress(session: SessionDep) -> dict:
    return dict(session.segmenter.progress)

@router.post('/predict', response_model=PredResponse)
def predict(payload: PredRequest, session: SessionDep) -> PredResponse:
    image = read_image(payload.image)
    image = resize_width(image, payload.width)
    edits = decode(payload.edits) if payload.edits is not None else None
    with session.lock:
        try:
            session.segmenter.configure(payload.width)
            session.segmenter.validate(image)
            if payload.training is not None:
                records = {}
                for item in payload.training:
                    source = read_image(item.image)
                    resized = resize_width(source, payload.width)
                    session.segmenter.validate(resized)
                    mask = resize(decode(item.edits), resized.shape[1], resized.shape[0])
                    records[session.segmenter.key(resized)] = (resized, mask)
                session.segmenter.fit(list(records.values()))
            labels, uncertain, summary = prediction.infer(
                image, session.segmenter, edits,
                train=payload.training is None)
        except Exception:
            session.segmenter.report(stage='error', done=0, total=0)
            raise
    return PredResponse(
        mask=Mask.model_validate(encode(labels), from_attributes=True),
        uncertain=Mask.model_validate(encode(uncertain), from_attributes=True),
        summary=summary)
