import unittest
from unittest.mock import patch
import numpy as np
from src.config import config
from src.segment.model import Segmenter
from src.segment.dino import Level, Pyramid
from src.segment.prediction import infer


def pyramid(image, progress=None):
    rng = np.random.default_rng(0)
    return Pyramid([Level(rng.normal(size=(3, 4, 16)).astype(np.float16), (1., 1.)),
                    Level(rng.normal(size=(6, 8, 16)).astype(np.float16), (2., 2.))], image.shape[:2])


class ModelTests(unittest.TestCase):
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

    def test_every_class_up_to_the_last_is_sampled_for_training(self):
        model = Segmenter(); image = np.zeros((8, 8, 3), np.uint8); image[:, 4:] = 255
        labels = np.full((8, 8), -1, np.int8); labels[:, :2] = 7; labels[:, 6:] = 9
        with patch.object(config.feature, 'kind', 'image'):
            model.fit([(image, labels)])
        self.assertEqual(model.classifier.classes, [7, 9])
        self.assertEqual(len(model.classifier.counts), 10)
        self.assertTrue(model.classifier.counts[7] and model.classifier.counts[9])

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
            self.assertEqual(model.classifier.model.n_features_in_, 23)
            model.pca = object()
            with patch.object(config.feature, 'texture', True):
                model.configure(None)
                self.assertIsNone(model.pca)
                self.assertIsNone(model.classifier.model)
                self.assertEqual(model.features.size, 0)
                model.fit([(image, labels)])
                self.assertEqual(model.classifier.model.n_features_in_, 26)
                np.testing.assert_array_equal(next(iter(model.training.values()))[1], labels)

    def test_pca_is_shared_frozen_and_resets_with_configuration(self):
        model = Segmenter(); image = np.zeros((9, 11, 3), np.uint8)
        edits = np.zeros((9, 11), np.int8); edits[:, 5:] = 1
        with patch.object(config.feature, 'kind', 'dino'), patch('src.segment.model.dino.run', side_effect=pyramid) as run:
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
