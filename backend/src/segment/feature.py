from dataclasses import dataclass
import numpy as np
from scipy.ndimage import gaussian_filter, sobel, uniform_filter
from src.segment.context import Context
from src.segment.encoder import Tokens


def image_features(image):
    rgb = image.astype(np.float32) / 255
    gray = rgb @ np.array([.2126, .7152, .0722], np.float32)
    low, high = np.percentile(gray, [1, 99])
    gray = np.clip((gray-low)/(high-low), 0, 1) if high > low else np.zeros_like(gray)
    scale = min(gray.shape) / 512
    values = [gray]
    for factor in (1., 2., 4.):
        sigma = np.float32(np.clip(factor * scale, .5, 32))
        smooth = gaussian_filter(gray, sigma, mode='reflect')
        values.extend([smooth, np.hypot(sobel(smooth, axis=1), sobel(smooth, axis=0))])
        hxx = gaussian_filter(gray, sigma, order=(0, 2), mode='reflect')
        hxy = gaussian_filter(gray, sigma, order=(1, 1), mode='reflect')
        hyy = gaussian_filter(gray, sigma, order=(2, 0), mode='reflect')
        delta = np.sqrt((hxx-hyy)**2 + 4*hxy**2)
        values.extend([.5*(hxx+hyy+delta), .5*(hxx+hyy-delta)])
    for factor in (8., 16., 32.):
        values.append(gray-uniform_filter(gray, size=int(round(factor*scale))*2+1, mode='reflect'))
    return np.stack(values, axis=-1).astype(np.float32)


@dataclass
class Features:
    shape: tuple
    local: np.ndarray | None = None
    tokens: Tokens | None = None
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
