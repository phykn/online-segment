from concurrent.futures import ThreadPoolExecutor
from os import cpu_count

import numpy as np
from scipy.ndimage import gaussian_filter, sobel, uniform_filter

from app.config import config as app_config
from app.segment.cache import FeatureCache


perf = app_config.performance.feature
cfg = app_config.feature
cache = FeatureCache(cfg.cache_mb)
CONTEXT_START = (
    1
    + len(cfg.factors) * 2
    + len(cfg.hessian_factors) * 2
)
COUNT = CONTEXT_START + len(cfg.context_factors)


def config() -> dict:
    return cfg.model_dump(mode="json", exclude={"cache_mb"}) | {"count": COUNT}


def sigmas(shape: tuple[int, ...]) -> np.ndarray:
    scale = min(shape[:2]) / cfg.base_size
    values = np.asarray(cfg.factors, dtype=np.float32) * scale
    return np.clip(values, cfg.sigma_min, cfg.sigma_max)


def context_windows(shape: tuple[int, ...]) -> tuple[int, ...]:
    scale = min(shape[:2]) / cfg.base_size
    max_radius = max(1, min(shape[:2]) // 2)
    radii = np.rint(np.asarray(cfg.context_factors) * scale).astype(int)
    radii = np.clip(radii, 1, max_radius)
    return tuple(int(radius * 2 + 1) for radius in radii)


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


def _scale_features(
    gray: np.ndarray,
    factor: float,
    sigma: float,
) -> tuple[np.ndarray, ...]:
    smooth = gaussian_filter(gray, sigma, mode="reflect")
    edge_x = sobel(smooth, axis=1, mode="reflect")
    edge_y = sobel(smooth, axis=0, mode="reflect")
    values = [smooth, np.hypot(edge_x, edge_y)]

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
    return tuple(values)


def _context_features(
    gray: np.ndarray,
    windows: tuple[int, ...],
) -> tuple[np.ndarray, ...]:
    return tuple(
        gray - uniform_filter(gray, size=window, mode="reflect")
        for window in windows
    )


def _taskgraph_features(
    gray: np.ndarray,
    scales: tuple[tuple[float, np.float32], ...],
    windows: tuple[int, ...],
) -> list[np.ndarray]:
    task_count = len(scales) * 4 + len(windows)
    workers = min(perf.max_workers, cpu_count() or 1, task_count)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        scale_jobs = []
        for factor, sigma in scales:
            smooth = pool.submit(
                gaussian_filter, gray, sigma, mode="reflect"
            )
            hessian = None
            if factor in cfg.hessian_factors:
                hessian = tuple(
                    pool.submit(
                        gaussian_filter,
                        gray,
                        sigma,
                        order=order,
                        mode="reflect",
                    )
                    for order in ((0, 2), (1, 1), (2, 0))
                )
            scale_jobs.append((smooth, hessian))

        context_jobs = [
            pool.submit(uniform_filter, gray, size=window, mode="reflect")
            for window in windows
        ]

        values = [gray]
        for smooth_job, hessian_jobs in scale_jobs:
            smooth = smooth_job.result()
            edge_x = pool.submit(
                sobel, smooth, axis=1, mode="reflect"
            )
            edge_y = pool.submit(
                sobel, smooth, axis=0, mode="reflect"
            )
            values.extend((smooth, np.hypot(edge_x.result(), edge_y.result())))

            if hessian_jobs is not None:
                hxx, hxy, hyy = (job.result() for job in hessian_jobs)
                delta = np.sqrt((hxx - hyy) ** 2 + 4 * hxy**2)
                values.extend(
                    (
                        0.5 * (hxx + hyy + delta),
                        0.5 * (hxx + hyy - delta),
                    )
                )

        values.extend(gray - job.result() for job in context_jobs)
        return values


def make(image: np.ndarray) -> np.ndarray:
    gray = normalize(image)
    scales = tuple(zip(cfg.factors, sigmas(image.shape), strict=True))
    windows = context_windows(image.shape)
    values = [gray]
    if gray.size < perf.parallel_min_pixels:
        for factor, sigma in scales:
            values.extend(_scale_features(gray, factor, sigma))
        values.extend(_context_features(gray, windows))
    else:
        values = _taskgraph_features(gray, scales, windows)

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
