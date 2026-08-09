import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.config import config
from app.segment.cuda_forest import CudaForestPredictor
from app.segment.model import Segmenter


cfg = config.model


def _labels(
    probs: np.ndarray,
    classifier: RandomForestClassifier,
) -> np.ndarray:
    return classifier.classes_[np.argmax(probs, axis=2)].astype(np.int8)


def infer(
    image: np.ndarray,
    segmenter: Segmenter,
    classifier: RandomForestClassifier | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    classifier = classifier or segmenter.load()
    probs = segmenter.prob(image, classifier)
    labels = _labels(probs, classifier)
    uncertain = np.max(probs, axis=2) < cfg.uncertain_threshold
    return labels, uncertain.astype(np.int8)


def predict(
    image: np.ndarray,
    segmenter: Segmenter,
    classifier: RandomForestClassifier | None = None,
) -> np.ndarray:
    classifier = classifier or segmenter.load()
    probs = segmenter.prob(image, classifier)
    return _labels(probs, classifier)


def predict_features(
    stack: np.ndarray,
    segmenter: Segmenter,
    classifier: RandomForestClassifier | None = None,
    predictor: CudaForestPredictor | None = None,
) -> np.ndarray:
    if predictor is not None:
        labels = predictor.predict(stack)
        if labels is not None:
            return labels

    classifier = classifier or segmenter.load()
    probs = segmenter.prob_features(stack, classifier)
    return _labels(probs, classifier)
