import numpy as np
from fastapi import HTTPException, status

from app.config import config
from app.data.mask import TrainItemLike, read_item
from app.segment import feature, sample
from app.segment.model import Segmenter


cfg = config.model


def make_data(items: list[TrainItemLike]) -> tuple[np.ndarray, np.ndarray]:
    records = []
    counts = {}

    for item in items:
        image, mask = read_item(item)
        if not np.any(mask >= 0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="invalid mask RLE.",
            )
        stack = feature.cached(image)
        records.append(
            (
                stack.reshape(-1, feature.COUNT),
                mask,
                feature.edge_score(stack),
            )
        )
        for label in np.unique(mask[mask >= 0]):
            value = int(label)
            counts[value] = counts.get(value, 0) + int(np.sum(mask == value))

    reference = max(min(counts.values()), cfg.balance_floor)
    targets = {
        label: sample.log_limit(count, reference, cfg.max_per_class)
        for label, count in counts.items()
    }
    xs = []
    ys = []
    for label in sorted(counts):
        available = [int(np.sum(mask == label)) for _, mask, _ in records]
        for (stack, mask, score), limit in zip(
            records,
            sample.quotas(available, targets[label]),
        ):
            if limit == 0:
                continue
            indices = sample.guided(
                mask == label,
                score,
                limit,
                cfg.edge_ratio,
                cfg.edge_quantile,
            )
            xs.append(stack[indices])
            ys.append(np.full(limit, label, dtype=np.int8))

    return np.concatenate(xs), np.concatenate(ys)


def apply(items: list[TrainItemLike], segmenter: Segmenter) -> None:
    x, y = make_data(items)
    segmenter.fit(x, y)
