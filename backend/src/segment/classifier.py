import numpy as np
from sklearn.ensemble import RandomForestClassifier


class Classifier:
    def __init__(self):
        self.model = None
        self.count = 0
        self.counts = [0]*4
        self.classes = []

    def fit(self, samples):
        selected = [(x, y) for x, y in samples if len(y)]
        self.count = sum(len(y) for _, y in selected)
        self.counts = [sum(int(np.count_nonzero(y == label)) for _, y in selected) for label in range(4)]
        self.classes = sorted(set(int(v) for _, y in selected for v in np.unique(y)))
        model = None
        if len(self.classes) >= 2:
            model = RandomForestClassifier(n_estimators=200, max_depth=10,
                min_samples_leaf=2, max_features='sqrt', class_weight='balanced',
                random_state=0, n_jobs=-1)
            model.fit(np.concatenate([x for x, _ in selected]), np.concatenate([y for _, y in selected]))
        self.model = model

    def predict(self, features, progress=lambda **kwargs: None):
        size = int(np.prod(features.shape))
        labels = np.full(size, -1, np.int8)
        unclear = np.ones(size, np.int8)
        if self.model is not None:
            for start in range(0, size, 65536):
                end = min(size, start+65536)
                progress(stage='predicting', done=start, total=size)
                probs = self.model.predict_proba(features.pixels(np.arange(start, end)))
                labels[start:end] = self.model.classes_[probs.argmax(axis=1)]
                unclear[start:end] = probs.max(axis=1) < .7
        return labels.reshape(features.shape), unclear.reshape(features.shape)
