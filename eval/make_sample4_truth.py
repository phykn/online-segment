"""Build a reviewable particle / pore / crack truth mask for frontend/asset/sample4.png.

sample4 is a polished cross-section of flaky graphite. Polished sections are flat mid-gray with
bright rims; slits inside them are cracks. Through the pores one sees particle surfaces below the
section plane, about as bright as the sections; rules cannot tell them apart, so their interiors
are marked by hand below (like brush strokes) and count as pore.

Rules and those boxes mark confident seeds; the app's DINO + ExtraTrees pipeline, trained on the
seeds, fills the rest. Unscored: low-confidence pixels, bright section rims, crack specks, fluffy
carbon-binder clumps, particle blobs with no seeded section, and the current collector.

Values: 0 particle, 1 pore, 2 crack, 255 ignored. Run with backend/.venv python:
    python eval/make_sample4_truth.py frontend/asset/sample4.png frontend/asset/sample4
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from src.config import config  # noqa: E402
from src.segment.model import Segmenter  # noqa: E402
from make_truth import COLORS, disk, overlay  # noqa: E402

PARTICLE, PORE, CRACK, IGNORE = 0, 1, 2, 255
# Particle surfaces below the section plane, seen through pores (x0, y0, x1, y1).
BEHIND = [(5, 15, 55, 100), (125, 5, 225, 40), (3, 220, 40, 285), (550, 10, 680, 60), (5, 810, 90, 860),
          (170, 672, 290, 700), (305, 940, 340, 985), (820, 872, 995, 922)]
# Fluffy carbon-binder clumps: neither section nor empty pore.
CLUMPS = [(875, 175, 935, 300), (662, 655, 712, 720)]


def boxes(shape, rects):
    out = np.zeros(shape, bool)
    for x0, y0, x1, y1 in rects:
        out[y0:y1, x0:x1] = True
    return out


def seeds(gray):
    smooth = cv2.GaussianBlur(gray, (0, 0), 1)
    mean = cv2.GaussianBlur(gray, (0, 0), 3)
    spread = np.sqrt(np.maximum(cv2.GaussianBlur(gray*gray, (0, 0), 3) - mean*mean, 0))
    behind = boxes(gray.shape, BEHIND)
    dark = smooth < 28
    pore = cv2.erode(dark.astype(np.uint8), disk(2)).astype(bool) & (cv2.GaussianBlur(dark.astype(np.float32), (0, 0), 5) > .75)
    rim = smooth > 135
    clear = cv2.distanceTransform((~(dark | rim)).astype(np.uint8), cv2.DIST_L2, 3) > 3
    flat = (smooth > 45) & (smooth < 110) & (spread < 14) & clear
    flat = cv2.morphologyEx(flat.astype(np.uint8), cv2.MORPH_OPEN, disk(2)).astype(bool)
    flat &= ~cv2.dilate(behind.astype(np.uint8), disk(6)).astype(bool)
    # Section outlines: flat areas sealed across slits. Dark or thin dark lines deep inside are cracks.
    hull = ndi.binary_fill_holes(cv2.morphologyEx(flat.astype(np.uint8), cv2.MORPH_CLOSE, disk(5)))
    inner = cv2.distanceTransform(hull.astype(np.uint8), cv2.DIST_L2, 5) > 4
    blackhat = cv2.morphologyEx(smooth, cv2.MORPH_BLACKHAT, disk(3))
    crack = inner & ((smooth < 45) | (blackhat > 20)) & ~pore
    lab, count = ndi.label(crack, structure=np.ones((3, 3)))
    crack &= np.isin(lab, 1+np.flatnonzero(ndi.sum(crack, lab, range(1, count+1)) >= 8))
    seed = np.full(gray.shape, -1, np.int8)
    seed[flat & ~crack] = PARTICLE
    seed[(pore & ~inner) | behind] = PORE
    seed[crack] = CRACK
    return seed, inner, rim


def segment(img):
    gray = img.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    # The current collector: bright rows at the bottom, plus a margin for its rough top.
    collector = np.zeros(gray.shape, bool)
    collector[int(np.flatnonzero(gray.mean(1) > 150)[0])-8:] = True
    seed, inner, rim = seeds(gray)
    seed[collector] = -1

    seg = Segmenter()
    seg.fit([(img, seed, 1.)])
    feats, model = seg.feature(img), seg.classifier.model
    size = feats.shape[0]*feats.shape[1]
    probs = np.concatenate([model.predict_proba(feats.pixels(np.arange(i, min(i+65536, size))))
                            for i in range(0, size, 65536)]).reshape(*feats.shape, -1)
    mask = model.classes_[probs.argmax(-1)].astype(np.uint8)
    mask[seed >= 0] = seed[seed >= 0]
    mask[(probs.max(-1) < .5) & (seed < 0)] = IGNORE
    lab, count = ndi.label(mask == CRACK, structure=np.ones((3, 3)))
    mask[np.isin(lab, 1+np.flatnonzero(ndi.sum(mask == CRACK, lab, range(1, count+1)) < 8))] = IGNORE
    # Voids inside a section outline are slits; bright rims mix a section with what lies behind it.
    mask[inner & (mask == PORE) & (seed < 0)] = CRACK
    mask[rim & (seed < 0)] = IGNORE
    mask[collector | boxes(gray.shape, CLUMPS)] = IGNORE
    # Particle blobs with no seeded section are surfaces behind pores or debris.
    lab, count = ndi.label(mask == PARTICLE)
    mask[np.isin(lab, 1+np.flatnonzero(ndi.maximum(seed == PARTICLE, lab, range(1, count+1)) == 0))] = IGNORE
    return mask, seed, gray


def main(src, dst):
    config.feature.kind, config.feature.cellpose = 'dino', 'none'
    # Scale 8 at the native 1058 px needs a few more tokens than the app allows by default.
    config.dino.max_tokens = 300000
    img = np.asarray(Image.open(src).convert('RGB'))
    mask, seed, gray = segment(img)
    out = Image.fromarray(mask, 'P')
    out.putpalette([*COLORS.ravel(), *[0]*(256*3-COLORS.size)])
    out.save(f'{dst}_mask.png')
    Image.fromarray(overlay(gray.astype(np.uint8), mask)).save(f'{dst}_overlay.png')
    names = (('particle', PARTICLE), ('pore', PORE), ('crack', CRACK), ('ignore', IGNORE))
    print({name: int(np.count_nonzero(mask == v)) for name, v in names},
          'seeds', {name: int(np.count_nonzero(seed == v)) for name, v in names[:3]})


if __name__ == '__main__':
    main(*sys.argv[1:3])
