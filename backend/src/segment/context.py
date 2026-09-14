"""Image-only Cellpose evidence for pixel classification; never consumes user labels."""
from dataclasses import dataclass
import numpy as np
from scipy import ndimage as ndi
from scipy.special import expit
from src.segment.flow import features as flow_features


NAMES = ('foreground_probability', 'instance_present', 'signed_boundary_distance',
         'minor_axis', 'major_axis', 'axis_ratio',
         'box_fill', 'boundary_ratio', 'mean_foreground_probability',
         'image_edge', 'mean_brightness', 'brightness_std', 'area')


@dataclass
class Context:
    instances: np.ndarray
    probability: np.ndarray
    distance: np.ndarray
    table: np.ndarray
    flow: np.ndarray | None = None

    @property
    def nbytes(self):
        return (self.instances.nbytes + self.probability.nbytes + self.distance.nbytes + self.table.nbytes
                + (self.flow.nbytes if self.flow is not None else 0))

    def pixels(self, indices, scale=1., mode='statistics'):
        score = self.probability.ravel()[indices, None]
        if mode == 'foreground':
            return score
        ids = self.instances.ravel()[indices]
        stats = self.table[ids].copy()
        stats[:, :2] *= scale
        stats[:, -1] *= scale**2
        values = [score, ids > 0, self.distance.ravel()[indices]*scale, stats]
        if self.flow is not None:
            values.append(self.flow.reshape(-1, self.flow.shape[-1])[indices])
        return np.column_stack(values).astype(np.float32)


def extract(image, masks, logits, endpoints=None):
    if masks.ndim != 2 or masks.shape != logits.shape or masks.shape != image.shape[:2]:
        raise ValueError('Cellpose context must match image geometry.')
    if not np.issubdtype(masks.dtype, np.integer) or np.any(masks < 0) or not np.isfinite(logits).all():
        raise ValueError('Invalid Cellpose context values.')
    ids, inverse = np.unique(masks, return_inverse=True)
    mapping = np.arange(len(ids), dtype=np.int32) + int(ids[0] != 0)
    instances = mapping[inverse].reshape(masks.shape)
    probability = expit(logits.astype(np.float32))
    table = np.zeros((int(instances.max())+1, 10), np.float32)
    distance = np.zeros(masks.shape, np.float32)
    if instances.any():
        distance[:] = -ndi.distance_transform_edt(instances == 0)
    gray = image.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32) / 255
    for idx, slices in enumerate(ndi.find_objects(instances), 1):
        if slices is None:
            continue
        mask = instances[slices] == idx
        yy, xx = np.where(mask)
        area = len(xx)
        coordinates = np.stack((xx-xx.mean(), yy-yy.mean()))
        axes = 4*np.sqrt(np.maximum(np.linalg.eigvalsh(coordinates @ coordinates.T / area), 0)+1/12)
        boundary = np.count_nonzero(mask & ~ndi.binary_erosion(mask))
        intensity = gray[slices][mask]
        edge = (slices[0].start == 0 or slices[1].start == 0 or
                slices[0].stop == masks.shape[0] or slices[1].stop == masks.shape[1])
        table[idx] = (*axes, axes[0]/axes[1], area/mask.size,
                      boundary/np.sqrt(area), probability[slices][mask].mean(), edge,
                      intensity.mean(), intensity.std(), area)
        inside = ndi.distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]
        distance[slices][mask] = inside[mask]
    flow = flow_features(instances, endpoints) if endpoints is not None else None
    return Context(instances, probability, distance, table, flow)
