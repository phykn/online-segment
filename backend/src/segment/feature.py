from dataclasses import dataclass
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter, sobel, uniform_filter
from src.segment.context import Context
from src.segment.encoder import Tokens
from src.segment.dino import Pyramid


def luminance(image):
    gray = image.astype(np.float32) / 255 @ np.array([.2126, .7152, .0722], np.float32)
    low, high = np.percentile(gray, [.5, 99.5])
    if high <= low:
        return np.zeros_like(gray)
    # Above the black level, detector gain and gamma become an offset and a factor in log space,
    # which the z-score removes, so brightness/contrast settings do not move the trees' thresholds.
    value = np.log(np.maximum(gray-low, 0) + .05*(high-low))
    std = value.std()
    return (np.clip((value-value.mean())/std, -3, 3)/6 + .5).astype(np.float32) if std > 0 else np.zeros_like(gray)


def image_features(image, texture=False):
    gray = luminance(image)
    scale = min(gray.shape) / 512
    base = np.clip(scale, .5, 8)
    values = [gray]
    for factor in (1., 2., 4.):
        sigma = np.float32(factor * base)
        smooth = gaussian_filter(gray, sigma, mode='reflect')
        values.extend([smooth, np.hypot(sobel(smooth, axis=1), sobel(smooth, axis=0))])
        hxx = gaussian_filter(gray, sigma, order=(0, 2), mode='reflect')
        hxy = gaussian_filter(gray, sigma, order=(1, 1), mode='reflect')
        hyy = gaussian_filter(gray, sigma, order=(2, 0), mode='reflect')
        delta = np.sqrt((hxx-hyy)**2 + 4*hxy**2)
        values.extend([.5*(hxx+hyy+delta), .5*(hxx+hyy-delta)])
    radius = max(1, int(round(8*scale)))
    textures = []
    for factor in (1, 2, 4):
        size = radius*factor*2+1
        mean = uniform_filter(gray, size=size, mode='reflect')
        values.append(gray-mean)
        if texture:
            variance = uniform_filter(gray*gray, size=size, mode='reflect')-mean*mean
            textures.append(np.sqrt(np.maximum(variance, 0)))
    values.extend(textures)
    return np.stack(values, axis=-1).astype(np.float32)


def size_features(image):
    """Grayscale openings by disks whose radius doubles every two channels. Wherever a disk fits
    inside a bright structure, its pixels keep about their own brightness out to the rim; smaller
    structures drop to their surroundings. Particles thus part by what fits inside them, not by
    their edges, which look alike on a large particle's rim and on a small grain."""
    gray = luminance(image)
    base = np.clip(min(gray.shape) / 512, .5, 8)
    smooth = gaussian_filter(gray, np.float32(base), mode='reflect')
    values = []
    # Seven channels at every image size, so features of differently sized images stack.
    for step in range(7):
        radius = max(1, int(round(base * 2**(1 + step/2))))
        disk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1))
        values.append(cv2.morphologyEx(smooth, cv2.MORPH_OPEN, disk))
    return np.stack(values, axis=-1).astype(np.float32)


@dataclass
class Features:
    shape: tuple
    local: np.ndarray | None = None
    tokens: Tokens | Pyramid | None = None
    context: Context | None = None
    scale: float = 1.
    context_mode: str = 'statistics'
    size: np.ndarray | None = None

    @property
    def nbytes(self):
        return sum(value.nbytes for value in (self.local, self.size, self.tokens, self.context) if value is not None)

    def pixels(self, indices):
        values = []
        if self.local is not None:
            values.append(self.local.reshape(-1, self.local.shape[-1])[indices])
        if self.size is not None:
            values.append(self.size.reshape(-1, self.size.shape[-1])[indices])
        if self.tokens is not None:
            values.append(self.tokens.pixels(indices))
        if self.context is not None:
            values.append(self.context.pixels(indices, self.scale, self.context_mode))
        return np.concatenate(values, axis=1) if len(values) > 1 else values[0]
