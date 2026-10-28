"""Build a reviewable particle / pore / crack / binder truth mask for a battery SEM cross-section.

Rules mark only confident seeds; the app's own DINO + ExtraTrees pipeline, trained on those seeds
over the whole image, fills the ambiguous rest (fine-grain agglomerates, necks, faint cracks).
Pixels it is unsure about are left unscored. Because DINO helps make this truth, scores of
DINO features against it are optimistic; review the overlay before trusting them.

Values: 0 particle, 1 pore, 2 crack, 3 binder, 255 ignored. Run with backend/.venv python:
    python eval/make_truth.py frontend/asset/sample1.png eval/truth/sample1
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

PARTICLE, PORE, CRACK, BINDER, IGNORE = 0, 1, 2, 3, 255
COLORS = np.array([[239, 71, 111], [17, 138, 178], [255, 214, 10], [142, 93, 231]], np.uint8)
CONFIG = dict(sigma=.7, close=3, grain=8, seal=5, depth=6, window=8, solid=.8, contrast=12, flat=6, gap=20, packed=.4, sure=.5, min_crack=8, margin=3, mixed=1)


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))


def levels(smooth):
    """Brightness cut-offs from the binder and particle histogram peaks."""
    hist = np.histogram(smooth, 256, (0, 256))[0]
    hist = np.convolve(hist, np.ones(9)/9, mode='same')
    particle = 128 + int(np.argmax(hist[128:]))
    binder = 40 + int(np.argmax(hist[40:128]))
    # Particle edge at half height between the two plateaus; pores are clearly darker than binder.
    return (binder+particle)/2, binder*.6


def seeds(smooth, cfg):
    edge, dark = levels(smooth)
    bright = smooth > edge
    # Opening drops fine grains and thin bridges, leaving the bodies of secondary particles.
    body = cv2.morphologyEx(bright.astype(np.uint8), cv2.MORPH_OPEN, disk(cfg['grain'])).astype(bool)
    # Deep inside a solid particle, dark pixels can only be damage. Sealing cracks and filling holes
    # gives the particle outline; agglomerates and necks between particles fail the solidity test
    # because binder shows through around them.
    sealed = ndi.binary_fill_holes(cv2.morphologyEx(body.astype(np.uint8), cv2.MORPH_CLOSE, disk(cfg['seal'])))
    depth = cv2.distanceTransform(sealed.astype(np.uint8), cv2.DIST_L2, 5)
    solid = cv2.GaussianBlur(bright.astype(np.float32), (0, 0), cfg['window']) > cfg['solid']
    deep = (depth > cfg['depth']) & solid

    tophat = cv2.morphologyEx(smooth, cv2.MORPH_BLACKHAT, disk(cfg['close']))
    crack = deep & (~bright | (tophat > cfg['contrast']))
    lab, count = ndi.label(crack, structure=np.ones((3, 3)))
    crack &= np.isin(lab, 1+np.flatnonzero(ndi.sum(crack, lab, range(1, count+1)) >= cfg['min_crack']))

    away = cv2.distanceTransform((~bright).astype(np.uint8), cv2.DIST_L2, 3) > cfg['margin']
    mask = np.full(smooth.shape, -1, np.int8)
    mask[cv2.erode(body.astype(np.uint8), disk(2)).astype(bool) & (tophat < cfg['flat'])] = PARTICLE
    mask[away & (smooth > dark+10) & (smooth < edge-30)] = BINDER
    mask[away & (smooth < dark-10)] = PORE
    # Outside sealed particles nothing is a crack. Grains of agglomerates are particle and the narrow
    # gaps between packed grains are pore; wider mid-gray regions are binder.
    out = ~cv2.dilate(sealed.astype(np.uint8), disk(cfg['margin'])).astype(bool)
    grains = out & bright
    packed = cv2.GaussianBlur(grains.astype(np.float32), (0, 0), cfg['window']) > cfg['packed']
    near = cv2.distanceTransform((~bright).astype(np.uint8), cv2.DIST_L2, 3) <= cfg['margin']
    mask[out & cv2.erode(bright.astype(np.uint8), disk(1)).astype(bool)] = PARTICLE
    mask[out & ~packed & (smooth > dark) & (smooth < edge-cfg['gap'])] = BINDER
    mask[out & (smooth < dark-10)] = PORE
    mask[out & packed & near & (smooth < edge-cfg['gap'])] = PORE
    mask[crack] = CRACK
    return mask, bright & ~deep, edge, dark


def segment(img, cfg):
    gray = img.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    smooth = cv2.GaussianBlur(gray, (0, 0), cfg['sigma'])
    seed, outer, edge, dark = seeds(smooth, cfg)

    seg = Segmenter()
    seg.fit([(img, seed, 1.)])
    feats, model = seg.feature(img), seg.classifier.model
    probs = np.concatenate([model.predict_proba(feats.pixels(np.arange(i, min(i+65536, feats.shape[0]*feats.shape[1]))))
                            for i in range(0, feats.shape[0]*feats.shape[1], 65536)]).reshape(*feats.shape, -1)

    mask = model.classes_[probs.argmax(-1)].astype(np.uint8)
    mask[seed >= 0] = seed[seed >= 0]
    mask[(probs.max(-1) < cfg['sure']) & (seed < 0)] = IGNORE
    # Isolated crack specks are texture, not damage; leave them unscored.
    lab, count = ndi.label(mask == CRACK, structure=np.ones((3, 3)))
    mask[np.isin(lab, 1+np.flatnonzero(ndi.sum(mask == CRACK, lab, range(1, count+1)) < cfg['min_crack']))] = IGNORE
    # The one-pixel rim where a particle outline meets binder/pore mixes both; it is not scored.
    rim = cv2.morphologyEx(outer.astype(np.uint8), cv2.MORPH_GRADIENT, disk(cfg['mixed'])).astype(bool)
    mask[rim & (mask != CRACK) & (np.abs(smooth-edge) < (edge-dark)/4)] = IGNORE
    return mask, seed, dict(edge=round(float(edge), 1), dark=round(float(dark), 1))


def overlay(gray, mask):
    rgb = np.repeat(gray[..., None], 3, -1).astype(np.float32)
    for value, color in enumerate(COLORS):
        sel = mask == value
        rgb[sel] = .55*rgb[sel] + .45*color
    rgb[mask == IGNORE] = [0, 0, 0]
    return rgb.astype(np.uint8)


def main(src, dst):
    config.feature.kind, config.feature.cellpose = 'dino', 'none'
    img = np.asarray(Image.open(src).convert('RGB'))
    mask, seed, cuts = segment(img, CONFIG)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out = Image.fromarray(mask, 'P')
    out.putpalette([*COLORS.ravel(), *[0]*(256*3-COLORS.size)])
    out.save(f'{dst}_mask.png')
    gray = (img.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)).astype(np.uint8)
    Image.fromarray(overlay(gray, mask)).save(f'{dst}_overlay.png')
    Image.fromarray(overlay(gray, np.where(seed < 0, IGNORE, seed.astype(np.int16)).astype(np.uint8))).save(f'{dst}_seeds.png')
    names = (('particle', PARTICLE), ('pore', PORE), ('crack', CRACK), ('binder', BINDER), ('ignore', IGNORE))
    print(cuts, {name: int(np.count_nonzero(mask == v)) for name, v in names},
          'seeds', {name: int(np.count_nonzero(seed == v)) for name, v in names[:4]})


if __name__ == '__main__':
    main(*sys.argv[1:3])
