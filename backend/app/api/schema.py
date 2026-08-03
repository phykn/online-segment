from typing import Literal

from pydantic import BaseModel, Field


LabelValue = Literal[-1, 0, 1, 2, 3]


class SessionResponse(BaseModel):
    id: str


class Mask(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    runs: list[tuple[LabelValue, int]]


class TrainItem(BaseModel):
    image: str = Field(min_length=1)
    mask: Mask


class RefineItem(BaseModel):
    image: str = Field(min_length=1)
    mask: Mask | None = None


class ApplyRequest(BaseModel):
    images: list[TrainItem] = Field(min_length=1)


class PredRequest(BaseModel):
    image: str = Field(min_length=1)
    labels: Mask | None = None


class PredResponse(BaseModel):
    mask: Mask
    uncertain: Mask


class RefineRequest(BaseModel):
    images: list[RefineItem] = Field(min_length=1)


class ExportRequest(BaseModel):
    mask: Mask
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ExportFile(BaseModel):
    name: str = Field(min_length=1)
    mask: Mask


class ExportArchiveRequest(BaseModel):
    files: list[ExportFile] = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ExportJobRequest(BaseModel):
    total: int = Field(gt=0)
