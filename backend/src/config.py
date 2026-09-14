from pathlib import Path
from typing import Annotated, Literal
import yaml
from pydantic import BaseModel, Field

ColorChannel = Annotated[int, Field(ge=0, le=255)]

class ServerConfig(BaseModel):
    title: str
    origins: list[str]

class SessionConfig(BaseModel):
    max_age: int = Field(gt=0)

class CellposeConfig(BaseModel):
    checkpoint: str
    device: Literal['auto', 'cpu', 'cuda'] = 'auto'
    threads: int = Field(default=6, gt=0)
    tile_size: int = Field(default=384, ge=32, multiple_of=16)
    overlap: float = Field(default=.1, ge=.05, le=.5)
    batch_size: int = Field(default=2, gt=0)
    max_pixels: int = Field(default=16_777_216, gt=0)
    flow_threshold: float = Field(default=.4, ge=0, allow_inf_nan=False)
    cellprob_threshold: float = Field(default=0, allow_inf_nan=False)
    cache_mb: int = Field(default=128, gt=0)
    min_area: int = Field(default=8, gt=0)

class ExportConfig(BaseModel):
    max_age: int = Field(gt=0)
    temp_prefix: str
    colors: list[tuple[ColorChannel, ColorChannel, ColorChannel]] = Field(min_length=4, max_length=4)
    png_compress_level: int = Field(default=1, ge=0, le=9)

class FeatureConfig(BaseModel):
    kind: Literal['image', 'encoder', 'hybrid'] = 'image'
    components: Literal[32, 64] = 32
    cache_mb: int = Field(default=256, gt=0)
    cellpose: Literal['none', 'foreground', 'statistics'] = 'statistics'

class CellposeParameters(BaseModel):
    diameter: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    flow_threshold: float = Field(default=.4, ge=0, allow_inf_nan=False)
    cellprob_threshold: float = Field(default=0, allow_inf_nan=False)
    min_area: int = Field(default=8, ge=1)

    @classmethod
    def defaults(cls):
        return cls(flow_threshold=config.cellpose.flow_threshold,
                   cellprob_threshold=config.cellpose.cellprob_threshold, min_area=config.cellpose.min_area)

class Config(BaseModel):
    server: ServerConfig
    session: SessionConfig
    cellpose: CellposeConfig
    feature: FeatureConfig = Field(default_factory=FeatureConfig)
    export: ExportConfig

path = Path(__file__).parents[1] / 'config.yaml'
config = Config.model_validate(yaml.safe_load(path.read_text(encoding='utf-8')))
