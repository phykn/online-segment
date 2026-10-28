import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from src.segment.cuda_forest import make_predictor


def forest(trees):
    # Random split thresholds generalise better than RF from a few brush strokes on DINO features.
    # Trying 30% of features per split lets the few brightness channels compete with DINO dims.
    return ExtraTreesClassifier(n_estimators=trees, max_depth=10, min_samples_leaf=2, max_features=.3,
                                class_weight='balanced', random_state=0, n_jobs=-1)


class Classifier:
    def __init__(self):
        self.model = None
        self.cuda = None
        self.count = 0
        self.counts = [0]*4
        self.classes = []

    def fit(self, samples, local=0):
        selected = [(x, y) for x, y in samples if len(y)]
        self.count = sum(len(y) for _, y in selected)
        self.counts = [sum(int(np.count_nonzero(y == label)) for _, y in selected) for label in range(4)]
        self.classes = sorted(set(int(v) for _, y in selected for v in np.unique(y)))
        model = None
        if len(self.classes) >= 2:
            x = np.concatenate([x for x, _ in selected])
            y = np.concatenate([y for _, y in selected])
            split = 0 < local < x.shape[1]
            model = forest(100 if split else 200).fit(x, y)
            if split:
                # Half the trees see only the leading pixel-exact image channels (the rest are zeroed,
                # and constant columns are never split on). Averaging them with trees that also see
                # encoder tokens keeps a few strokes from fitting token noise.
                only = x.copy()
                only[:, local:] = 0
                model.estimators_ += forest(100).fit(only, y).estimators_
                model.n_estimators = len(model.estimators_)
        self.model = model
        self.cuda = make_predictor(model) if model is not None else None

    def predict(self, features, progress=lambda **kwargs: None):
        size = int(np.prod(features.shape))
        labels = np.full(size, -1, np.int8)
        unclear = np.ones(size, np.int8)
        if self.model is not None:
            for start in range(0, size, 65536):
                end = min(size, start+65536)
                progress(stage='predicting', done=start, total=size)
                values = features.pixels(np.arange(start, end))
                probs = self.cuda.predict_proba(values) if self.cuda is not None else None
                if probs is None:
                    self.cuda = None
                    probs = self.model.predict_proba(values)
                labels[start:end] = self.model.classes_[probs.argmax(axis=1)]
                unclear[start:end] = probs.max(axis=1) < .7
        return labels.reshape(features.shape), unclear.reshape(features.shape)
