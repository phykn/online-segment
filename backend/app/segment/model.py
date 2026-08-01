from pathlib import Path
from threading import RLock
from uuid import uuid4

import joblib
import numpy as np
from fastapi import HTTPException, status
from sklearn.ensemble import RandomForestClassifier

from app.config import config
from app.segment import edge, feature


cfg = config.model


class Segmenter:
    def __init__(self, path: Path):
        self.path = path
        self.lock = RLock()

    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        weights: np.ndarray | None = None,
    ) -> RandomForestClassifier:
        if np.unique(y).size < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Use at least two labels.",
            )
        with self.lock:
            classifier = self._make()
            classifier.fit(x, y, sample_weight=weights)
            self._save(classifier)
        return classifier

    def load(self) -> RandomForestClassifier:
        with self.lock:
            if not self.path.exists():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="model is not trained.",
                )
            try:
                saved = joblib.load(self.path)
            except Exception as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="model could not be loaded.",
                ) from error

        if not isinstance(saved, dict):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="model could not be loaded.",
            )
        if saved.get("features") != feature.config():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="model must be retrained for the current features.",
            )
        if saved.get("kind") != cfg.kind:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="model must be retrained for the current model type.",
            )
        classifier = saved.get("model")
        if not isinstance(classifier, RandomForestClassifier):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="model could not be loaded.",
            )
        if not isinstance(getattr(classifier, "model_id_", None), str):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="model must be retrained for refinement.",
            )
        return classifier

    def prob(
        self,
        image: np.ndarray,
        classifier: RandomForestClassifier | None = None,
    ) -> np.ndarray:
        height, width, _ = image.shape
        stack = feature.cached(image)
        classifier = classifier or self.load()
        probs = classifier.predict_proba(stack.reshape(-1, feature.COUNT))
        return edge.adjust(image, probs.reshape(height, width, -1))

    def _make(self) -> RandomForestClassifier:
        return RandomForestClassifier(
            n_estimators=cfg.n_estimators,
            max_depth=cfg.max_depth,
            max_features=cfg.max_features,
            min_samples_leaf=cfg.min_samples_leaf,
            class_weight=cfg.class_weight,
            random_state=cfg.random_state,
            n_jobs=cfg.n_jobs,
        )

    def _save(self, classifier: RandomForestClassifier) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        classifier.model_id_ = uuid4().hex
        tmp = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            joblib.dump(
                {
                    "model": classifier,
                    "kind": cfg.kind,
                    "features": feature.config(),
                },
                tmp,
            )
            tmp.replace(self.path)
        finally:
            tmp.unlink(missing_ok=True)
