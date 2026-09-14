import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch

from src.segment.encoder import EncoderCapture


class EncoderTests(unittest.TestCase):
    def model(self, channels):
        return SimpleNamespace(backbone={768: 'dino_vitb', 1024: 'dino_vitl'}[channels],
                               net=SimpleNamespace(ps=8, out=torch.nn.Linear(channels, 192)))

    def test_both_backbones_capture_only_spatial_tokens_without_changing_output(self):
        for channels in (768, 1024):
            model = self.model(channels)
            value = torch.randn(1, 16, channels)
            expected = model.net.out(value).detach()
            with EncoderCapture(model, (9, 11), (9, 11), 32, .1) as capture:
                actual = model.net.out(value).detach()
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
            tokens = capture.tokens()
            self.assertEqual(tokens.tiles[0].shape, (4, 4, channels))
            np.testing.assert_array_equal(tokens.tiles[0], value.numpy().reshape(4, 4, channels))
            self.assertEqual(len(model.net.out._forward_pre_hooks), 0)

    def test_failed_inference_removes_hook(self):
        model = self.model(768)
        with self.assertRaisesRegex(RuntimeError, 'inference failed'):
            with EncoderCapture(model, (9, 11), (9, 11), 32, .1):
                raise RuntimeError('inference failed')
        self.assertFalse(model.net.out._forward_pre_hooks)

    def test_version_and_geometry_fail_explicitly(self):
        model = self.model(768)
        with patch('src.segment.encoder.version', return_value='unknown'):
            from fastapi import HTTPException
            with self.assertRaises(HTTPException):
                with EncoderCapture(model, (9, 11), (9, 11), 32, .1):
                    pass
        with self.assertRaisesRegex(ValueError, 'token geometry'):
            with EncoderCapture(model, (9, 11), (9, 11), 32, .1):
                model.net.out(torch.randn(1, 21, 768))
        self.assertFalse(model.net.out._forward_pre_hooks)
