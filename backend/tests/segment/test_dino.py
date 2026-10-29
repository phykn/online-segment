import unittest
from unittest.mock import patch
import numpy as np
import torch
from fastapi import HTTPException
from pydantic import ValidationError
from sklearn.decomposition import PCA
from src.config import config, DinoConfig
from src.segment.dino import DinoEncoder, Level, Pyramid, PATCH, channels
from src.segment.feature import image_features, size_features
from src.segment.model import Segmenter


class PatchMean(torch.nn.Module):
    """Stand-in backbone whose token is the mean of its 16x16 patch, so geometry is checkable."""
    embed_dim = 3

    def get_intermediate_layers(self, x, n, reshape, norm):
        return [torch.nn.functional.avg_pool2d(x, PATCH)]


def ramp(h, w):
    y, x = np.mgrid[:h, :w].astype(np.float32)
    return np.stack([y/h, x/w, (y+x)/(h+w)], -1)


class Positional(PatchMean):
    """PatchMean plus a fixed pattern over in-tile token positions, like a magnified ViT tile."""
    def __init__(self, side):
        super().__init__()
        self.pattern = torch.from_numpy(np.random.default_rng(1).normal(size=(3, side, side)).astype(np.float32))

    def get_intermediate_layers(self, x, n, reshape, norm):
        return [super().get_intermediate_layers(x, n, reshape, norm)[0] + self.pattern]


class DinoTests(unittest.TestCase):
    def encode(self, x, scale, tile, overlap, model=None, debias=False):
        encoder = DinoEncoder(); encoder.device = 'cpu'
        with patch.object(config.dino, 'tile', tile), patch.object(config.dino, 'overlap', overlap), \
                patch.object(config.dino, 'debias', debias):
            return encoder.encode(model or PatchMean(), x, scale)

    def test_debiasing_removes_the_pattern_shared_by_all_tiles(self):
        x = np.random.default_rng(0).uniform(size=(96, 160, 3)).astype(np.float32)
        # The pattern's own mean cannot be told from a constant offset in the content and stays.
        centred = lambda level: level.grid.astype(np.float32) - level.grid.astype(np.float32).mean((0, 1))
        clean = centred(self.encode(x, 2, 64, 16))
        raw = centred(self.encode(x, 2, 64, 16, Positional(4)))
        fixed = centred(self.encode(x, 2, 64, 16, Positional(4), debias=True))
        self.assertLess(np.abs(fixed-clean).mean(), .1*np.abs(raw-clean).mean())
        # A single tile cannot separate the pattern from the content, so it is left alone.
        single = self.encode(x[:24, :24], 2, 64, 16, Positional(4), debias=True).grid
        np.testing.assert_array_equal(single, self.encode(x[:24, :24], 2, 64, 16, Positional(4)).grid)

    def test_overlapping_tiles_match_a_single_pass(self):
        x = ramp(70, 150)
        whole = self.encode(x, 2, 320, 0)
        tiled = self.encode(x, 2, 64, 32)
        self.assertEqual(whole.grid.shape, (9, 19, 3))
        np.testing.assert_allclose(tiled.grid.astype(np.float32), whole.grid.astype(np.float32), atol=2e-3)

    def test_pixels_land_on_their_own_location_at_every_scale(self):
        x = ramp(64, 96)
        idx = np.array([20*96+30, 40*96+60, 33*96+47])
        for scale in (2, 4, 8):
            with self.subTest(scale=scale):
                level = self.encode(x, scale, 512, 128)
                np.testing.assert_allclose(level.pixels(idx, 96), x.reshape(-1, 3)[idx], atol=1.5/scale/16+2e-3)

    def test_pyramid_projects_each_level_separately(self):
        grid = np.random.default_rng(0).normal(size=(4, 4, 6)).astype(np.float16)
        pyramid = Pyramid([Level(grid, (1., 1.)), Level(grid, (2., 2.))], (16, 16))
        class Half:
            def transform(self, value):
                return value[:, :3]
        values = pyramid.project([Half(), Half()]).pixels(np.arange(5))
        self.assertEqual(values.shape, (5, 6))
        self.assertEqual(pyramid.nbytes, 2*grid.nbytes)

    def test_projecting_tokens_before_interpolation_matches_interpolating_first(self):
        rng = np.random.default_rng(0)
        levels = [Level(rng.normal(size=(3, 4, 32)).astype(np.float16), (1., 1.)),
                  Level(rng.normal(size=(5, 7, 32)).astype(np.float16), (2., 2.))]
        pcas = [PCA(4).fit(level.grid.reshape(-1, 32).astype(np.float32)) for level in levels]
        idx = np.arange(40*56)
        expected = np.concatenate([pca.transform(level.pixels(idx, 56)) for level, pca in zip(levels, pcas)], axis=1)
        np.testing.assert_allclose(Pyramid(levels, (40, 56)).project(pcas).pixels(idx), expected, atol=1e-5)

    def test_enhanced_channels_keep_gray_first(self):
        image = (ramp(32, 32)*255).astype(np.uint8)
        values = channels(image, 'enhanced')
        self.assertEqual(values.shape, (32, 32, 3))
        np.testing.assert_allclose(values[..., 0], channels(image, 'rgb') @ np.array([.2126, .7152, .0722]), atol=1e-6)

    def test_limits_and_missing_weights_are_reported(self):
        with self.assertRaises(ValidationError):
            DinoConfig(tile=128, overlap=128)
        with patch.object(config.dino, 'max_tokens', 10), self.assertRaises(HTTPException) as error:
            self.encode(ramp(64, 64), 4, 512, 128)
        self.assertEqual(error.exception.status_code, 422)
        with patch.object(config.dino, 'checkpoint', 'weights/missing.pth'), self.assertRaises(HTTPException) as error:
            DinoEncoder().load()
        self.assertEqual(error.exception.status_code, 503)

    def test_segmenter_trains_on_dino_and_image_channels(self):
        rng = np.random.default_rng(0)
        image = np.zeros((24, 32, 3), np.uint8); image[:, 16:] = 200
        def run(img, progress):
            return Pyramid([Level(rng.normal(size=(3, 4, 8)).astype(np.float16), (1., 1.)),
                            Level(rng.normal(size=(6, 8, 8)).astype(np.float16), (2., 2.))], img.shape[:2])
        labels = np.full((24, 32), -1, np.int8); labels[:, :8] = 0; labels[:, 24:] = 1
        with patch.object(config.feature, 'kind', 'dino'), patch('src.segment.model.dino.run', side_effect=run) as encode:
            model = Segmenter()
            model.fit([(image, labels)])
            self.assertEqual(len(model.pca), 2)
            features = model.feature(image)
            width = image_features(image).shape[-1] + size_features(image).shape[-1] + 2*min(config.feature.components, 8)
            self.assertEqual(features.pixels(np.arange(3)).shape, (3, width))
            pred, _ = model.classifier.predict(features)
        self.assertEqual(encode.call_count, 1)
        self.assertTrue((pred[:, :8] == 0).all() and (pred[:, 24:] == 1).all())


if __name__ == '__main__':
    unittest.main()
