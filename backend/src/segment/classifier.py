import cv2
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from src.segment.cuda_forest import make_predictor


def forest(trees):
    # Random split thresholds generalise better than RF from a few brush strokes on DINO features.
    # Trying 30% of features per split lets the few brightness channels compete with DINO dims.
    return ExtraTreesClassifier(n_estimators=trees, max_depth=10, min_samples_leaf=2, max_features=.3,
                                class_weight='balanced', random_state=0, n_jobs=-1)


def shapes(trees):
    # Labels sit inside particles, but a rim shares its particle's size channels. One best-split cut
    # between the labelled sizes keeps rims with their particle; random cuts leave mixed nodes that
    # edge channels finish, and there a large particle's rim looks like a small grain.
    return RandomForestClassifier(n_estimators=trees, max_depth=10, min_samples_leaf=2, max_features=.3,
                                  bootstrap=False, class_weight='balanced', random_state=0, n_jobs=-1)


class Classifier:
    def __init__(self):
        self.model = None
        self.cuda = None
        self.count = 0
        self.counts = [0]*4
        self.classes = []

    def fit(self, samples, local=0, size=0):
        selected = [(x, y) for x, y in samples if len(y)]
        self.count = sum(len(y) for _, y in selected)
        self.counts = [sum(int(np.count_nonzero(y == label)) for _, y in selected) for label in range(4)]
        self.classes = sorted(set(int(v) for _, y in selected for v in np.unique(y)))
        model = None
        if len(self.classes) >= 2:
            x = np.concatenate([x for x, _ in selected])
            y = np.concatenate([y for _, y in selected])
            if 0 < local < x.shape[1]:
                # Columns: `local` pixel-exact image channels, `size` size channels, then encoder
                # tokens or context. Three quarters of the trees see the image channels with the
                # tokens, a quarter with the size channels (other columns are zeroed; constant
                # columns are never split on). The image-only quarter keeps a few strokes from
                # fitting token noise, and size channels in the token trees lowered scores.
                tokens = x.copy()
                tokens[:, local:local+size] = 0
                shape = x.copy()
                shape[:, local+size:] = 0
                model = forest(150).fit(tokens, y)
                model.estimators_ += (shapes if size else forest)(50).fit(shape, y).estimators_
                model.n_estimators = len(model.estimators_)
            else:
                model = forest(200).fit(x, y)
        self.model = model
        self.cuda = make_predictor(model) if model is not None else None

    def predict(self, features, progress=lambda **kwargs: None):
        size = int(np.prod(features.shape))
        labels = np.full(size, -1, np.int8)
        unclear = np.ones(size, np.int8)
        if self.model is not None:
            probs = np.empty((size, len(self.model.classes_)), np.float32)
            for start in range(0, size, 65536):
                end = min(size, start+65536)
                progress(stage='predicting', done=start, total=size)
                values = features.pixels(np.arange(start, end))
                chunk = self.cuda.predict_proba(values) if self.cuda is not None else None
                if chunk is None:
                    self.cuda = None
                    chunk = self.model.predict_proba(values)
                probs[start:end] = chunk
            local = getattr(features, 'local', None)
            if local is not None:
                probs = refine(probs, local[..., 0])
            probs = rebalance(probs)
            labels = self.model.classes_[probs.argmax(axis=1)].astype(np.int8)
            unclear = (probs.max(axis=1) < .7).astype(np.int8)
        return labels.reshape(features.shape), unclear.reshape(features.shape)


def refine(probs, gray, radius=2, eps=1e-4):
    """Guided filter of class probabilities by the luminance: tokens are interpolated, so class
    edges blur over a few pixels; the filter snaps them to brightness edges, which keeps thin
    cracks thin and particle rims whole."""
    window = (2*radius+1, 2*radius+1)
    box = lambda value: cv2.boxFilter(value, -1, window)
    gray = gray.astype(np.float32)
    mean = box(gray)
    variance = box(gray*gray) - mean*mean
    out = np.empty_like(probs)
    for c in range(probs.shape[1]):
        p = np.ascontiguousarray(probs[:, c].reshape(gray.shape))
        p_mean = box(p)
        a = (box(gray*p) - mean*p_mean) / (variance+eps)
        b = p_mean - a*mean
        out[:, c] = (box(a)*gray + box(b)).ravel()
    out = np.maximum(out, 1e-4)
    return out / out.sum(axis=1, keepdims=True)


def rebalance(probs, power=.5):
    """Balanced class weights train every class as equally common, so a rare class such as crack
    is over-predicted. Move halfway (in log space) to the class shares the image itself predicts."""
    shares = probs.mean(axis=0) * probs.shape[1]
    out = probs * shares**power
    return out / out.sum(axis=1, keepdims=True)
