import numpy as np
from fastapi import HTTPException, status
from sklearn.ensemble import RandomForestClassifier

from app.data.mask import read_item
from app.api.schema import TrainItem
from app.config import config
from app.refine.model import Refiner
from app.segment import feature, sample
from app.segment.model import Segmenter


cfg = config.model


def make_data(items: list[TrainItem]) -> tuple[np.ndarray, np.ndarray]:
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

    target = min(cfg.max_per_class, *counts.values())
    xs = []
    ys = []
    for label in sorted(counts):
        available = [int(np.sum(mask == label)) for _, mask, _ in records]
        for (stack, mask, score), limit in zip(
            records,
            sample.quotas(available, target),
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


def apply(
    items: list[TrainItem],
    segmenter: Segmenter,
    refiner: Refiner,
) -> None:
    x, y = make_data(items)
    segmenter.fit(x, y)
    refiner.reset()


def infer(
    image: np.ndarray,
    segmenter: Segmenter,
    refiner: Refiner,
    classifier: RandomForestClassifier | None = None,
    selected: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    classifier = classifier or segmenter.load()
    probs = segmenter.prob(image, classifier)
    probs = refiner.adjust(
        image,
        probs,
        classifier.classes_,
        classifier.model_id_,
    )
    labels = classifier.classes_[np.argmax(probs, axis=2)]
    uncertain = np.max(probs, axis=2) < cfg.uncertain_threshold
    if selected is not None:
        if selected.shape != labels.shape:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="image and mask sizes differ.",
            )
        manual = selected >= 0
        labels[manual] = selected[manual]
        uncertain[manual] = False
    return labels.astype(np.int8), uncertain.astype(np.int8)


def predict(
    image: np.ndarray,
    segmenter: Segmenter,
    refiner: Refiner,
    classifier: RandomForestClassifier | None = None,
    selected: np.ndarray | None = None,
) -> np.ndarray:
    return infer(image, segmenter, refiner, classifier, selected)[0]
