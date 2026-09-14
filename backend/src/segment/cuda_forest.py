from __future__ import annotations

from importlib import import_module
from threading import RLock
from typing import Any

import numpy as np


_CUDA_LOCK = RLock()
_CUDA_DISABLED = False


def _float32_cutoffs(thresholds: np.ndarray) -> np.ndarray:
    """Map float64 tree thresholds to equivalent float32 comparisons."""
    values = np.asarray(thresholds, dtype=np.float64)
    cutoffs = values.astype(np.float32)
    rounded_up = cutoffs.astype(np.float64) > values
    cutoffs[rounded_up] = np.nextafter(
        cutoffs[rounded_up],
        np.float32(-np.inf),
    )
    return cutoffs


def _load_torch() -> Any | None:
    try:
        return import_module("torch")
    except (ImportError, OSError, RuntimeError):
        return None


def _pack(classifier: Any) -> tuple[Any, ...] | None:
    estimators = tuple(getattr(classifier, "estimators_", ()))
    classes = np.asarray(getattr(classifier, "classes_", ()))
    if not estimators or classes.ndim != 1 or classes.size == 0:
        return None

    try:
        feature_count = int(classifier.n_features_in_)
        labels = classes.astype(np.int8)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None

    offsets = []
    node_count = 0
    for estimator in estimators:
        offsets.append(node_count)
        node_count += int(estimator.tree_.node_count)

    features = np.zeros(node_count, dtype=np.int64)
    thresholds = np.full(node_count, np.inf, dtype=np.float32)
    children_left = np.empty(node_count, dtype=np.int64)
    children_right = np.empty(node_count, dtype=np.int64)
    probabilities = np.empty(
        (node_count, classes.size),
        dtype=np.float32,
    )
    max_depth = 0

    for offset, estimator in zip(offsets, estimators, strict=True):
        tree = estimator.tree_
        count = int(tree.node_count)
        stop = offset + count
        node_ids = np.arange(count, dtype=np.int64)
        internal = tree.children_left >= 0
        max_depth = max(max_depth, int(tree.max_depth))

        node_features = features[offset:stop]
        node_thresholds = thresholds[offset:stop]
        node_features[internal] = tree.feature[internal]
        node_thresholds[internal] = _float32_cutoffs(
            tree.threshold[internal]
        )

        children_left[offset:stop] = np.where(
            internal,
            tree.children_left + offset,
            node_ids + offset,
        )
        children_right[offset:stop] = np.where(
            internal,
            tree.children_right + offset,
            node_ids + offset,
        )

        values = np.asarray(tree.value)
        if (
            values.ndim != 3
            or values.shape[1] != 1
            or values.shape[2] != classes.size
        ):
            return None
        values = values[:, 0, :]
        probabilities[offset:stop] = values / values.sum(axis=1, keepdims=True)

    return (
        features,
        thresholds,
        children_left,
        children_right,
        probabilities,
        np.asarray(offsets, dtype=np.int64),
        labels,
        feature_count,
        max_depth,
    )


def _disable_cuda(torch: Any) -> None:
    global _CUDA_DISABLED

    _CUDA_DISABLED = True
    try:
        torch.cuda.empty_cache()
    except Exception:
        pass


class CudaForestPredictor:
    def __init__(
        self,
        classifier: Any,
        torch: Any,
        packed: tuple[Any, ...],
    ) -> None:
        (
            features,
            thresholds,
            children_left,
            children_right,
            probabilities,
            roots,
            labels,
            self.feature_count,
            self.max_depth,
        ) = packed
        self.classifier = classifier
        self.torch = torch
        self.device = torch.device("cuda")
        self.features = torch.from_numpy(features).to(self.device)
        self.thresholds = torch.from_numpy(thresholds).to(self.device)
        self.children_left = torch.from_numpy(children_left).to(self.device)
        self.children_right = torch.from_numpy(children_right).to(self.device)
        self.probabilities = torch.from_numpy(probabilities).to(self.device)
        self.roots = torch.from_numpy(roots).to(self.device)
        self.labels = torch.from_numpy(labels).to(self.device)
        self.class_labels = labels

    def predict_proba(self, values: np.ndarray) -> np.ndarray | None:
        flat = np.ascontiguousarray(values, dtype=np.float32)
        if flat.ndim != 2 or flat.shape[1] != self.feature_count:
            raise ValueError("wrong feature dimensions")
        with _CUDA_LOCK:
            if _CUDA_DISABLED:
                return None
            try:
                return self._predict_locked(flat)
            except (RuntimeError, OSError):
                _disable_cuda(self.torch)
                return None

    def _predict_locked(self, flat: np.ndarray) -> np.ndarray:
        torch = self.torch
        output = np.empty((len(flat), len(self.class_labels)), np.float32)
        with torch.inference_mode():
            for start in range(0, len(flat), 4096):
                stop = min(start + 4096, len(flat))
                inputs = torch.from_numpy(flat[start:stop]).to(self.device)
                nodes = self.roots.expand(len(inputs), -1).clone()
                for _ in range(self.max_depth):
                    values = torch.gather(inputs, 1, self.features[nodes])
                    nodes = torch.where(values <= self.thresholds[nodes],
                        self.children_left[nodes], self.children_right[nodes])
                scores = self.probabilities[nodes].mean(dim=1)
                output[start:stop] = scores.cpu().numpy()
        return output


def make_predictor(classifier: Any) -> CudaForestPredictor | None:
    if _CUDA_DISABLED:
        return None
    torch = _load_torch()
    if torch is None or not torch.cuda.is_available():
        return None
    packed = _pack(classifier)
    if packed is None:
        return None
    with _CUDA_LOCK:
        if _CUDA_DISABLED:
            return None
        try:
            return CudaForestPredictor(classifier, torch, packed)
        except (RuntimeError, OSError):
            _disable_cuda(torch)
            return None
