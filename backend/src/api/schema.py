from typing import Annotated

from pydantic import BaseModel, Field
from src.config import CLASSES

LabelValue = Annotated[int, Field(ge=-1, lt=CLASSES)]


class SessionResponse(BaseModel):
    id: str


class Mask(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    runs: list[tuple[LabelValue, int]]


class TrainingImage(BaseModel):
    image: str = Field(min_length=1)
    edits: Mask


class PredRequest(BaseModel):
    image: str = Field(min_length=1)
    width: int | None = Field(default=None, gt=0)
    edits: Mask | None = None
    training: list[TrainingImage] | None = None


class PredResponse(BaseModel):
    mask: Mask
    uncertain: Mask
    summary: dict


class ExportJobRequest(BaseModel):
    total: int = Field(gt=0)
