import unittest

from pydantic import ValidationError

from src.config import config, CellposeConfig, ExportConfig
from src.api.schema import PredRequest


class ConfigTests(unittest.TestCase):
    def test_cellpose_replaces_sam_configuration(self):
        self.assertEqual(config.cellpose.checkpoint, 'weights/cpdino-vitb.pth')
        self.assertEqual(config.cellpose.tile_size, 384)
        for key in ('sam', 'model'):
            self.assertNotIn(key, config.model_dump())

    def test_invalid_threshold_and_tile_settings_rejected(self):
        for value in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValidationError):
                PredRequest(image='x', diameter=value)
        for settings in [dict(overlap=1), dict(tile_size=383), dict(batch_size=0),
                         dict(flow_threshold=float('nan')), dict(min_area=0)]:
            with self.subTest(settings=settings), self.assertRaises(ValidationError):
                CellposeConfig(checkpoint='x', **settings)

    def test_palette_channels_must_fit_in_png_bytes(self):
        for channel in [-1, 256]:
            with self.subTest(channel=channel), self.assertRaises(ValidationError):
                ExportConfig.model_validate({
                    **config.export.model_dump(),
                    'colors': [(channel, 0, 0)] * 4,
                })

    def test_invalid_web_cellpose_settings_are_rejected(self):
        for settings in ({'diameter': 0}, {'diameter': float('nan')}, {'min_area': 0},
                         {'min_area': 1.5}, {'flow_threshold': -1}, {'cellprob_threshold': float('inf')}):
            with self.subTest(settings=settings), self.assertRaises(ValidationError):
                PredRequest(image='x', cellpose=settings)
