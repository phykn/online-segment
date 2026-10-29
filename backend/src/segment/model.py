from hashlib import blake2b
from threading import RLock
import numpy as np
from fastapi import HTTPException
from sklearn.decomposition import PCA
from src.config import config, CLASSES
from src.segment.dino import encoder as dino
from src.segment.classifier import Classifier
from src.segment.cache import Cache
from src.segment.feature import Features, image_features, size_features
from src.segment.sample import quotas, spatial


class Segmenter:
    def __init__(self):
        self.lock = RLock()
        self.features = Cache(config.feature.cache_mb)
        self.raw = Cache(config.dino.cache_mb)
        self.progress = dict(stage='idle', done=0, total=0)
        self.classifier = Classifier()
        self.training = {}
        self.pca = None
        self.signature = None

    @staticmethod
    def key(image):
        data = np.ascontiguousarray(image)
        return (data.shape, blake2b(data.view(np.uint8), digest_size=16).digest())

    def report(self, **state):
        self.progress = state

    def configure(self, width):
        signature = (width, config.feature.kind, config.feature.components, config.feature.texture,
                     repr(config.dino.model_dump()))
        if signature != self.signature:
            self.clear()
            self.signature = signature

    def validate(self, image):
        if image.shape[0]*image.shape[1] > config.feature.max_pixels:
            raise HTTPException(422, 'Image is too large. Reduce the working width.')

    def tokens(self, image, progress=None):
        key = self.key(image)
        value = self.raw.get(key)
        if value is None:
            value = self.raw.put(key, dino.run(image, progress or self.report))
        return value

    def prepare_pca(self, records):
        if config.feature.kind == 'image' or self.pca is not None or not records:
            return
        limit = 50000
        pools = []
        for i, (image, _) in enumerate(records):
            # Bounded per-image pools avoid retaining all raw encoder volumes.
            pools.append(self.tokens(image).sample(limit//len(records) + (i < limit % len(records))))
        self.report(stage='pca', done=0, total=1)
        # DINO pyramid: one projection per magnification keeps fine and coarse tokens separate.
        self.pca = [fit_pca(np.concatenate(level)) for level in zip(*pools)]

    def feature(self, image, progress=None):
        self.validate(image)
        key = self.key(image)
        found = self.features.get(key)
        if found is not None:
            return found
        report = progress or self.report
        report(stage='features', done=0, total=1)
        local = image_features(image, config.feature.texture)
        size = size_features(image)
        tokens = None
        if config.feature.kind == 'dino':
            if self.pca is None:
                raise ValueError('PCA must be fitted with training images first.')
            tokens = self.tokens(image, report).project(self.pca)
        return self.features.put(key, Features(image.shape[:2], local, tokens, size))

    def fit(self, records):
        records = [(image, mask) for image, mask in records if np.any(mask >= 0)]
        counts = [[int(np.count_nonzero(mask == label)) for _, mask in records] for label in range(CLASSES)]
        can_train = sum(any(values) for values in counts) >= 2
        if can_train:
            self.prepare_pca(records)
        limits = [quotas(values, 10000) for values in counts]
        samples = []
        local = size = 0
        for i, (image, mask) in enumerate(records):
            indices = np.concatenate([spatial(mask == label, limits[label][i]) for label in range(CLASSES)])
            values = np.empty((len(indices), 0), np.float32)
            if can_train:
                features = self.feature(image)
                values = features.pixels(indices)
                # Image channels lead the feature columns, then size channels; the classifier
                # splits its trees between them and the DINO tokens that follow.
                local = features.local.shape[-1]
                size = features.size.shape[-1]
            samples.append((values, mask.ravel()[indices]))
        self.report(stage='training', done=0, total=1)
        classifier = Classifier()
        classifier.fit(samples, local, size)
        self.classifier = classifier
        self.training = {self.key(image): (image, mask.copy()) for image, mask in records}

    def clear(self):
        self.features.clear()
        self.raw.clear()
        self.classifier = Classifier()
        self.training = {}
        self.pca = None
        self.signature = None


def fit_pca(data):
    pca = PCA(n_components=min(config.feature.components, *data.shape),
              whiten=False, svd_solver='randomized', random_state=0)
    return pca.fit(data)
