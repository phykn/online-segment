import numpy as np
import torch
from fastapi import HTTPException, status
from scipy.ndimage import distance_transform_edt as distance
from torch.nn import functional

from app.api.schema import TrainItem
from app.config import config
from app.data.mask import read_item
from app.refine import net
from app.refine.model import refiner
from app.segment import feature
from app.segment.model import segmenter


cfg = config.refine


def fit(items: list[TrainItem], target: TrainItem) -> None:
    classifier = segmenter.load()
    classes = classifier.classes_.astype(np.int8)
    class_idx = {int(label): idx for idx, label in enumerate(classes)}
    unique = {item.image: item for item in items}
    unique[target.image] = target
    records = []
    caps = {int(label): 0 for label in classes}
    target_idx = None

    for item in unique.values():
        image, mask = read_item(item)
        used = np.unique(mask[mask >= 0])
        if any(int(label) not in class_idx for label in used):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Apply after adding a new label.",
            )
        for label in used:
            caps[int(label)] += int(np.sum(mask == label))
        probs = segmenter.prob(image, classifier)
        records.append((image, mask, probs))
        if item.image == target.image:
            target_idx = len(records) - 1

    image, mask, probs = records[target_idx]
    indices, labels = _select(
        probs.reshape(-1, probs.shape[2]),
        classes,
        mask,
        caps,
    )
    if indices.size == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No predictions met the refine confidence.",
        )

    data = []
    for idx, (image, mask, probs) in enumerate(records):
        targets = np.full(mask.shape, cfg.ignore, dtype=np.int64)
        weights = np.zeros(mask.shape, dtype=np.float32)
        manual = mask >= 0
        for label, label_idx in class_idx.items():
            selected = mask == label
            targets[selected] = label_idx
            weights[selected] = 1.0
        if idx == target_idx:
            flat_targets = targets.ravel()
            flat_weights = weights.ravel()
            for label, label_idx in class_idx.items():
                selected = indices[labels == label]
                flat_targets[selected] = label_idx
                flat_weights[selected] = cfg.pseudo_weight
        data.append((image, probs, targets, weights, manual))

    _learn(data, classes, classifier.model_id_)


def _core(labels: np.ndarray) -> np.ndarray:
    edge = np.zeros(labels.shape, dtype=bool)
    diff = labels[1:, :] != labels[:-1, :]
    edge[1:, :] |= diff
    edge[:-1, :] |= diff
    diff = labels[:, 1:] != labels[:, :-1]
    edge[:, 1:] |= diff
    edge[:, :-1] |= diff
    if not np.any(edge):
        return np.ones(labels.size, dtype=bool)

    radius = max(
        1.0,
        min(labels.shape) / config.feature.base_size * cfg.core_scale,
    )
    return (distance(~edge) >= radius).ravel()


