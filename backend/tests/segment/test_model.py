import unittest
from unittest.mock import patch
import numpy as np
from src.config import config
from src.segment.model import Segmenter
from src.segment.encoder import Tokens
from src.segment.flow import Endpoints
from src.segment.prediction import infer


class ModelTests(unittest.TestCase):
    def setUp(self):
        context = patch.object(config.feature, 'cellpose', 'none'); context.start()
        self.addCleanup(context.stop)

    def test_feature_cache_changes_with_pixels_and_does_not_erase_training(self):
        model = Segmenter(); image = np.zeros((8, 8, 3), np.uint8)
        with patch.object(config.feature, 'kind', 'image'):
            one = model.feature(image)
            self.assertIs(model.feature(image.copy()), one)
            self.assertIsNot(model.feature(image+1), one)
            labels = np.zeros((8, 8), np.int8); labels[4:] = 1
            model.fit([(image, labels)])
            model.features.clear()
            self.assertEqual(len(model.training), 1)
            self.assertIsNotNone(model.classifier.model)
            model.clear()
            self.assertEqual(model.features.size, 0)
            self.assertEqual(model.training, {})

    def test_proposals_and_pca_context_share_one_forward_and_reset_together(self):
        model = Segmenter(); image = np.zeros((9, 11, 3), np.uint8)
        raw = Tokens([np.random.default_rng(0).normal(size=(48, 48, 1024)).astype(np.float32)],
                     (9, 11), [(0, 0)], (187, 188, 186, 187), 384)
        masks = np.ones((9, 11), np.int32); logits = np.zeros(masks.shape, np.float32)
        edits = np.zeros((9, 11), np.int8); edits[:, 5:] = 1
        endpoints = Endpoints(np.indices(masks.shape).astype(np.float32), masks > 0)
        with patch.object(config.feature, 'kind', 'hybrid'), patch.object(config.feature, 'cellpose', 'statistics'), patch('src.segment.model.runtime.run', return_value=(masks, logits, raw, endpoints)) as run:
            model.configure(None)
            model.propose(image)
            model.fit([(image, edits)])
            self.assertEqual(model.classifier.model.n_features_in_, 96)
            pca = model.pca
            model.fit([(image, 1-edits)])
            model.features.clear()
            model.feature(image)
            self.assertIs(model.pca, pca)
            run.assert_called_once()
            self.assertTrue(run.call_args.kwargs['capture'])
            self.assertTrue(run.call_args.kwargs['flow'])
            with patch.object(config.feature, 'cellpose', 'foreground'):
                model.configure(None)
            self.assertIsNone(model.pca)
            self.assertIsNone(model.classifier.model)
            self.assertEqual(model.training, {})

    def test_flow_switch_resets_shared_models_and_retrains_without_flow_channels(self):
        image = np.zeros((16, 16, 3), np.uint8)
        masks = np.ones((16, 16), np.int32)
        logits = np.ones(masks.shape, np.float32)
        labels = np.zeros_like(masks, np.int8); labels[:, 8:] = 1
        endpoints = Endpoints(np.indices(masks.shape).astype(np.float32), masks > 0)
        model = Segmenter()
        with patch.object(config.feature, 'kind', 'image'), patch.object(config.feature, 'cellpose', 'statistics'), \
                patch.object(config.feature, 'flow', True), patch('src.segment.model.runtime.run') as run:
            run.side_effect = lambda *args, **kw: (masks, logits, None, endpoints if kw['flow'] else None)
            model.configure(None)
            model.fit([(image, labels)])
            self.assertEqual(model.classifier.model.n_features_in_, 32)
            model.pca = object()
            with patch.object(config.feature, 'flow', False):
                model.configure(None)
                self.assertIsNone(model.pca)
                self.assertIsNone(model.classifier.model)
                self.assertEqual(model.features.size, 0)
                model.fit([(image, labels)])
                self.assertEqual(model.classifier.model.n_features_in_, 29)
                self.assertFalse(run.call_args.kwargs['flow'])

    def test_failed_feature_is_not_cached(self):
        model = Segmenter(); image = np.zeros((8, 8, 3), np.uint8)
        with patch.object(config.feature, 'kind', 'image'), patch('src.segment.model.image_features', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError): model.feature(image)
            self.assertEqual(model.features.size, 0)

    def test_texture_setting_resets_features_pca_and_forest_but_can_retrain_labels(self):
        model = Segmenter()
        image = np.random.default_rng(1).integers(0, 256, (32, 32, 3), dtype=np.uint8)
        labels = np.zeros((32, 32), np.int8); labels[:, 16:] = 1
        with patch.object(config.feature, 'kind', 'image'), patch.object(config.feature, 'texture', False):
            model.configure(None)
            model.fit([(image, labels)])
            self.assertEqual(model.classifier.model.n_features_in_, 16)
            model.pca = object()
            with patch.object(config.feature, 'texture', True):
                model.configure(None)
                self.assertIsNone(model.pca)
                self.assertIsNone(model.classifier.model)
                self.assertEqual(model.features.size, 0)
                model.fit([(image, labels)])
                self.assertEqual(model.classifier.model.n_features_in_, 19)
                np.testing.assert_array_equal(next(iter(model.training.values()))[1], labels)

    def test_pca_is_shared_frozen_and_resets_with_configuration(self):
        model = Segmenter(); image = np.zeros((9, 11, 3), np.uint8)
        raw = Tokens([np.random.default_rng(0).normal(size=(48, 48, 1024)).astype(np.float32)],
                     (9, 11), [(0, 0)], (187, 188, 186, 187), 384)
        edits = np.zeros((9, 11), np.int8); edits[:, 5:] = 1
        with patch.object(config.feature, 'kind', 'encoder'), patch('src.segment.model.runtime.run', return_value=(None, None, raw, None)) as run:
            model.configure(None)
            model.fit([(image, edits)])
            pca = model.pca
            first = infer(image, model, train=False)[0]
            model.fit([(image, 1-edits)])
            self.assertIs(model.pca, pca)
            self.assertEqual(run.call_count, 1)
            model.features.clear()
            second = infer(image, model, train=False)[0]
            np.testing.assert_array_equal(second, 1-first)
            model.fit([(image+1, edits)])
            self.assertIs(model.pca, pca)
            model.configure(20)
            self.assertIsNone(model.pca)
            self.assertIsNone(model.classifier.model)
            self.assertEqual(model.training, {})
