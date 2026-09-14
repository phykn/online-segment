import unittest
from unittest.mock import patch
import numpy as np
import torch
from src.segment.flow import Endpoints, features, trace
from src.segment.context import extract


def disk(size=41, radius=12):
    y, x = np.indices((size, size))
    center = (size-1)/2
    mask = ((y-center)**2+(x-center)**2 <= radius**2).astype(np.int32)
    points = np.full((2, size, size), center, np.float32)
    return mask, Endpoints(points, mask > 0)


class FlowTests(unittest.TestCase):
    def test_real_flow_integration_converges_and_respects_foreground(self):
        masks, endpoints = disk(21, 6)
        vectors = (endpoints.points-np.indices(masks.shape))*.5
        logits = np.where(masks > 0, 1., -1.)
        traced = trace(vectors, logits, 0, 150, torch.device('cpu'))
        np.testing.assert_allclose(traced.points[:, traced.valid], 10, atol=.01)
        np.testing.assert_array_equal(traced.valid, masks > 0)
        self.assertTrue((traced.points[:, ~traced.valid] == 0).all())
        with patch('cellpose.dynamics.follow_flows') as follow:
            empty = trace(vectors, logits, 2, 150, torch.device('cpu'))
            follow.assert_not_called()
            self.assertFalse(empty.valid.any())

    def test_center_and_edge_have_distances_but_same_endpoint_has_no_spread(self):
        masks, endpoints = disk()
        values = features(masks, endpoints)
        self.assertEqual(values[20, 20, 0], 0)
        self.assertGreater(values[20, 30, 0], .8)
        self.assertLess(values[..., 1].max(), 1e-6)
        np.testing.assert_array_equal(values[..., 2], masks > 0)
        self.assertTrue((values[masks == 0] == 0).all())

    def test_rotation_translation_and_isotropic_scale(self):
        masks, endpoints = disk()
        endpoints.points[0] += np.indices(masks.shape)[1]*.05
        original = features(masks, endpoints)
        rotated = np.stack((40-np.rot90(endpoints.points[1]), np.rot90(endpoints.points[0])))
        actual = features(np.rot90(masks), Endpoints(rotated, np.rot90(endpoints.valid)))
        np.testing.assert_allclose(actual, np.rot90(original), atol=1e-6)
        shifted = np.pad(masks, ((7, 3), (11, 2)))
        points = np.pad(endpoints.points, ((0, 0), (7, 3), (11, 2)))
        points += np.array([7, 11])[:, None, None]
        actual = features(shifted, Endpoints(points, shifted > 0))
        np.testing.assert_allclose(actual[7:48, 11:52], original, atol=1e-6)
        small, small_endpoints = disk(21, 6)
        large, large_endpoints = disk(41, 12)
        a, b = features(small, small_endpoints), features(large, large_endpoints)
        np.testing.assert_allclose(a[10, 13], b[20, 26], rtol=.03, atol=1e-6)
        small_endpoints.points = (small_endpoints.points+np.indices(small.shape))/2
        large_endpoints.points = (large_endpoints.points+np.indices(large.shape))/2
        a, b = features(small, small_endpoints), features(large, large_endpoints)
        self.assertGreater(a[10, 10, 1], .1)
        np.testing.assert_allclose(a[10, 10, 1], b[20, 20, 1], rtol=.03)

    def test_endpoint_disagreement_is_visible_without_crossing_instance_boundaries(self):
        masks = np.ones((25, 30), np.int32)
        points = np.zeros((2, 25, 30), np.float32)
        points[0] = 12; points[1, :, :15] = 7; points[1, :, 15:] = 22
        endpoints = Endpoints(points, masks > 0)
        mixed = features(masks, endpoints)
        self.assertGreater(mixed[12, 14, 1], .2)
        masks[:, 15:] = 2
        separated = features(masks, endpoints)
        self.assertLess(separated[..., 1].max(), 1e-6)

    def test_missing_endpoints_are_distinct_from_a_valid_center_and_cache_counts_bytes(self):
        masks, endpoints = disk()
        endpoints.valid[20, 21] = False
        image = np.zeros((*masks.shape, 3), np.uint8)
        context = extract(image, masks, np.ones(masks.shape), endpoints)
        indices = np.array([20*41+20, 20*41+21])
        one = context.pixels(indices)
        two = context.pixels(indices, scale=3)
        self.assertEqual(one.shape[1], 16)
        np.testing.assert_array_equal(one[:, -3:], two[:, -3:])
        np.testing.assert_array_equal(one[:, -1], [1, 0])
        self.assertTrue((one[1, -3:] == 0).all())
        baseline = extract(image, masks, np.ones(masks.shape))
        self.assertEqual(context.nbytes-baseline.nbytes, context.flow.nbytes)
        self.assertEqual(context.pixels(indices, mode='foreground').shape[1], 1)

    def test_invalid_flow_geometry_is_rejected(self):
        masks, endpoints = disk()
        with self.assertRaises(ValueError):
            trace(np.zeros((2, 3, 4)), np.zeros((4, 4)), 0, 10, torch.device('cpu'))
        endpoints.points[0, 0, 0] = np.nan
        with self.assertRaises(ValueError): features(masks, endpoints)