def _select(
    probs: np.ndarray,
    classes: np.ndarray,
    mask: np.ndarray,
    caps: dict[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    best = np.argmax(probs, axis=1)
    rows = np.arange(probs.shape[0])
    confidence = probs[rows, best]
    labels = classes[best].astype(np.int8)
    candidates = (
        (confidence >= cfg.threshold)
        & _core(labels.reshape(mask.shape))
        & (mask.ravel() < 0)
    )
    rng = np.random.default_rng(0)
    groups = []

    for label in classes:
        limit = caps.get(int(label), 0)
        if limit <= 0:
            continue
        indices = np.flatnonzero(candidates & (labels == label))
        if indices.size > limit:
            indices = rng.choice(indices, limit, replace=False)
        if indices.size:
            groups.append(indices)

    counts = np.zeros(len(groups), dtype=np.int64)
    remaining = min(cfg.max_total, sum(group.size for group in groups))
    while remaining:
        changed = False
        for idx, group in enumerate(groups):
            if counts[idx] >= group.size:
                continue
            counts[idx] += 1
            remaining -= 1
            changed = True
            if remaining == 0:
                break
        if not changed:
            break

    chosen = []
    for group, count in zip(groups, counts):
        if count < group.size:
            group = rng.choice(group, count, replace=False)
        chosen.append(group)

    indices = np.concatenate(chosen) if chosen else np.empty(0, dtype=np.int64)
    return indices, labels[indices]


def _learn(data, classes: np.ndarray, rf_id: str) -> dict:
    device = net.device()

    with refiner.lock:
        corrector = refiner.load(classes, rf_id, device)
        first = corrector is None
        if first:
            corrector = net.UNet(len(classes)).to(device)

        ready, groups = _prepare(data)
        if not groups[True] and not groups[False]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No labels are available for refinement.",
            )

        steps = cfg.first_steps if first else cfg.next_steps
        rng = np.random.default_rng(0)
        optimizer = torch.optim.AdamW(corrector.parameters(), lr=cfg.lr)
        use_amp = device.type == "cuda"
        scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
        corrector.train()

        last_loss = 0.0
        for step in range(steps):
            images, targets, weights, manual = _batch(
                ready,
                groups,
                rng,
                step * cfg.batch,
            )
            images = torch.from_numpy(images).to(device)
            targets = torch.from_numpy(targets).long().to(device)
            weights = torch.from_numpy(weights).to(device)
            manual = torch.from_numpy(manual).to(device)
            optimizer.zero_grad(set_to_none=True)

            with torch.autocast(
                device_type=device.type,
                dtype=torch.float16,
                enabled=use_amp,
            ):
                logits = corrector(images)
                loss = _loss(
                    logits,
                    targets,
                    weights,
                    manual,
                )

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            last_loss = float(loss.detach().cpu())

        corrector.eval()
        refiner.save(corrector, classes, rf_id)
        return {"device": device.type, "steps": steps, "loss": last_loss}


def _loss(logits, targets, weights, manual):
    losses = functional.cross_entropy(
        logits,
        targets,
        ignore_index=cfg.ignore,
        reduction="none",
    )
    focal = (1.0 - torch.exp(-losses)).pow(cfg.focal_gamma)
    focal = torch.where(manual, focal, torch.ones_like(focal))
    return (losses * focal * weights).sum() / weights.sum().clamp_min(1.0)


def _prepare(data):
    half = cfg.patch // 2
    ready = []
    groups = {True: {}, False: {}}

    for idx, (image, probs, target, weights, manual) in enumerate(data):
        mode = "reflect" if min(image.shape[:2]) > 1 else "edge"
        value = np.pad(
            net.input(image, probs),
            ((0, 0), (half, half), (half, half)),
            mode=mode,
        )
        labels = np.pad(target, half, constant_values=cfg.ignore)
        weight = np.pad(weights, half, constant_values=0.0)
        padded_manual = np.pad(manual, half, constant_values=False)
        ready.append((value, labels, weight, padded_manual))

        for source in (True, False):
            selected = (target >= 0) & (manual == source)
            for label in np.unique(target[selected]):
                points = np.argwhere(selected & (target == label))
                groups[source].setdefault(int(label), []).append((idx, points))

    return ready, groups


def _batch(ready, groups, rng, offset: int):
    images = []
    targets = []
    weights = []
    manuals = []
    blocks, rest = divmod(offset, cfg.batch)
    counts = {
        True: blocks * cfg.manual_batch + min(rest, cfg.manual_batch),
        False: (
            blocks * (cfg.batch - cfg.manual_batch)
            + max(0, rest - cfg.manual_batch)
        ),
    }

    for batch_idx in range(cfg.batch):
        source = (offset + batch_idx) % cfg.batch < cfg.manual_batch
        if not groups[source]:
            source = not source
        active = sorted(groups[source])
        label = active[counts[source] % len(active)]
        counts[source] += 1
        choices = groups[source][label]
        item_idx, points = choices[rng.integers(len(choices))]
        y, x = points[rng.integers(len(points))]
        image, target, weight, manual = ready[item_idx]
        image = image[:, y : y + cfg.patch, x : x + cfg.patch]
        target = target[y : y + cfg.patch, x : x + cfg.patch]
        weight = weight[y : y + cfg.patch, x : x + cfg.patch]
        manual = manual[y : y + cfg.patch, x : x + cfg.patch]

        turns = int(rng.integers(4))
        image = np.rot90(image, turns, axes=(1, 2))
        target = np.rot90(target, turns)
        weight = np.rot90(weight, turns)
        manual = np.rot90(manual, turns)
        if rng.random() < 0.5:
            image = image[:, :, ::-1]
            target = target[:, ::-1]
            weight = weight[:, ::-1]
            manual = manual[:, ::-1]
        if rng.random() < 0.5:
            image = image[:, ::-1, :]
            target = target[::-1, :]
            weight = weight[::-1, :]
            manual = manual[::-1, :]

        images.append(np.ascontiguousarray(image))
        targets.append(np.ascontiguousarray(target))
        weights.append(np.ascontiguousarray(weight))
        manuals.append(np.ascontiguousarray(manual))

    return (
        np.stack(images),
        np.stack(targets),
        np.stack(weights),
        np.stack(manuals),
    )
