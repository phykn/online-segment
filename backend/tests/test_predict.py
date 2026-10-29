import unittest
from unittest.mock import patch
import numpy as np
from src.config import config
from src.segment.model import Segmenter
from src.segment.prediction import infer


class PredictTests(unittest.TestCase):
    def test_no_labels_means_unlabeled_including_background(self):
        image = np.zeros((8, 9, 3), np.uint8)
        result = infer(image, Segmenter())
        self.assertTrue((result[0] == -1).all())
        self.assertEqual(result[2]['unlabeled_pixels'], 72)

    def test_single_class_annotations_are_training_data_not_final_predictions(self):
        edits = np.full((4, 6), -1, np.int8); edits[0] = 0
        with patch.object(config.feature, 'kind', 'image'):
            result = infer(np.zeros((4, 6, 3), np.uint8), Segmenter(), edits=edits)
        self.assertEqual(result[2]['pixel_counts'], [0]*10)
        self.assertEqual(result[2]['area_fractions'], [0]*10)
        self.assertEqual(result[2]['unlabeled_pixels'], 24)
        self.assertEqual(result[2]['training_samples_by_class'], [4]+[0]*9)
