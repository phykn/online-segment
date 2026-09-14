from fastapi import APIRouter
from src.api.dependencies import SessionDep
from src.api.schema import Mask, PredRequest, PredResponse, ProposalRequest, InstanceMask
from src.data.image import read as read_image, resize_width
from src.data.mask import decode, encode, resize
from src.segment import prediction

router = APIRouter(tags=['model'])

@router.get('/predict/status')
def progress(session: SessionDep) -> dict:
    return dict(session.segmenter.progress)

@router.post('/label-proposals', response_model=InstanceMask)
def proposals(payload: ProposalRequest, session: SessionDep) -> InstanceMask:
    image = resize_width(read_image(payload.image), payload.width)
    with session.lock:
        session.segmenter.configure(payload.width, payload.cellpose)
        try:
            masks = session.segmenter.propose(image)
            return InstanceMask.model_validate(encode(masks), from_attributes=True)
        except Exception:
            session.segmenter.report(stage='error', done=0, total=0)
            raise

@router.post('/predict', response_model=PredResponse)
def predict(payload: PredRequest, session: SessionDep) -> PredResponse:
    image = read_image(payload.image)
    original_width = image.shape[1]
    image = resize_width(image, payload.width)
    edits = decode(payload.edits) if payload.edits is not None else None
    with session.lock:
        try:
            session.segmenter.configure(payload.width, payload.cellpose)
            session.segmenter.validate(image)
            if payload.training is not None:
                records = {}
                for item in payload.training:
                    source = read_image(item.image)
                    resized = resize_width(source, payload.width)
                    session.segmenter.validate(resized)
                    mask = resize(decode(item.edits), resized.shape[1], resized.shape[0])
                    scale = source.shape[1]/resized.shape[1]
                    records[(session.segmenter.key(resized), scale)] = (resized, mask, scale)
                session.segmenter.fit(list(records.values()))
            labels, uncertain, summary, particles = prediction.infer(
                image, session.segmenter, payload.diameter, original_width, edits,
                train=payload.training is None)
        except Exception:
            session.segmenter.report(stage='error', done=0, total=0)
            raise
    return PredResponse(
        mask=Mask.model_validate(encode(labels), from_attributes=True),
        uncertain=Mask.model_validate(encode(uncertain), from_attributes=True),
        summary=summary, particles=particles)
