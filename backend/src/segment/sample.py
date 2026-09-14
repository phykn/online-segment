import numpy as np
from scipy.ndimage import label


CELL_SIZE = 8
CELL_LIMIT = 4
REGION_LIMIT = 256


def quotas(counts, total):
    values = np.asarray(counts, dtype=np.int64)
    result = np.zeros(len(values), dtype=int)
    remaining = min(total, int(values.sum()))
    while remaining:
        active = np.flatnonzero(result < values)
        share = remaining // len(active)
        if not share:
            selected = ((np.arange(remaining)+.5)*len(active)/remaining).astype(int)
            result[active[selected]] += 1
            break
        added = np.minimum(share, values[active]-result[active])
        result[active] += added
        remaining -= int(added.sum())
    return result


def spatial(mask, limit):
    flat = np.flatnonzero(mask)
    if not len(flat) or limit <= 0:
        return flat[:0]
    groups = label(mask, structure=np.ones((3, 3), bool))[0].ravel()[flat]
    y, x = np.divmod(flat, mask.shape[1])
    cells = y//CELL_SIZE*((mask.shape[1]+CELL_SIZE-1)//CELL_SIZE) + x//CELL_SIZE
    # Fixed coordinate priorities keep surviving examples stable during edits.
    priority = flat.astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15)
    priority = (priority ^ (priority >> 30)) * np.uint64(0xBF58476D1CE4E5B9)
    priority = (priority ^ (priority >> 27)) * np.uint64(0x94D049BB133111EB)
    priority ^= priority >> 31
    order = np.lexsort((priority, cells, groups))
    starts = np.flatnonzero(np.r_[True, (np.diff(groups[order]) != 0) | (np.diff(cells[order]) != 0)])
    counts = np.diff(np.r_[starts, len(order)])
    ranks = np.arange(len(order)) - np.repeat(starts, counts)
    order = order[ranks < CELL_LIMIT]
    flat, groups = flat[order], groups[order]
    starts = np.flatnonzero(np.r_[True, np.diff(groups) != 0])
    counts = np.diff(np.r_[starts, len(flat)])
    budgets = quotas(np.minimum(counts, REGION_LIMIT), limit)
    if np.array_equal(budgets, counts):
        return flat
    ranks = np.arange(budgets.sum()) - np.repeat(np.cumsum(budgets)-budgets, budgets)
    selected = np.repeat(starts, budgets) + ((ranks+.5)*np.repeat(counts, budgets)/np.repeat(budgets, budgets)).astype(int)
    return flat[selected]
