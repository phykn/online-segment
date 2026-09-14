import unittest
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch, Mock
import numpy as np
from src.api.dependencies import read_session
from src.api.model import predict,progress
from src.api.schema import PredRequest
from src.api.router import create_session,health_check
from src.main import app
from src.session import sessions

class RouterTests(unittest.TestCase):
    def test_health_and_session(self):
        self.assertEqual(health_check(),{'status':'ok'})
        created=create_session();dependency=read_session(created.id)
        try: self.assertEqual(next(dependency).id,created.id)
        finally: dependency.close();sessions.close()

    def test_training_uses_prediction_endpoint_and_progress_is_available(self):
        paths=set(app.openapi()['paths'])
        self.assertNotIn('/api/apply',paths)
        self.assertIn('/api/predict/status',paths)

    def test_unlabeled_prediction_preserves_mask_schema_and_original_scale(self):
        segmenter=SimpleNamespace(progress=dict(stage='segmenting',done=2,total=10), configure=Mock(), validate=Mock(), report=Mock())
        session=SimpleNamespace(lock=RLock(),segmenter=segmenter)
        payload=PredRequest(image='encoded',width=4,diameter=19)
        labels=np.array([[0,1,2,0]],np.int8);uncertain=np.zeros_like(labels)
        with patch('src.api.model.read_image',return_value=np.zeros((2,8,3),np.uint8)), patch(
                'src.api.model.prediction.infer',return_value=(labels,uncertain,{'total':2},[])) as run:
            response=predict(payload,session)
        self.assertEqual(run.call_args.args[0].shape,(1,4,3))
        self.assertEqual(run.call_args.args[3],8)
        self.assertEqual(response.mask.runs,[(0,1),(1,1),(2,1),(0,1)])
        self.assertEqual(progress(session)['done'],2)

    def test_training_failure_reports_error_and_target_limit_precedes_training(self):
        from src.config import config
        from src.segment.model import Segmenter
        from fastapi import HTTPException
        model = Segmenter(); session = SimpleNamespace(lock=RLock(), segmenter=model)
        payload = PredRequest(image='encoded', training=[])
        with patch('src.api.model.read_image', return_value=np.zeros((2, 2, 3), np.uint8)), patch.object(config.cellpose, 'max_pixels', 3), patch.object(model, 'fit') as fit:
            with self.assertRaises(HTTPException): predict(payload, session)
            fit.assert_not_called()
        self.assertEqual(progress(session)['stage'], 'error')
