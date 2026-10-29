"""Score large vs small particle separation with a left/right spatial split.

Labels from the left half of a size truth (eval/make_size_truth.py) train the RF; the right half is
scored for 5/10/30 clicks and strokes per class. Run from backend/:
    .venv/bin/python ../eval/evaluate_size.py ../frontend/asset/sample3.png ../eval/truth/sample3_size_mask.png
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from src.config import config  # noqa: E402
from src.segment.model import Segmenter  # noqa: E402
from evaluate import clicks  # noqa: E402

NAMES = ('large', 'small', 'background')
# Small particles are a few pixels across, so their strokes are short and stay near the centre.
MARGIN, LENGTH = (4, 1, 3), (24, 8, 24)


def strokes(train, count, seed=0, radius=2):
    rng = np.random.default_rng(seed)
    out = np.full_like(train, -1)
    h, w = train.shape
    yy, xx = np.ogrid[-radius:radius+1, -radius:radius+1]
    dab = yy*yy + xx*xx <= radius*radius
    for label in range(len(NAMES)):
        core = ndi.distance_transform_edt(train == label) > MARGIN[label]
        ys, xs = np.nonzero(core)
        for i in rng.choice(len(ys), min(count, len(ys)), replace=False):
            angle = rng.uniform(0, np.pi)
            for t in np.linspace(-LENGTH[label]/2, LENGTH[label]/2, LENGTH[label]):
                y, x = int(round(ys[i]+t*np.sin(angle))), int(round(xs[i]+t*np.cos(angle)))
                if radius <= y < h-radius and radius <= x < w-radius and core[y, x]:
                    win = (slice(y-radius, y+radius+1), slice(x-radius, x+radius+1))
                    out[win][dab & (train[win] == label)] = label
    return out


def score(pred, truth, half):
    pred = np.clip(pred, 0, 2)
    right = np.zeros(truth.shape, bool)
    right[:, half:] = True
    valid = right & (truth != 255)
    cm = np.bincount(truth[valid].astype(int)*3 + pred[valid], minlength=9).reshape(3, 3)
    tp = np.diag(cm).astype(float)
    iou = tp / np.maximum(cm.sum(0)+cm.sum(1)-tp, 1)
    # Rim: large-particle pixels within 2 px of the edge of the scored large region.
    rim = right & (truth == 0) & (ndi.distance_transform_edt(truth == 0) <= 2)
    wrong = []
    for label in (0, 1):
        # Particles wholly in the scored half, judged by the majority of their pixels.
        count, parts, stats, _ = cv2.connectedComponentsWithStats((truth == label).astype(np.uint8), connectivity=8)
        votes = np.bincount(parts.ravel()*3 + pred.ravel(), minlength=count*3).reshape(count, 3)
        keep = (stats[:, cv2.CC_STAT_LEFT] >= half) & (stats[:, cv2.CC_STAT_AREA] >= 20)
        keep[0] = False
        wrong.append(int((votes[keep].argmax(1) != label).sum()))
    return dict(iou=iou, large_to_small=cm[0, 1]/cm[0].sum(), small_to_large=cm[1, 0]/cm[1].sum(),
                rim=float((pred[rim] != 0).mean()), wrong=wrong)


def line(name, rows):
    iou = np.mean([r['iou'] for r in rows], 0)
    return (f'{name:12s} ' + ' '.join(f'{n}={v:.3f}' for n, v in zip(NAMES, iou)) + f' mIoU={iou.mean():.3f}'
            f'  large>small={np.mean([r["large_to_small"] for r in rows]):.3f} small>large={np.mean([r["small_to_large"] for r in rows]):.3f}'
            f'  rim error={np.mean([r["rim"] for r in rows]):.2f}'
            f'  wrong particles large/small={sum(r["wrong"][0] for r in rows)}/{sum(r["wrong"][1] for r in rows)}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image')
    parser.add_argument('truth')
    parser.add_argument('--kind', default=config.feature.kind, choices=['image', 'dino'])
    parser.add_argument('--seeds', type=int, nargs='+', default=[0, 1])
    args = parser.parse_args()

    config.feature.kind = args.kind
    img = np.asarray(Image.open(args.image).convert('RGB'))
    truth = np.asarray(Image.open(args.truth))
    half = img.shape[1] // 2
    train = truth.astype(np.int8)  # 255 wraps to -1, the app's unlabeled value
    train[:, half:] = -1
    seg, everything = Segmenter(), []
    start = time.perf_counter()
    for how, simulate in (('clicks', clicks), ('strokes', strokes)):
        for count in (5, 10, 30):
            rows = []
            for seed in args.seeds:
                seg.fit([(img, simulate(train, count, seed=seed))])
                labels, _ = seg.classifier.predict(seg.feature(img))
                rows.append(score(labels, truth, half))
            print(line(f'{how} {count}', rows), flush=True)
            everything += rows
    print(line('mean', everything), f' {time.perf_counter()-start:.0f}s')


if __name__ == '__main__':
    main()
