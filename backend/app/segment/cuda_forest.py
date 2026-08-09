from __future__ import annotations

from importlib import import_module
from threading import RLock
from typing import Any

import numpy as np

from app.config import config

cfg = config.performance.cuda_forest


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
        probabilities[offset:stop] = values[:, 0, :]

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

    def predict(self, stack: np.ndarray) -> np.ndarray | None:
        values = np.asarray(stack)
        if values.ndim != 3:
            raise ValueError("feature stack must have three dimensions")
        if values.shape[2] != self.feature_count:
            raise ValueError("feature stack has the wrong feature count")

        height, width, _ = values.shape
        flat = np.ascontiguousarray(
            values.reshape(-1, self.feature_count),
            dtype=np.float32,
        )
        if flat.shape[0] == 0:
            return np.empty((height, width), dtype=np.int8)

        with _CUDA_LOCK:
            if _CUDA_DISABLED:
                return None
            try:
                output = self._predict_locked(flat)
            except (RuntimeError, OSError):
                _disable_cuda(self.torch)
                return None

        return output.reshape(height, width)

    def _tree_scores(self, inputs: Any, roots: Any) -> Any:
        torch = self.torch
        nodes = roots.expand(inputs.shape[0], -1).clone()
        for _ in range(self.max_depth):
            node_features = self.features[nodes]
            feature_values = torch.gather(inputs, 1, node_features)
            go_left = feature_values <= self.thresholds[nodes]
            nodes = torch.where(
                go_left,
                self.children_left[nodes],
                self.children_right[nodes],
            )
        return self.probabilities[nodes].sum(dim=1)

    def _full_chunk(self, inputs: Any) -> np.ndarray:
        scores = self._tree_scores(inputs, self.roots)
        indices = self.torch.argmax(scores, dim=1)
        return self.labels[indices].cpu().numpy()

    def _staged_chunk(self, inputs: Any) -> tuple[np.ndarray, float]:
        torch = self.torch
        count = inputs.shape[0]
        class_count = self.labels.shape[0]
        active_indices = torch.arange(count, device=self.device)
        active_inputs = inputs
        scores = torch.zeros(
            (count, class_count),
            dtype=torch.float32,
            device=self.device,
        )
        result = torch.empty(count, dtype=torch.int8, device=self.device)
        first_exit_rate = 0.0
        tree_start = 0

        for stage in cfg.early_exit:
            tree_stop = stage.trees
            margin = stage.margin
            if tree_stop >= self.roots.shape[0]:
                break
            scores += self._tree_scores(
                active_inputs,
                self.roots[tree_start:tree_stop],
            )
            top_two = torch.topk(scores, 2, dim=1).values
            done = (top_two[:, 0] - top_two[:, 1]) / tree_stop >= margin
            if tree_start == 0:
                first_exit_rate = float(done.float().mean().item())

            if torch.any(done):
                label_indices = torch.argmax(scores[done], dim=1)
                result[active_indices[done]] = self.labels[label_indices]

            keep = ~done
            if not torch.any(keep):
                return result.cpu().numpy(), first_exit_rate
            active_indices = active_indices[keep]
            active_inputs = active_inputs[keep]
            scores = scores[keep]
            tree_start = tree_stop

        scores += self._tree_scores(active_inputs, self.roots[tree_start:])
        label_indices = torch.argmax(scores, dim=1)
        result[active_indices] = self.labels[label_indices]
        return result.cpu().numpy(), first_exit_rate

    def _predict_locked(self, flat: np.ndarray) -> np.ndarray:
        if self.labels.shape[0] == 1:
            return np.full(flat.shape[0], self.class_labels[0], dtype=np.int8)

        torch = self.torch
        output = np.empty(flat.shape[0], dtype=np.int8)
        early_exit = self.roots.shape[0] > cfg.early_exit[0].trees
        first_chunk = True
        start = 0

        with torch.inference_mode():
            while start < flat.shape[0]:
                size = cfg.chunk_size if early_exit else cfg.full_chunk_size
                stop = min(start + size, flat.shape[0])
                inputs = torch.from_numpy(flat[start:stop]).to(self.device)
                if early_exit:
                    labels, exit_rate = self._staged_chunk(inputs)
                    if first_chunk and exit_rate < cfg.min_exit_rate:
                        early_exit = False
                else:
                    labels = self._full_chunk(inputs)
                output[start:stop] = labels
                first_chunk = False
                start = stop

        return output


def make_predictor(classifier: Any) -> CudaForestPredictor | None:
    if not cfg.enabled or _CUDA_DISABLED:
        return None

    packed = _pack(classifier)
    if packed is None:
        return None

    torch = _load_torch()
    if torch is None:
        return None

    with _CUDA_LOCK:
        if _CUDA_DISABLED:
            return None
        try:
            if not torch.cuda.is_available():
                return None
            return CudaForestPredictor(classifier, torch, packed)
        except Exception:
            _disable_cuda(torch)
            return None
