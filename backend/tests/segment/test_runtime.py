import unittest
from unittest.mock import Mock, patch
import numpy as np
from fastapi import HTTPException
from src.config import config, CellposeParameters
from src.segment.runtime import CellposeRuntime


class RuntimeTests(unittest.TestCase):
    def model(self):
        runtime = CellposeRuntime(); runtime.model = Mock()
        runtime.load = Mock(return_value=runtime.model)
        runtime.model.eval.side_effect = lambda image, **kw: (np.zeros(image.shape[:2], np.int32), [None, None, np.ones(image.shape[:2])], None)
        return runtime

    def test_one_pass_receives_original_rgb_without_enlargement(self):
        runtime = self.model(); image = np.zeros((9, 11, 3), np.uint8); states = []
        runtime.run(image, progress=lambda **state: states.append(state))
        self.assertEqual(runtime.model.eval.call_count, 1)
        call = runtime.model.eval.call_args
        self.assertIs(call.args[0], image)
        self.assertIsNone(call.kwargs['diameter'])
        self.assertEqual(call.kwargs['bsize'], 384)
        self.assertEqual(call.kwargs['min_size'], config.cellpose.min_area)
        self.assertFalse(call.kwargs['augment'])
        self.assertTrue(all(state['total'] == 1 for state in states))

    def test_cancel_before_and_after_inference(self):
        for stop in ('segmenting', 'ready'):
            runtime = self.model()
            def check(**state):
                if state['stage'] == stop: raise HTTPException(409, 'canceled')
            with self.assertRaises(HTTPException): runtime.run(np.zeros((2, 2, 3), np.uint8), progress=check)
            self.assertEqual(runtime.model.eval.call_count, int(stop == 'ready'))

    def test_encoder_only_skips_mask_reconstruction(self):
        runtime = self.model()
        runtime.run(np.zeros((9, 11, 3), np.uint8), compute_masks=False)
        self.assertFalse(runtime.model.eval.call_args.kwargs['compute_masks'])

    def test_web_parameters_are_forwarded_without_changing_shared_configuration(self):
        runtime = self.model()
        parameters = CellposeParameters(diameter=15, flow_threshold=.7, cellprob_threshold=-1, min_area=3)
        before = config.cellpose.model_dump()
        runtime.run(np.zeros((9, 11, 3), np.uint8), parameters=parameters)
        options = runtime.model.eval.call_args.kwargs
        self.assertEqual((options['diameter'], options['flow_threshold'], options['cellprob_threshold'], options['min_size']), (15, .7, -1, 3))
        self.assertEqual(config.cellpose.model_dump(), before)

    def test_flow_uses_resampled_outputs_and_cellpose_iteration_count(self):
        from src.segment.flow import Endpoints
        runtime = self.model()
        image = np.zeros((9, 11, 3), np.uint8)
        vectors = np.ones((2, 9, 11), np.float32)
        logits = np.ones((9, 11), np.float32)
        runtime.model.eval.return_value = (np.zeros((9, 11), np.int32), [None, vectors, logits], None)
        runtime.model.eval.side_effect = None
        endpoints = Endpoints(np.zeros_like(vectors), logits > 0)
        with patch('src.segment.runtime.trace', return_value=endpoints) as trace:
            for diameter, niter in ((None, 200), (15, 100), (60, 400)):
                result = runtime.run(image, flow=True, parameters=CellposeParameters(diameter=diameter, cellprob_threshold=-1))
                self.assertIs(result[3], endpoints)
                self.assertIs(trace.call_args.args[0], vectors)
                self.assertEqual(trace.call_args.args[2:4], (-1, niter))
                self.assertTrue(runtime.model.eval.call_args.kwargs['resample'])
            trace.reset_mock()
            result = runtime.run(image, flow=False)
            self.assertIsNone(result[3])
            trace.assert_not_called()

    def test_diameter_expansion_limit_is_checked_before_model_loading(self):
        runtime = CellposeRuntime()
        with patch.object(config.cellpose, 'max_pixels', 100), patch.object(runtime, 'load') as load:
            with self.assertRaises(HTTPException):
                runtime.run(np.zeros((9, 9, 3), np.uint8), parameters=CellposeParameters(diameter=15))
            load.assert_not_called()

    def test_large_image_rejected_before_loading(self):
        runtime = CellposeRuntime()
        with patch.object(config.cellpose, 'max_pixels', 3), patch.object(runtime, 'load') as load:
            with self.assertRaises(HTTPException): runtime.run(np.zeros((2, 2, 3), np.uint8))
            load.assert_not_called()

    def test_missing_checkpoint_does_not_fall_back(self):
        with patch.object(config.cellpose, 'checkpoint', 'weights/missing-cpdino-test.pth'):
            with self.assertRaises(HTTPException) as caught: CellposeRuntime().load()
            self.assertEqual(caught.exception.status_code, 503)

    def test_checkpoint_change_reloads_instead_of_reusing_previous_encoder(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            first = Path(directory) / 'first.pth'
            second = Path(directory) / 'second.pth'
            first.touch(); second.touch()
            runtime = CellposeRuntime()
            with patch.object(config.cellpose, 'checkpoint', str(first)), patch.object(config.cellpose, 'device', 'cpu'), \
                    patch('cellpose.models.CellposeModel', side_effect=[Mock(), Mock()]) as create:
                one = runtime.load()
                self.assertIs(runtime.load(), one)
                config.cellpose.checkpoint = str(second)
                self.assertIsNot(runtime.load(), one)
                self.assertEqual(create.call_count, 2)
