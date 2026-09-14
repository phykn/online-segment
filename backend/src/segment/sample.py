import numpy as np


def quotas(counts, total):
    values = np.asarray(counts, dtype=np.int64)
    result = np.zeros(len(values), dtype=int)
    remaining = min(total, int(values.sum()))
    while remaining:
        active = np.flatnonzero(result < values)
        share = max(1, remaining // len(active))
        for i in active:
            added = min(share, int(values[i]-result[i]), remaining)
            result[i] += added
            remaining -= added
    return result


def spatial(mask, limit):
    flat = np.flatnonzero(mask)
    if len(flat) <= limit:
        return flat
    y, x = np.unravel_index(flat, mask.shape)
    side = max(1, int(np.ceil(np.sqrt(limit))))
    cells = y*side//mask.shape[0]*side + x*side//mask.shape[1]
    order = np.argsort(cells, kind='stable')
    starts = np.flatnonzero(np.r_[True, np.diff(cells[order]) != 0])
    ends = np.r_[starts[1:], len(order)]
    centers = flat[order[starts+(ends-starts)//2]]
    if len(centers) >= limit:
        return centers[((np.arange(limit)+.5)*len(centers)/limit).astype(int)]
    rest = np.setdiff1d(flat, centers, assume_unique=True)
    count = limit-len(centers)
    return np.r_[centers, rest[((np.arange(count)+.5)*len(rest)/count).astype(int)]]
