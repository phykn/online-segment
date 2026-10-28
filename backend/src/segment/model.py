from hashlib import blake2b
from threading import RLock
import numpy as np
from fastapi import HTTPException
from sklearn.decomposition import PCA
from src.config import config, CellposeParameters
from src.segment.runtime import runtime
from src.segment.dino import encoder as dino
from src.segment.classifier import Classifier
from src.segment.cache import Cache
from src.segment.feature import Features, image_features
from src.segment.sample import quotas, spatial
from src.segment.context import extract as extract_context


class Segmenter:
    def __init__(self):
        self.lock = RLock()
        self.features = Cache(config.feature.cache_mb)
        self.raw = Cache(config.dino.cache_mb if config.feature.kind == 'dino' else config.cellpose.cache_mb)
        self.segments = Cache(config.cellpose.cache_mb)
        self.progress = dict(stage='idle', done=0, total=0)
        self.classifier = Classifier()
        self.training = {}
        self.pca = None
        self.signature = None
        self.parameters = CellposeParameters.defaults()

    @staticmethod
    def key(image):
        data = np.ascontiguousarray(image)
        return (data.shape, blake2b(data.view(np.uint8), digest_size=16).digest())

    def report(self, **state):
        self.progress = state

    def configure(self, width, parameters=None):
        parameters = parameters if parameters is not None else self.parameters
        signature = (width, config.feature.kind, config.feature.components, config.feature.cellpose, config.feature.texture, config.feature.flow,
                     tuple(config.cellpose.model_dump().items()), tuple(parameters.model_dump().items()),
                     repr(config.dino.model_dump()))
        if signature != self.signature:
            self.clear()
            self.signature = signature
            self.parameters = parameters.model_copy(deep=True)

    def validate(self, image):
        if image.shape[0]*image.shape[1] > config.cellpose.max_pixels:
            raise HTTPException(422, 'Image is too large. Reduce the working width.')

    def tokens(self, image, progress=None):
        key = self.key(image)
        value = self.raw.get(key)
        if value is None and config.feature.kind == 'dino':
            value = self.raw.put(key, dino.run(image, progress or self.report))
        elif value is None:
            if config.feature.cellpose != 'none':
                _, value = self.run(image, capture=True, progress=progress)
            else:
                _, _, value, _ = runtime.run(image, capture=True, compute_masks=False, progress=progress or self.report, parameters=self.parameters)
                self.raw.put(key, value)
        return value

    def run(self, image, capture, progress=None):
        masks, logits, tokens, endpoints = runtime.run(image, capture=capture, progress=progress or self.report,
            parameters=self.parameters, flow=config.feature.flow and config.feature.cellpose == 'statistics')
        value = extract_context(image, masks, logits, endpoints)
        key = self.key(image)
        self.segments.put(key, value)
        if tokens is not None:
            self.raw.put(key, tokens)
        return value, tokens

    def context(self, image, progress=None):
        self.validate(image)
        key = self.key(image)
        value = self.segments.get(key)
        if value is None:
            value, _ = self.run(image, capture=config.feature.kind != 'image', progress=progress)
        return value

    def propose(self, image):
        return self.context(image).instances

    def prepare_pca(self, records):
        if config.feature.kind == 'image' or self.pca is not None or not records:
            return
        limit = 50000
        pools = []
        for i, (image, _, _) in enumerate(records):
            # Bounded per-image pools avoid retaining all raw encoder volumes.
            pools.append(self.tokens(image).sample(limit//len(records) + (i < limit % len(records))))
        self.report(stage='pca', done=0, total=1)
        if isinstance(pools[0], list):
            # DINO pyramid: one projection per magnification keeps fine and coarse tokens separate.
            self.pca = [fit_pca(np.concatenate(level)) for level in zip(*pools)]
        else:
            self.pca = fit_pca(np.concatenate(pools))

    def feature(self, image, progress=None, scale=1.):
        self.validate(image)
        key = (self.key(image), scale)
        found = self.features.get(key)
        if found is not None:
            return found
        report = progress or self.report
        report(stage='features', done=0, total=1)
        local = None
        if config.feature.kind != 'encoder':
            local = image_features(image, config.feature.texture)
        tokens = None
        if config.feature.kind != 'image':
            if self.pca is None:
                raise ValueError('PCA must be fitted with training images first.')
            tokens = self.tokens(image, report).project(self.pca)
        context = self.context(image, report) if config.feature.cellpose != 'none' else None
        return self.features.put(key, Features(image.shape[:2], local, tokens, context, scale, config.feature.cellpose))

    def fit(self, records):
        records = [(item[0], item[1], item[2] if len(item) > 2 else 1.) for item in records if np.any(item[1] >= 0)]
        counts = [[int(np.count_nonzero(mask == label)) for image, mask, _ in records] for label in range(4)]
        can_train = sum(any(values) for values in counts) >= 2
        if can_train:
            self.prepare_pca(records)
        limits = [quotas(values, 10000) for values in counts]
        samples = []
        local = 0
        for i, (image, mask, scale) in enumerate(records):
            indices = np.concatenate([spatial(mask == label, limits[label][i]) for label in range(4)])
            values = np.empty((len(indices), 0), np.float32)
            if can_train:
                features = self.feature(image, scale=scale)
                values = features.pixels(indices)
                # Image channels lead the feature columns; with encoder tokens beside them the
                # classifier also grows trees on the image channels alone.
                local = features.local.shape[-1] if features.local is not None and features.tokens is not None else 0
            samples.append((values, mask.ravel()[indices]))
        self.report(stage='training', done=0, total=1)
        classifier = Classifier()
        classifier.fit(samples, local)
        self.classifier = classifier
        self.training = {(self.key(image), scale): (image, mask.copy(), scale) for image, mask, scale in records}

    def clear(self):
        self.features.clear()
        self.raw.clear()
        self.segments.clear()
        self.classifier = Classifier()
        self.training = {}
        self.pca = None
        self.signature = None


def fit_pca(data):
    pca = PCA(n_components=min(config.feature.components, *data.shape),
              whiten=False, svd_solver='randomized', random_state=0)
    return pca.fit(data)
