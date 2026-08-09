from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class ServerConfig(BaseModel):
    title: str = Field(min_length=1)
    origins: list[str] = Field(min_length=1)


class SessionConfig(BaseModel):
    max_age: int = Field(gt=0)
    temp_prefix: str = Field(min_length=1)


class ModelConfig(BaseModel):
    file: str = Field(min_length=1)
    n_estimators: int = Field(gt=0)
    max_depth: int = Field(gt=0)
    max_features: int = Field(gt=0)
    min_samples_leaf: int = Field(gt=0)
    class_weight: str = Field(min_length=1)
    max_per_class: int = Field(gt=0)
    balance_floor: int = Field(gt=0)
    edge_ratio: float = Field(ge=0.0, le=1.0)
    edge_quantile: float = Field(ge=0.0, lt=1.0)
    uncertain_threshold: float = Field(gt=0.0, lt=1.0)
    random_state: int
    n_jobs: int

    @model_validator(mode="after")
    def validate_sampling(self):
        if self.balance_floor > self.max_per_class:
            raise ValueError("balance_floor must not exceed max_per_class")
        return self


class FeatureConfig(BaseModel):
    base_size: int = Field(gt=0)
    factors: tuple[float, ...] = Field(min_length=1)
    hessian_factors: tuple[float, ...]
    context_factors: tuple[float, ...] = Field(min_length=1)
    sigma_min: float = Field(gt=0.0)
    sigma_max: float = Field(gt=0.0)
    percentiles: tuple[float, float]
    cache_mb: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_scales(self):
        if any(value <= 0 for value in (*self.factors, *self.context_factors)):
            raise ValueError("feature factors must be positive")
        values = set(self.factors)
        if not set(self.hessian_factors) <= values:
            raise ValueError("hessian_factors must be included in factors")
        if self.sigma_min > self.sigma_max:
            raise ValueError("sigma_min must not exceed sigma_max")
        if self.percentiles[0] >= self.percentiles[1]:
            raise ValueError("percentiles must be increasing")
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


class FeaturePerformanceConfig(BaseModel):
    max_workers: int = Field(gt=0)
    parallel_min_pixels: int = Field(gt=0)


class CudaEarlyExitConfig(BaseModel):
    trees: int = Field(gt=0)
    margin: float = Field(ge=0.0, le=1.0)


class CudaForestPerformanceConfig(BaseModel):
    enabled: bool
    chunk_size: int = Field(gt=0)
    full_chunk_size: int = Field(gt=0)
    early_exit: tuple[CudaEarlyExitConfig, ...] = Field(min_length=1)
    min_exit_rate: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_early_exit(self):
        trees = [stage.trees for stage in self.early_exit]
        if trees != sorted(set(trees)):
            raise ValueError("early-exit tree counts must be increasing")
        return self


class ExportPerformanceConfig(BaseModel):
    gpu_min_pixels: int = Field(gt=0)
    png_compress_level: int = Field(ge=0, le=9)


class PerformanceConfig(BaseModel):
    feature: FeaturePerformanceConfig
    cuda_forest: CudaForestPerformanceConfig
    export: ExportPerformanceConfig


class Config(BaseModel):
    server: ServerConfig
    session: SessionConfig
    model: ModelConfig
    feature: FeatureConfig
    export: ExportConfig
    performance: PerformanceConfig


path = Path(__file__).parents[1] / "config.yaml"
config = Config.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
