from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class ServerConfig(BaseModel):
    title: str = Field(min_length=1)
    origins: list[str] = Field(min_length=1)


class ModelConfig(BaseModel):
    file: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    n_estimators: int = Field(gt=0)
    max_depth: int = Field(gt=0)
    max_features: int = Field(gt=0)
    min_samples_leaf: int = Field(gt=0)
    class_weight: str = Field(min_length=1)
    max_per_class: int = Field(gt=0)
    edge_ratio: float = Field(ge=0.0, le=1.0)
    edge_quantile: float = Field(ge=0.0, lt=1.0)
    uncertain_threshold: float = Field(gt=0.0, lt=1.0)
    random_state: int
    n_jobs: int


class FeatureConfig(BaseModel):
    base_size: int = Field(gt=0)
    factors: tuple[float, ...] = Field(min_length=1)
    hessian_factors: tuple[float, ...]
    log_factors: tuple[float, ...]
    sigma_min: float = Field(gt=0.0)
    sigma_max: float = Field(gt=0.0)
    percentiles: tuple[float, float]
    cache_mb: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_scales(self):
        values = set(self.factors)
        if not set(self.hessian_factors) <= values:
            raise ValueError("hessian_factors must be included in factors")
        if not set(self.log_factors) <= set(self.hessian_factors):
            raise ValueError("log_factors must be included in hessian_factors")
        if self.sigma_min > self.sigma_max:
            raise ValueError("sigma_min must not exceed sigma_max")
        if self.percentiles[0] >= self.percentiles[1]:
            raise ValueError("percentiles must be increasing")
        return self


class EdgeConfig(BaseModel):
    radius: float = Field(gt=0.0)
    steps: int = Field(gt=0)
    unary: float = Field(gt=0.0)
    sigma: float = Field(gt=0.0)


class RefineConfig(BaseModel):
    file: str = Field(min_length=1)
    base: int = Field(gt=0)
    dilations: tuple[int, ...] = Field(min_length=1)
    threshold: float = Field(gt=0.0, le=1.0)
    max_total: int = Field(gt=0)
    core_scale: float = Field(gt=0.0)
    pseudo_weight: float = Field(gt=0.0, le=1.0)
    patch: int = Field(gt=0)
    batch: int = Field(gt=0)
    manual_batch: int = Field(gt=0)
    first_steps: int = Field(gt=0)
    next_steps: int = Field(gt=0)
    lr: float = Field(gt=0.0)
    focal_gamma: float = Field(ge=0.0)
    ignore: int

    @model_validator(mode="after")
    def validate_batch(self):
        if self.manual_batch > self.batch:
            raise ValueError("manual_batch must not exceed batch")
        return self


class ExportConfig(BaseModel):
    max_age: int = Field(gt=0)
    temp_prefix: str = Field(min_length=1)
    colors: list[tuple[int, int, int]] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_colors(self):
        if any(value < 0 or value > 255 for color in self.colors for value in color):
            raise ValueError("color values must be between 0 and 255")
        return self


class Config(BaseModel):
    server: ServerConfig
    model: ModelConfig
    feature: FeatureConfig
    edge: EdgeConfig
    refine: RefineConfig
    export: ExportConfig


path = Path(__file__).with_name("config.yaml")
config = Config.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
