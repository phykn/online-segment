from collections import OrderedDict
from hashlib import blake2b
from threading import RLock
from typing import Callable

import numpy as np


class FeatureCache:
    def __init__(self, max_mb: int):
        self.max_bytes = max_mb * 1024**2
        self.items = OrderedDict()
        self.size = 0
        self.lock = RLock()

    def get(
        self,
        image: np.ndarray,
        build: Callable[[np.ndarray], np.ndarray],
    ) -> np.ndarray:
        key = self._key(image)
        with self.lock:
            found = self.items.get(key)
            if found is not None:
                self.items.move_to_end(key)
                return found

        value = build(image)
        if value.nbytes > self.max_bytes:
            return value
        value.setflags(write=False)

        with self.lock:
            found = self.items.get(key)
            if found is not None:
                self.items.move_to_end(key)
                return found
            while self.items and self.size + value.nbytes > self.max_bytes:
                _, removed = self.items.popitem(last=False)
                self.size -= removed.nbytes
            self.items[key] = value
            self.size += value.nbytes
        return value

    def clear(self) -> None:
        with self.lock:
            self.items.clear()
            self.size = 0

    @staticmethod
    def _key(image: np.ndarray) -> tuple:
        data = np.ascontiguousarray(image)
        digest = blake2b(data.view(np.uint8), digest_size=16).digest()
        return (*data.shape, data.dtype.str, digest)
