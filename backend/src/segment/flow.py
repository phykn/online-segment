from dataclasses import dataclass
import numpy as np
from scipy import ndimage as ndi


NAMES = ('normalized_flow_distance', 'normalized_endpoint_spread', 'flow_available')


@dataclass
class Endpoints:
    points: np.ndarray
    valid: np.ndarray


def trace(vectors, logits, threshold, niter, device):
    from cellpose.dynamics import follow_flows

    vectors = np.asarray(vectors, np.float32)
    if vectors.shape != (2, *logits.shape) or not np.isfinite(vectors).all():
        raise ValueError('Cellpose flow must be finite and match image geometry.')
    valid = logits > threshold
    points = np.zeros_like(vectors)
    indices = np.nonzero(valid)
    if len(indices[0]):
        result = follow_flows(vectors*valid/5., inds=indices, niter=niter, device=device)
        if hasattr(result, 'detach'):
            result = result.detach().cpu().numpy()
        points[:, indices[0], indices[1]] = result
    return Endpoints(points, valid)


def features(instances, endpoints):
    if (endpoints.points.shape != (2, *instances.shape) or endpoints.valid.shape != instances.shape
            or not np.isfinite(endpoints.points).all()):
        raise ValueError('Flow endpoints must be finite and match image geometry.')
    values = np.zeros((*instances.shape, len(NAMES)), np.float32)
    for idx, slices in enumerate(ndi.find_objects(instances), 1):
        if slices is None:
            continue
        mask = instances[slices] == idx
        valid = mask & endpoints.valid[slices]
        if not valid.any():
            continue
        radius = np.sqrt(np.count_nonzero(mask)/np.pi)
        points = endpoints.points[(slice(None), *slices)].astype(np.float64)
        y, x = np.indices(mask.shape)
        origin = np.array([slices[0].start, slices[1].start])[:, None, None]
        distance = np.linalg.norm(points-np.stack((y, x))-origin, axis=0)/radius
        # Centering prevents cancellation for images with large absolute coordinates.
        points -= points[:, valid].mean(axis=1)[:, None, None]
        sigma = max(.5, radius/6)
        weight = ndi.gaussian_filter(valid.astype(np.float64), sigma, mode='constant')
        variance = np.zeros(mask.shape, np.float64)
        for axis in points:
            mean = ndi.gaussian_filter(np.where(valid, axis, 0), sigma, mode='constant')/np.maximum(weight, 1e-12)
            square = ndi.gaussian_filter(np.where(valid, axis*axis, 0), sigma, mode='constant')/np.maximum(weight, 1e-12)
            variance += np.maximum(square-mean*mean, 0)
        region = values[slices]
        region[..., 0][valid] = distance[valid]
        region[..., 1][valid] = np.sqrt(variance[valid])/radius
        region[..., 2][valid] = 1
    return values
