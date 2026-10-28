from dataclasses import dataclass
import numpy as np
from scipy.ndimage import gaussian_filter, sobel, uniform_filter
from src.segment.context import Context
from src.segment.encoder import Tokens
from src.segment.dino import Pyramid


def luminance(image):
    gray = image.astype(np.float32) / 255 @ np.array([.2126, .7152, .0722], np.float32)
    low, high = np.percentile(gray, [1, 99])
    return np.clip((gray-low)/(high-low), 0, 1) if high > low else np.zeros_like(gray)


def pixel_features(image):
    """Pixel-exact companions to DINO tokens, which cannot place edges finer than their stride."""
    gray = luminance(image)
    # Brightness relative to fine, local and wide surroundings separates small grains from their matrix.
    return np.stack([gray] + [gray-gaussian_filter(gray, sigma, mode='reflect') for sigma in (1, 4, 16)],
                    axis=-1).astype(np.float32)


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


@dataclass
class Features:
    shape: tuple
    local: np.ndarray | None = None
    tokens: Tokens | Pyramid | None = None
    context: Context | None = None
    scale: float = 1.
    context_mode: str = 'statistics'

    @property
    def nbytes(self):
        return sum(value.nbytes for value in (self.local, self.tokens, self.context) if value is not None)

    def pixels(self, indices):
        values = []
        if self.local is not None:
            values.append(self.local.reshape(-1, self.local.shape[-1])[indices])
        if self.tokens is not None:
            values.append(self.tokens.pixels(indices))
        if self.context is not None:
            values.append(self.context.pixels(indices, self.scale, self.context_mode))
        return np.concatenate(values, axis=1) if len(values) > 1 else values[0]
