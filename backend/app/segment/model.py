from pathlib import Path
from threading import RLock
from uuid import uuid4

import joblib
import numpy as np
from fastapi import HTTPException, status
from sklearn.ensemble import RandomForestClassifier

from app.config import config
from app.segment import cuda_forest, feature


cfg = config.model


class Segmenter:
    def __init__(self, path: Path):
        self.path = path
        self.lock = RLock()
        self._cache = {}

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
            stamp = self.path.stat().st_mtime_ns
            if self._cache.get("stamp") == stamp:
                return self._cache["model"]
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
        classifier = saved.get("model")
        if not isinstance(classifier, RandomForestClassifier):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="model could not be loaded.",
            )
        self._remember_model(stamp, classifier)
        return classifier

    def _remember_model(
        self,
        stamp: int,
        classifier: RandomForestClassifier,
    ) -> None:
        with self.lock:
            self._cache.pop("batch_predictor_model", None)
            self._cache.pop("batch_predictor", None)
            self._cache.update(stamp=stamp, model=classifier)

    def features(
        self,
        image: np.ndarray,
        cached: bool = True,
    ) -> np.ndarray:
        if cached:
            return feature.cached(image)
        return feature.make(image)

    def prob(
        self,
        image: np.ndarray,
        classifier: RandomForestClassifier | None = None,
    ) -> np.ndarray:
        return self.prob_features(
            self.features(image),
            classifier,
        )

    def prob_features(
        self,
        stack: np.ndarray,
        classifier: RandomForestClassifier | None = None,
    ) -> np.ndarray:
        height, width, _ = stack.shape
        classifier = classifier or self.load()
        probs = classifier.predict_proba(stack.reshape(-1, feature.COUNT))
        return probs.reshape(height, width, -1)

    def batch_predictor(
        self,
        classifier: RandomForestClassifier,
    ) -> cuda_forest.CudaForestPredictor | None:
        with self.lock:
            if (
                self._cache.get("batch_predictor_model") is classifier
                and "batch_predictor" in self._cache
            ):
                return self._cache["batch_predictor"]

            predictor = cuda_forest.make_predictor(classifier)
            self._cache.update(
                batch_predictor_model=classifier,
                batch_predictor=predictor,
            )
            return predictor

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
        tmp = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            joblib.dump(
                {
                    "model": classifier,
                    "features": feature.config(),
                },
                tmp,
            )
            tmp.replace(self.path)
            self._remember_model(self.path.stat().st_mtime_ns, classifier)
        finally:
            tmp.unlink(missing_ok=True)
