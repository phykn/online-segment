import base64
from io import BytesIO
from threading import RLock
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from src.config import config
from src.api.model import predict as api_predict
from src.api.schema import Mask, PredRequest, TrainingImage
from src.data.mask import decode, encode
from src.segment.classifier import Classifier, rebalance, refine
from src.segment.model import Segmenter
from src.segment.prediction import infer, predict


def fixture():
    image = np.zeros((32, 64, 3), np.uint8)
    image[:, 16:32] = 220
    image[:, 48:] = 220
    edits = np.full(image.shape[:2], -1, np.int8)
    edits[8:16, 4:12] = 1
    edits[8:16, 20:28] = 2
    return image, edits


def encoded(image):
    buf = BytesIO(); Image.fromarray(image).save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


def mask_payload(edits):
    return Mask.model_validate(encode(edits), from_attributes=True)


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch.object(config.feature, 'kind', 'image'); self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_a_quarter_of_the_trees_use_only_leading_image_channels(self):
        rng = np.random.default_rng(0)
        y = np.repeat([0, 1, 2], 60).astype(np.int8)
        x = np.concatenate([y[:, None] + rng.normal(0, .1, (180, 2)), rng.normal(size=(180, 6))], 1).astype(np.float32)
        used = lambda trees: np.unique(np.concatenate([tree.tree_.feature[tree.tree_.feature >= 0] for tree in trees]))
        classifier = Classifier()
        classifier.fit([(x, y)], local=2)
        trees = classifier.model.estimators_
        self.assertEqual(len(trees), 200)
        self.assertFalse((used(trees[150:]) >= 2).any())
        self.assertTrue((used(trees[:150]) >= 2).any())
        np.testing.assert_array_equal(classifier.model.predict(x), y)
        # With size channels in columns 2-3, token trees never see them and the size half (best
        # split thresholds, not random ones) never sees the tokens after them.
        classifier.fit([(x, y)], local=2, size=2)
        trees = classifier.model.estimators_
        self.assertEqual(len(trees), 200)
        self.assertFalse(np.isin(used(trees[:150]), [2, 3]).any())
        self.assertTrue((used(trees[:150]) >= 4).any())
        self.assertFalse((used(trees[150:]) >= 4).any())
        self.assertEqual({type(tree).__name__ for tree in trees}, {'ExtraTreeClassifier', 'DecisionTreeClassifier'})
        np.testing.assert_array_equal(classifier.model.predict(x), y)
        classifier.fit([(x, y)])
        self.assertEqual(len(classifier.model.estimators_), 200)

    def test_pixels_generalize_to_unlabeled_areas(self):
        image, edits = fixture(); segmenter = Segmenter()
        result = infer(image, segmenter, edits=edits)
        self.assertEqual(result[0][12, 40], 1)
        self.assertEqual(result[0][12, 56], 2)
        swapped = edits.copy(); swapped[edits == 1] = 2; swapped[edits == 2] = 1
        second = infer(image, segmenter, edits=swapped)
        self.assertEqual(second[0][12, 40], 2)
        self.assertEqual(second[0][12, 56], 1)
        self.assertEqual(result[2]['training_samples'], 16)
        self.assertEqual(result[2]['training_samples_by_class'], [0, 8, 8] + [0]*7)
        self.assertEqual(result[2]['message'], '')
        self.assertEqual(result[3], [])
        self.assertEqual(len(segmenter.features.values), 1)

    def test_class_zero_can_represent_the_same_material_as_any_other_class(self):
        image, edits = fixture()
        relabeled = np.full(edits.shape, -1, np.int8)
        relabeled[edits == 1] = 0; relabeled[edits == 2] = 3
        result = infer(image, Segmenter(), edits=relabeled)
        self.assertEqual(result[0][12, 40], 0)
        self.assertEqual(result[0][12, 56], 3)
        self.assertEqual(result[2]['classes'], [0, 3])
        self.assertEqual(result[2]['message'], '')

    def test_snapshot_trains_across_images_and_removes_deleted_examples(self):
        image, edits = fixture(); target = image.copy(); target[0, 0] = 1
        segmenter = Segmenter(); session = SimpleNamespace(lock=RLock(), segmenter=segmenter)
        payload = PredRequest(image=encoded(target), training=[TrainingImage(image=encoded(image), edits=mask_payload(edits))])
        response = api_predict(payload, session)
        self.assertEqual(decode(response.mask)[12, 56], 2)
        self.assertEqual(response.summary['training_samples'], 16)
        payload.training = []
        response = api_predict(payload, session)
        self.assertTrue((decode(response.mask) == -1).all())
        self.assertEqual(segmenter.training, {})

    def test_rebalance_shrinks_a_class_the_image_rarely_shows(self):
        probs = np.array([[.5, .5], [.9, .1], [.9, .1], [.9, .1]], np.float32)
        out = rebalance(probs)
        self.assertEqual(out[0].argmax(), 0)
        self.assertLess(out[0, 1], .5)
        np.testing.assert_allclose(out.sum(1), 1, rtol=1e-6)
        even = np.array([[.6, .4], [.4, .6]], np.float32)
        np.testing.assert_allclose(rebalance(even), even, rtol=1e-6)

    def test_refine_moves_a_blurred_class_edge_onto_the_brightness_edge(self):
        gray = np.zeros((16, 16), np.float32); gray[:, 8:] = 1
        ramp = np.clip((np.arange(16)-4.5)/8, 0, 1).astype(np.float32)
        p = np.broadcast_to(ramp, (16, 16))
        probs = np.stack([1-p, p], -1).reshape(-1, 2)
        out = refine(probs, gray).reshape(16, 16, 2)[..., 1]
        self.assertGreater(out[8, 8]-out[8, 7], p[8, 8]-p[8, 7])
        self.assertLess(out[8, 7], .5)
        self.assertGreater(out[8, 8], .5)

    def test_export_reuses_forest_and_matches_preview(self):
        image, edits = fixture(); segmenter = Segmenter()
        preview = infer(image, segmenter, edits=edits)[0]
        model = segmenter.classifier.model
        np.testing.assert_array_equal(preview, predict(image, segmenter, edits=edits))
        edits[0, 0] = 3
        np.testing.assert_array_equal(preview, predict(image, segmenter, edits=edits))
        self.assertIs(segmenter.classifier.model, model)

    def test_conflicting_pixels_and_background_are_individual_examples(self):
        image, edits = fixture(); edits[8:10, 4:8] = 0
        segmenter = Segmenter()
        result = infer(image, segmenter, edits=edits)
        self.assertEqual(result[2]['classes'], [0, 1, 2])
        self.assertEqual(result[2]['training_samples_by_class'], [4, 8, 8] + [0]*7)
        self.assertEqual(result[2]['message'], '')
        raw, unclear = segmenter.classifier.predict(segmenter.feature(image))
        np.testing.assert_array_equal(result[0], raw)
        np.testing.assert_array_equal(result[1], unclear)

    def test_conflicting_brush_examples_do_not_force_labels_or_certainty(self):
        image = np.full((16, 16, 3), 128, np.uint8)
        edits = np.full((16, 16), -1, np.int8); edits[4, 4:8] = 0; edits[10, 4:8] = 1
        segmenter = Segmenter(); result = infer(image, segmenter, edits=edits)
        # Equal input features cannot explain conflicting labels: preserve RF disagreement.
        self.assertTrue(np.any(result[0][edits >= 0] != edits[edits >= 0]))
        self.assertTrue((result[1][edits >= 0] == 1).all())
        self.assertEqual(result[2]['training_samples_by_class'], [4, 4] + [0]*8)
        np.testing.assert_array_equal(result[0], predict(image, segmenter, edits=edits))

    def test_single_class_and_erasure_do_not_flood_image(self):
        image, edits = fixture(); edits[edits == 2] = -1; model = Segmenter()
        result = infer(image, model, edits=edits)
        self.assertTrue((result[0] == -1).all())
        self.assertTrue(result[2]['message'])
        erased = infer(image, model, edits=np.full(edits.shape, -1, np.int8))
        self.assertTrue((erased[0] == -1).all())
        self.assertEqual(erased[2]['training_samples'], 0)

    def test_one_class_does_not_run_dino_or_fit_pca(self):
        image, edits = fixture(); edits[edits == 2] = -1; model = Segmenter()
        with patch.object(config.feature, 'kind', 'dino'), patch('src.segment.model.dino.run') as run:
            self.assertTrue((infer(image, model, edits=edits)[0] == -1).all())
            run.assert_not_called()
            self.assertIsNone(model.pca)
