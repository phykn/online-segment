import base64
from io import BytesIO
from threading import RLock
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from src.config import config, CellposeParameters
from src.api.model import predict as api_predict, proposals
from src.api.schema import Mask, PredRequest, TrainingImage, ProposalRequest
from src.data.mask import decode, encode
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
        context = patch.object(config.feature, 'cellpose', 'none'); context.start()
        self.addCleanup(context.stop)

    def test_pixels_generalize_inside_one_proposal_and_outside_proposals(self):
        image, edits = fixture(); segmenter = Segmenter()
        with patch('src.segment.model.runtime.run') as run:
            result = infer(image, segmenter, edits=edits)
            self.assertEqual(result[0][12, 40], 1)
            self.assertEqual(result[0][12, 56], 2)
            swapped = edits.copy(); swapped[edits == 1] = 2; swapped[edits == 2] = 1
            second = infer(image, segmenter, edits=swapped)
            self.assertEqual(second[0][12, 40], 2)
            self.assertEqual(second[0][12, 56], 1)
            self.assertEqual(result[2]['training_samples'], 128)
            self.assertEqual(result[2]['training_samples_by_class'], [0, 64, 64, 0])
            self.assertEqual(result[2]['message'], '')
            self.assertEqual(result[3], [])
            run.assert_not_called()
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
        self.assertEqual(response.summary['training_samples'], 128)
        payload.training = []
        response = api_predict(payload, session)
        self.assertTrue((decode(response.mask) == -1).all())
        self.assertEqual(segmenter.training, {})

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
        self.assertEqual(result[2]['training_samples_by_class'], [8, 56, 64, 0])
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
        self.assertEqual(result[2]['training_samples_by_class'], [4, 4, 0, 0])
        np.testing.assert_array_equal(result[0], predict(image, segmenter, edits=edits))

    def test_single_class_and_erasure_do_not_flood_image(self):
        image, edits = fixture(); edits[edits == 2] = -1; model = Segmenter()
        result = infer(image, model, edits=edits)
        self.assertTrue((result[0] == -1).all())
        self.assertTrue(result[2]['message'])
        erased = infer(image, model, edits=np.full(edits.shape, -1, np.int8))
        self.assertTrue((erased[0] == -1).all())
        self.assertEqual(erased[2]['training_samples'], 0)

    def test_proposal_ids_above_int8_range_are_preserved_and_never_train(self):
        image, _ = fixture(); model = Segmenter(); session = SimpleNamespace(lock=RLock(), segmenter=model)
        ids = np.arange(image.shape[0]*image.shape[1], dtype=np.int32).reshape(image.shape[:2])
        with patch('src.segment.model.runtime.run', return_value=(ids, np.zeros(ids.shape, np.float32), None)) as run:
            response = proposals(ProposalRequest(image=encoded(image)), session)
            self.assertEqual(response.runs, [(i, 1) for i in range(ids.size)])
            proposals(ProposalRequest(image=encoded(image)), session)
            self.assertEqual(run.call_count, 1)
        self.assertEqual(model.training, {})
        self.assertIsNone(model.classifier.model)

    def test_statistics_are_cached_and_do_not_lock_pixel_classes_to_instances(self):
        image, edits = fixture(); model = Segmenter()
        ids = np.zeros(edits.shape, np.int32); ids[:, :32] = 1000
        logits = np.zeros(edits.shape, np.float32)
        with patch.object(config.feature, 'cellpose', 'statistics'), patch('src.segment.model.runtime.run', return_value=(ids, logits, None)) as run:
            model.propose(image)
            first = infer(image, model, edits=edits)[0]
            # Different pixels of one proposed particle, and both classes outside it.
            self.assertEqual(first[20, 8], 1); self.assertEqual(first[20, 24], 2)
            self.assertEqual(first[20, 40], 1); self.assertEqual(first[20, 56], 2)
            second = infer(image, model, edits=np.where(edits >= 0, 3-edits, -1))[0]
            self.assertEqual(second[20, 40], 2); self.assertEqual(second[20, 56], 1)
            model.features.clear()
            np.testing.assert_array_equal(second, infer(image, model, train=False)[0])
            self.assertEqual(run.call_count, 1)

    def test_one_class_does_not_run_cellpose_or_fit_pca(self):
        image, edits = fixture(); edits[edits == 2] = -1; model = Segmenter()
        with patch.object(config.feature, 'kind', 'hybrid'), patch.object(config.feature, 'cellpose', 'statistics'), patch('src.segment.model.runtime.run') as run:
            self.assertTrue((infer(image, model, edits=edits)[0] == -1).all())
            run.assert_not_called()
            self.assertIsNone(model.pca)

    def test_parameter_changes_refresh_features_and_retrain_from_the_same_labels_per_session(self):
        image, edits = fixture(); model = Segmenter(); other = Segmenter()
        session = SimpleNamespace(lock=RLock(), segmenter=model)
        parameters = CellposeParameters(diameter=15, cellprob_threshold=-1, flow_threshold=.6, min_area=3)
        ids = np.ones(edits.shape, np.int32); logits = np.ones(edits.shape, np.float32)
        payload = PredRequest(image=encoded(image), cellpose=parameters, edits=mask_payload(edits),
                              training=[TrainingImage(image=encoded(image), edits=mask_payload(edits))])
        with patch.object(config.feature, 'cellpose', 'statistics'), patch('src.segment.model.runtime.run', return_value=(ids, logits, None)) as run:
            proposals(ProposalRequest(image=encoded(image), cellpose=parameters), session)
            first = api_predict(payload, session)
            self.assertEqual(first.summary['training_samples'], 128)
            self.assertEqual(run.call_count, 1)
            payload.cellpose = parameters.model_copy(update={'flow_threshold': .8})
            second = api_predict(payload, session)
            self.assertEqual(second.summary['training_samples'], 128)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.kwargs['parameters'].flow_threshold, .8)
            self.assertEqual(model.parameters.diameter, 15)
            self.assertIsNone(other.parameters.diameter)
            self.assertEqual(other.parameters.flow_threshold, config.cellpose.flow_threshold)
