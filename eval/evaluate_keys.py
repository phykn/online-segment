"""Score the pixel RF on the hand-checked answer keys frontend/asset/sampleN_mask.png.

Labels from the left half train the RF and the right half is scored, for 10 and 30 clicks and
strokes per class, at the app's default working width of 768. Run from backend/:
    .venv/bin/python ../eval/evaluate_keys.py --seed 0
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from src.config import config  # noqa: E402
from src.segment.model import Segmenter  # noqa: E402
from evaluate import clicks, strokes, tolerant_f1  # noqa: E402

# Samples 1, 2 and 4: particle, pore, crack. Sample 3: large particle, small particle, pore.
CRACKS = {1: True, 2: True, 3: False, 4: True}
SETTINGS = (('clicks', 10), ('clicks', 30), ('strokes', 10), ('strokes', 30))


def load(sample, width=768):
    img = Image.open(ROOT/f'frontend/asset/sample{sample}.png').convert('RGB')
    truth = Image.open(ROOT/f'frontend/asset/sample{sample}_mask.png')
    if img.width > width:
        size = (width, round(img.height*width/img.width))
        img, truth = img.resize(size, Image.BILINEAR), truth.resize(size, Image.NEAREST)
    return np.asarray(img), np.asarray(truth)


def score(pred, truth, crack):
    cm = np.bincount(truth.ravel().astype(int)*3 + np.clip(pred.ravel(), 0, 2), minlength=9).reshape(3, 3)
    tp = np.diag(cm).astype(float)
    iou = tp / np.maximum(cm.sum(0)+cm.sum(1)-tp, 1)
    result = dict(miou=float(iou.mean()), iou=iou.tolist())
    if crack:
        result['crack_f1_2px'] = float(tolerant_f1(pred, truth))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', default=config.feature.kind, choices=['image', 'encoder', 'hybrid', 'dino'])
    parser.add_argument('--samples', type=int, nargs='+', default=[1, 2, 3, 4])
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()

    config.feature.kind, config.feature.cellpose = args.kind, 'none'
    start, summary = time.perf_counter(), {}
    for sample in args.samples:
        img, truth = load(sample)
        half = img.shape[1] // 2
        train = truth.astype(np.int8)
        train[:, half:] = -1
        seg, rows = Segmenter(), []  # one Segmenter per image reuses its tokens and PCA
        for how, count in SETTINGS:
            seg.fit([(img, (strokes if how == 'strokes' else clicks)(train, count, seed=args.seed), 1.)])
            labels, _ = seg.classifier.predict(seg.feature(img))
            rows.append(score(labels[:, half:], truth[:, half:], CRACKS[sample]))
        summary[sample] = dict(miou=round(np.mean([r['miou'] for r in rows]), 4))
        if CRACKS[sample]:
            summary[sample]['crack'] = round(np.mean([r['iou'][2] for r in rows]), 4)
            summary[sample]['crack_f1_2px'] = round(np.mean([r['crack_f1_2px'] for r in rows]), 4)
        print(sample, json.dumps(summary[sample]), flush=True)
    print('mean', round(np.mean([v['miou'] for v in summary.values()]), 4), f'{time.perf_counter()-start:.0f}s')


if __name__ == '__main__':
    main()
