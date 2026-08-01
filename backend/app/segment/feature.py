import numpy as np
from scipy.ndimage import gaussian_filter, sobel

from app.config import config as app_config
from app.segment.cache import FeatureCache


cfg = app_config.feature
cache = FeatureCache(cfg.cache_mb)
COUNT = (
    1
    + len(cfg.factors) * 2
    + len(cfg.hessian_factors) * 2
    + len(cfg.log_factors)
)


def config() -> dict:
    return cfg.model_dump(mode="json", exclude={"cache_mb"}) | {"count": COUNT}


def sigmas(shape: tuple[int, ...]) -> np.ndarray:
    scale = min(shape[:2]) / cfg.base_size
    values = np.asarray(cfg.factors, dtype=np.float32) * scale
    return np.clip(values, cfg.sigma_min, cfg.sigma_max)


def normalize(image: np.ndarray) -> np.ndarray:
    rgb = image.astype(np.float32) / 255.0
    gray = (
        rgb[..., 0] * 0.2126
        + rgb[..., 1] * 0.7152
        + rgb[..., 2] * 0.0722
    )
    low, high = np.percentile(gray, cfg.percentiles)
    if high <= low:
        return np.zeros_like(gray)
    return np.clip((gray - low) / (high - low), 0.0, 1.0)


def make(image: np.ndarray) -> np.ndarray:
    gray = normalize(image)
    values = [gray]
    logs = {}

    for factor, sigma in zip(cfg.factors, sigmas(image.shape)):
        smooth = gaussian_filter(gray, sigma, mode="reflect")
        edge_x = sobel(smooth, axis=1, mode="reflect")
        edge_y = sobel(smooth, axis=0, mode="reflect")
        edge = np.hypot(edge_x, edge_y)
        values.extend((smooth, edge))

        if factor in cfg.hessian_factors:
            hxx = gaussian_filter(gray, sigma, order=(0, 2), mode="reflect")
            hxy = gaussian_filter(gray, sigma, order=(1, 1), mode="reflect")
            hyy = gaussian_filter(gray, sigma, order=(2, 0), mode="reflect")
            delta = np.sqrt((hxx - hyy) ** 2 + 4 * hxy**2)
            values.extend(
                (
                    0.5 * (hxx + hyy + delta),
                    0.5 * (hxx + hyy - delta),
                )
            )
            if factor in cfg.log_factors:
                logs[factor] = (sigma**2) * (hxx + hyy)

    values.extend(logs[factor] for factor in cfg.log_factors)

    return np.stack(values, axis=-1).astype(np.float32, copy=False)


def cached(image: np.ndarray) -> np.ndarray:
    return cache.get(image, make)


def edge_score(stack: np.ndarray) -> np.ndarray:
    indices = []
    offset = 1
    for factor in cfg.factors:
        indices.append(offset + 1)
        offset += 2
        if factor in cfg.hessian_factors:
            offset += 2
    return np.max(stack[..., indices], axis=2)
