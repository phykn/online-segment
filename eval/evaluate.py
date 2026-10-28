"""Score the pixel RF against a truth mask with a left/right spatial split.

Labels from the left half train the RF; the right half is scored. Run from backend/:
    .venv/bin/python ../eval/evaluate.py ../frontend/asset/sample1.png ../eval/truth/sample1_mask.png --kind image
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from src.config import config  # noqa: E402
from src.segment.model import Segmenter  # noqa: E402

NAMES = ('particle', 'pore', 'crack', 'binder')


def load(image_path, truth_path, width):
    img = Image.open(image_path).convert('RGB')
    truth = Image.open(truth_path)
    if width and width < img.width:
        size = (width, round(img.height*width/img.width))
        img, truth = img.resize(size, Image.BILINEAR), truth.resize(size, Image.NEAREST)
    return np.asarray(img), np.asarray(truth)


def clicks(train, count, radius=2, seed=0):
    """Mimic sparse user brushing: a few small dabs per class instead of dense labels."""
    rng = np.random.default_rng(seed)
    out = np.full_like(train, -1)
    yy, xx = np.ogrid[-radius:radius+1, -radius:radius+1]
    dab = yy*yy + xx*xx <= radius*radius
    for label in range(len(NAMES)):
        ys, xs = np.nonzero(train == label)
        for i in rng.choice(len(ys), min(count, len(ys)), replace=False):
            y0, x0 = ys[i]-radius, xs[i]-radius
            if y0 < 0 or x0 < 0 or y0+dab.shape[0] > train.shape[0] or x0+dab.shape[1] > train.shape[1]:
                continue
            win = (slice(y0, y0+dab.shape[0]), slice(x0, x0+dab.shape[1]))
            out[win][dab & (train[win] == label)] = label
    return out


def strokes(train, count, seed=0, length=24, radius=2, margin=4):
    """Mimic real brushing: short strokes inside confident regions, and traced along cracks."""
    from scipy import ndimage as ndi
    rng = np.random.default_rng(seed)
    out = np.full_like(train, -1)
    h, w = train.shape
    yy, xx = np.ogrid[-radius:radius+1, -radius:radius+1]
    dab = yy*yy + xx*xx <= radius*radius

    def paint(y, x, label, r):
        y0, y1, x0, x1 = max(y-r, 0), min(y+r+1, h), max(x-r, 0), min(x+r+1, w)
        d = dab[r-(y-y0):r+(y1-y), r-(x-x0):r+(x1-x)] if r == radius else np.ones((y1-y0, x1-x0), bool)
        win = (slice(y0, y1), slice(x0, x1))
        out[win][d & (train[win] == label)] = label

    for label in (0, 1, 3):
        # People brush well inside a region, away from uncertain edges.
        core = ndi.distance_transform_edt(train == label) > margin
        ys, xs = np.nonzero(core)
        for i in rng.choice(len(ys), min(count, len(ys)), replace=False):
            angle = rng.uniform(0, np.pi)
            for t in np.linspace(-length/2, length/2, length):
                y, x = int(round(ys[i]+t*np.sin(angle))), int(round(xs[i]+t*np.cos(angle)))
                if 0 <= y < h and 0 <= x < w and core[y, x]:
                    paint(y, x, label, radius)

    # Crack strokes follow the crack: walk along connected crack pixels from a random start.
    crack = train == 2
    ys, xs = np.nonzero(crack)
    for i in rng.choice(len(ys), min(count, len(ys)), replace=False):
        seen, frontier = {(ys[i], xs[i])}, [(ys[i], xs[i])]
        while frontier and len(seen) < length:
            y, x = frontier.pop(0)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    p = (y+dy, x+dx)
                    if 0 <= p[0] < h and 0 <= p[1] < w and crack[p] and p not in seen:
                        seen.add(p)
                        frontier.append(p)
        for y, x in seen:
            paint(y, x, 2, 0)
    return out


def score(pred, truth):
    valid = truth != 255
    k = len(NAMES)
    cm = np.bincount(truth[valid].astype(int)*k + np.clip(pred[valid], 0, k-1), minlength=k*k).reshape(k, k)
    tp = np.diag(cm).astype(float)
    iou = tp / np.maximum(cm.sum(0)+cm.sum(1)-tp, 1)
    f1 = 2*tp / np.maximum(cm.sum(0)+cm.sum(1), 1)
    return dict(iou={n: round(float(v), 4) for n, v in zip(NAMES, iou)},
                f1={n: round(float(v), 4) for n, v in zip(NAMES, f1)},
                miou=round(float(iou.mean()), 4), crack_f1_2px=round(float(tolerant_f1(pred, truth)), 4),
                confusion=cm.tolist())


def tolerant_f1(pred, truth, tol=2):
    """Crack F1 where a hit within tol pixels counts; thin lines are otherwise dominated by 1px offsets."""
    import cv2
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*tol+1, 2*tol+1))
    p, g = (pred == 2) & (truth != 255), truth == 2
    precision = (p & cv2.dilate(g.astype(np.uint8), kernel).astype(bool)).sum() / max(p.sum(), 1)
    recall = (g & cv2.dilate(p.astype(np.uint8), kernel).astype(bool)).sum() / max(g.sum(), 1)
    return 2*precision*recall / max(precision+recall, 1e-9)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image')
    parser.add_argument('truth')
    parser.add_argument('--kind', default=config.feature.kind, choices=['image', 'encoder', 'hybrid', 'dino'])
    parser.add_argument('--context', default=config.feature.cellpose, choices=['none', 'foreground', 'statistics'])
    parser.add_argument('--texture', action='store_true')
    parser.add_argument('--width', type=int, default=768)
    parser.add_argument('--clicks', type=int, default=0, help='dabs per class; 0 trains on every left-half label')
    parser.add_argument('--strokes', type=int, default=0, help='brush strokes per class, like real labeling')
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()

    config.feature.kind, config.feature.cellpose, config.feature.texture = args.kind, args.context, args.texture
    img, truth = load(args.image, args.truth, args.width)
    half = img.shape[1] // 2
    train = truth.astype(np.int8)  # 255 wraps to -1, the app's unlabeled value
    train[:, half:] = -1
    if args.strokes:
        train = strokes(train, args.strokes, seed=args.seed)
    elif args.clicks:
        train = clicks(train, args.clicks, seed=args.seed)

    seg = Segmenter()
    start = time.perf_counter()
    seg.fit([(img, train, 1.)])
    labels, _ = seg.classifier.predict(seg.feature(img))
    result = dict(kind=args.kind, context=args.context, texture=args.texture, width=img.shape[1],
                  seconds=round(time.perf_counter()-start, 2), **score(labels[:, half:], truth[:, half:]))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
