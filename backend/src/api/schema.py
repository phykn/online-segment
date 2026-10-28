from typing import Annotated, Literal

from pydantic import BaseModel, Field
from src.config import CellposeParameters

LabelValue = Literal[-1, 0, 1, 2, 3]


class SessionResponse(BaseModel):
    id: str


class Mask(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    runs: list[tuple[LabelValue, int]]


class TrainingImage(BaseModel):
    image: str = Field(min_length=1)
    edits: Mask


class ProposalRequest(BaseModel):
    image: str = Field(min_length=1)
    width: int | None = Field(default=None, gt=0)
    cellpose: CellposeParameters | None = None


class InstanceMask(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    runs: list[tuple[Annotated[int, Field(ge=0)], Annotated[int, Field(gt=0)]]]


class PredRequest(BaseModel):
    image: str = Field(min_length=1)
    width: int | None = Field(default=None, gt=0)
    cellpose: CellposeParameters | None = None
    diameter: float | None = Field(default=None, gt=0, allow_inf_nan=False, json_schema_extra={'deprecated': True},
                                   description='Accepted for compatibility; RF does not use a size threshold.')
    edits: Mask | None = None
    training: list[TrainingImage] | None = None


class PredResponse(BaseModel):
    mask: Mask
    uncertain: Mask
    summary: dict
    particles: list[dict]


class ExportJobRequest(BaseModel):
    total: int = Field(gt=0)
