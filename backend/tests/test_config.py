import unittest

from pydantic import ValidationError

from src.config import config, ExportConfig, FeatureConfig
from src.api.schema import Mask, PredRequest


class ConfigTests(unittest.TestCase):
    def test_region_finder_configuration_is_gone(self):
        for key in ('sam', 'model', 'cellpose'):
            self.assertNotIn(key, config.model_dump())
        for kind in ('encoder', 'hybrid'):
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                FeatureConfig(kind=kind)
        self.assertNotIn('cellpose', PredRequest.model_fields)

    def test_palette_channels_must_fit_in_png_bytes(self):
        for channel in [-1, 256]:
            with self.subTest(channel=channel), self.assertRaises(ValidationError):
                ExportConfig.model_validate({
                    **config.export.model_dump(),
                    'colors': [(channel, 0, 0)] * 10,
                })

    def test_masks_accept_ten_classes_matching_the_palette(self):
        self.assertEqual(len(config.export.colors), 10)
        Mask(width=3, height=1, runs=[(-1, 1), (0, 1), (9, 1)])
        for label in (-2, 10):
            with self.subTest(label=label), self.assertRaises(ValidationError):
                Mask(width=1, height=1, runs=[(label, 1)])
