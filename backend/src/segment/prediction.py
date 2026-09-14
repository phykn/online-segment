import numpy as np
from src.data.mask import resize
from src.segment.feature import Features


def infer(image, segmenter, diameter=None, original_width=None, edits=None, progress=None, train=True):
    report = progress or segmenter.report
    try:
        segmenter.validate(image)
        scale = (original_width or image.shape[1])/image.shape[1]
        if edits is not None:
            edits = resize(edits, image.shape[1], image.shape[0])
        if train and edits is not None:
            records = dict(segmenter.training)
            records[(segmenter.key(image), scale)] = (image, edits, scale)
            segmenter.fit(list(records.values()))
        classifier = segmenter.classifier
        features = segmenter.feature(image, report, scale) if classifier.model is not None else Features(image.shape[:2])
        labels, uncertain = classifier.predict(features, report)
        counts = [int(np.count_nonzero(labels == label)) for label in range(4)]
        message = ''
        if len(classifier.classes) < 2:
            message = 'Label at least two classes to predict.'
        summary = dict(pixel_counts=counts, area_fractions=[count/labels.size for count in counts],
            unlabeled_pixels=int(np.count_nonzero(labels < 0)), training_samples=classifier.count,
            training_samples_by_class=classifier.counts,
            classes=classifier.classes, classifier='rf' if classifier.model is not None else 'untrained',
            device='cuda' if classifier.cuda is not None else 'cpu',
            message=message)
        report(stage='ready', done=1, total=1)
        return labels, uncertain, summary, []
    except Exception:
        segmenter.report(stage='error', done=0, total=0)
        raise


def predict(image, segmenter, diameter=None, original_width=None, edits=None, progress=None):
    return infer(image, segmenter, diameter, original_width, edits, progress, train=False)[0]
