import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image

from src.api.image import crop_image
from src.data.image import read_bytes
from src.export.archive import make_pair_archive
from src.export.jobs import JobStore
from src.export.pipeline import append_archive_batch


class CropTests(unittest.TestCase):
    def source(self, image, exif=None):
        output = BytesIO()
        Image.fromarray(image).save(output, format='PNG', **({'exif': exif} if exif else {}))
        return UploadFile(filename='source.png', file=BytesIO(output.getvalue()))

    def test_crop_preserves_exact_pixels_and_pair_size(self):
        image = np.arange(8 * 10 * 3, dtype=np.uint8).reshape(8, 10, 3)
        response = crop_image(self.source(image), 2, 3, 7, 4)
        cropped = read_bytes(response.body)
        np.testing.assert_array_equal(cropped, image[3:7, 2:9])
        mask = np.array([[0, 3]], np.int8)
        with ZipFile(BytesIO(make_pair_archive('source.png', cropped, mask))) as archive:
            self.assertEqual(archive.namelist(), ['source_image.png', 'source_mask.png'])
            for name in archive.namelist():
                with Image.open(BytesIO(archive.read(name))) as result:
                    self.assertEqual(result.size, (7, 4))

    def test_crop_uses_oriented_coordinates(self):
        image = np.arange(3 * 4 * 3, dtype=np.uint8).reshape(3, 4, 3)
        exif = Image.Exif(); exif[274] = 6
        response = crop_image(self.source(image, exif), 1, 1, 2, 3)
        expected = np.rot90(image, k=-1)[1:4, 1:3]
        np.testing.assert_array_equal(read_bytes(response.body), expected)

    def test_invalid_crop_never_pads_outside_the_image(self):
        image = np.zeros((8, 10, 3), np.uint8)
        for rect in [(-1, 0, 2, 2), (0, 0, 0, 2), (8, 0, 3, 2), (0, 7, 2, 2)]:
            with self.subTest(rect=rect), self.assertRaises(HTTPException):
                crop_image(self.source(image), *rect)

    def test_batch_segments_only_cropped_pixels_and_exports_matching_sizes(self):
        image = np.arange(8 * 10 * 3, dtype=np.uint8).reshape(8, 10, 3)
        cropped = crop_image(self.source(image), 2, 3, 6, 4).body
        with TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp), 3600, 'crop-test')
            job = store.create('a'); store.start(job, 'a', 1)
            session = SimpleNamespace(id='a', lock=RLock(), segmenter=object())
            with patch('src.export.pipeline.jobs', store), patch('src.export.pipeline.prediction.predict',
                    return_value=np.array([[0, 1, 3], [3, 1, 0]], np.int8)) as predict:
                append_archive_batch(job, 3, [('source.png', BytesIO(cropped))], session)
            self.assertEqual(predict.call_args.args[0].shape, (2, 3, 3))
            self.assertEqual(predict.call_args.args[3], 6)
            with ZipFile(store.path(job, 'a')) as archive:
                for name in archive.namelist():
                    with Image.open(BytesIO(archive.read(name))) as result:
                        self.assertEqual(result.size, (6, 4))
                        if name.endswith('_image.png'):
                            np.testing.assert_array_equal(np.asarray(result), image[3:7, 2:8])
