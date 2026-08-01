import numpy as np


def quotas(counts: list[int], total: int) -> list[int]:
    values = np.asarray(counts, dtype=np.int64)
    result = np.zeros(values.size, dtype=np.int64)
    remaining = min(total, int(values.sum()))

    while remaining > 0:
        active = np.flatnonzero(result < values)
        share = max(1, (remaining + active.size - 1) // active.size)
        for idx in active:
            added = min(share, int(values[idx] - result[idx]), remaining)
            result[idx] += added
            remaining -= added
            if remaining == 0:
                break

    return result.tolist()


def spatial(mask: np.ndarray, limit: int) -> np.ndarray:
    flat = np.flatnonzero(mask)
    if flat.size <= limit:
        return flat

    height, width = mask.shape
    y, x = np.unravel_index(flat, mask.shape)
    side = max(1, int(np.ceil(np.sqrt(limit))))
    cells = (y * side // height) * side + x * side // width
    order = np.argsort(cells, kind="stable")
    sorted_cells = cells[order]
    starts = np.flatnonzero(
        np.r_[True, sorted_cells[1:] != sorted_cells[:-1]]
    )
    ends = np.r_[starts[1:], order.size]
    centers = order[starts + (ends - starts) // 2]

    if centers.size >= limit:
        return flat[centers[_even(centers.size, limit)]]

    chosen = flat[centers]
    rest = np.setdiff1d(flat, chosen, assume_unique=True)
    needed = limit - chosen.size
    return np.concatenate((chosen, rest[_even(rest.size, needed)]))


def guided(
    mask: np.ndarray,
    score: np.ndarray,
    limit: int,
    ratio: float,
    quantile: float,
) -> np.ndarray:
    flat = np.flatnonzero(mask)
    if flat.size <= limit or ratio <= 0.0:
        return spatial(mask, limit)

    values = score.ravel()[flat]
    if np.max(values) <= np.min(values):
        return spatial(mask, limit)

    cutoff = np.quantile(values, quantile)
    edge_mask = mask & (
        (score > cutoff) if cutoff <= np.min(values) else (score >= cutoff)
    )
    edge_limit = min(max(1, round(limit * ratio)), int(np.sum(edge_mask)))
    chosen = spatial(edge_mask, edge_limit)
    rest_mask = mask.copy()
    rest_mask.ravel()[chosen] = False
    rest = spatial(rest_mask, limit - chosen.size)
    return np.concatenate((chosen, rest))


def _even(size: int, count: int) -> np.ndarray:
    return ((np.arange(count) + 0.5) * size / count).astype(np.int64)
