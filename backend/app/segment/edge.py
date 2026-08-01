import numpy as np
from scipy.ndimage import binary_dilation

from app.config import config
from app.segment import feature


cfg = config.edge


def _boundary(labels: np.ndarray) -> np.ndarray:
    edge = np.zeros(labels.shape, dtype=bool)
    diff = labels[1:, :] != labels[:-1, :]
    edge[1:, :] |= diff
    edge[:-1, :] |= diff
    diff = labels[:, 1:] != labels[:, :-1]
    edge[:, 1:] |= diff
    edge[:, :-1] |= diff
    return edge


def _valid(shape: tuple[int, int], dy: int, dx: int) -> np.ndarray:
    valid = np.ones(shape, dtype=bool)
    if dy > 0:
        valid[:dy, :] = False
    elif dy < 0:
        valid[dy:, :] = False
    if dx > 0:
        valid[:, :dx] = False
    elif dx < 0:
        valid[:, dx:] = False
    return valid


def adjust(image: np.ndarray, probs: np.ndarray) -> np.ndarray:
    labels = np.argmax(probs, axis=2)
    boundary = _boundary(labels)
    if not np.any(boundary):
        return probs

    radius = max(
        1,
        round(min(labels.shape) / config.feature.base_size * cfg.radius),
    )
    band = binary_dilation(boundary, iterations=radius)
    gray = feature.normalize(image)

    base = probs.astype(np.float32, copy=False)
    current = base.copy()
    for _ in range(cfg.steps):
        total = base * cfg.unary
        weight = np.full(labels.shape, cfg.unary, dtype=np.float32)

        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nearby = np.roll(current, (dy, dx), axis=(0, 1))
            nearby_gray = np.roll(gray, (dy, dx), axis=(0, 1))
            diff = (gray - nearby_gray) / cfg.sigma
            value = np.exp(-(diff**2))
            value *= _valid(labels.shape, dy, dx)
            total += nearby * value[..., None]
            weight += value

        updated = total / weight[..., None]
        current[band] = updated[band]

    return current
