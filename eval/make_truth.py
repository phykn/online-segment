"""Build a reviewable particle / pore / crack truth mask for a battery SEM cross-section.

Values: 0 particle, 1 pore, 2 crack, 255 ignored. Run with backend/.venv python:
    python eval/make_truth.py frontend/asset/sample1.png eval/truth/sample1
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

PARTICLE, PORE, CRACK, IGNORE = 0, 1, 2, 255
COLORS = np.array([[239, 71, 111], [17, 138, 178], [255, 214, 10]], np.uint8)


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))


def segment(gray, cfg):
    smooth = cv2.GaussianBlur(gray, (0, 0), .8)
    bright = smooth > cfg['threshold']
    # Bridge thin dark lines inside particles, then keep only secondary particles large enough to hold cracks.
    env = cv2.morphologyEx(bright.astype(np.uint8), cv2.MORPH_CLOSE, disk(cfg['close'])).astype(bool)
    holes = ndi.binary_fill_holes(env) & ~env
    lab, n = ndi.label(holes)
    sizes = ndi.sum(holes, lab, range(1, n+1))
    env |= np.isin(lab, 1+np.flatnonzero(sizes <= cfg['hole']))
    lab, n = ndi.label(env)
    sizes = ndi.sum(env, lab, range(1, n+1))
    big = np.isin(lab, 1+np.flatnonzero(sizes >= cfg['big']))

    # Split touching particles so gaps between two particles stay pores, not cracks.
    dist = cv2.distanceTransform(big.astype(np.uint8), cv2.DIST_L2, 5)
    peaks = (dist == ndi.maximum_filter(dist, size=cfg['peak'])) & (dist >= cfg['min_radius'])
    markers, n = ndi.label(ndi.binary_dilation(peaks, iterations=2))
    markers = markers.astype(np.int32)
    markers[ndi.binary_erosion(~big, iterations=2)] = n+1
    relief = cv2.cvtColor((255-np.clip(dist*4, 0, 255)).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    ws = cv2.watershed(relief, markers)
    lines = ndi.binary_dilation((ws == -1) & big, iterations=cfg['line'])

    # Agglomerates of fine grains also close into large blobs; only solid secondary particles hold cracks.
    ids = np.where(big, np.maximum(ws, 0), 0)
    ids[ids == n+1] = 0
    fill = ndi.mean(bright, ids, range(n+1))
    area = np.bincount(ids.ravel(), minlength=n+1)
    solid = (fill >= cfg['solid']) & (area >= cfg['big'])
    solid[0] = False
    inside = solid[ids] & ~lines
    inside &= cv2.erode(big.astype(np.uint8), disk(cfg['rim'])).astype(bool) | ~bright

    # Cracks are thin lines darker than the surrounding particle, even when not dark in absolute terms.
    tophat = cv2.morphologyEx(smooth, cv2.MORPH_BLACKHAT, disk(cfg['close']))
    candidate = inside & ((tophat > cfg['contrast']) | ~bright)
    # Dense dark networks are grain boundaries in agglomerates, not cracks; they are too ambiguous to score.
    core = np.zeros(n+1)
    pieces, count = ndi.label(bright & ~candidate & solid[ids])
    owner = ndi.maximum(ids, pieces, range(1, count+1)).astype(int)
    np.maximum.at(core, owner, np.bincount(pieces.ravel(), minlength=count+1)[1:])
    core = core / np.maximum(area, 1)
    crowd = cv2.blur(candidate.astype(np.float32), (cfg['window'], cfg['window'])) > cfg['crowd']
    busy = ((core < cfg['core'])[ids] | ndi.binary_dilation(crowd, iterations=cfg['rim'])) & candidate
    candidate &= ~busy
    # Hairline cracks are real but too faint to label confidently; exclude them instead of calling them particle.
    faint = inside & bright & (tophat > cfg['faint']) & ~candidate
    thick = cv2.distanceTransform((~bright & big).astype(np.uint8), cv2.DIST_L2, 3) > cfg['max_half_width']
    crack = candidate & ~ndi.binary_dilation(thick, iterations=cfg['max_half_width'])
    lab, n = ndi.label(crack, structure=np.ones((3, 3)))
    sizes = ndi.sum(crack, lab, range(1, n+1))
    crack &= np.isin(lab, 1+np.flatnonzero(sizes >= cfg['min_crack']))

    mask = np.full(gray.shape, PORE, np.uint8)
    mask[bright] = PARTICLE
    mask[crack] = CRACK
    # Edge pixels between bright particles and dark surroundings are mixed; leave them out of scoring.
    edge = (cv2.morphologyEx(bright.astype(np.uint8), cv2.MORPH_GRADIENT, disk(1)) > 0) & ~crack
    ambiguous = np.abs(smooth - cfg['threshold']) < cfg['band']
    mask[edge & ambiguous] = IGNORE
    mask[busy | (faint & ~crack)] = IGNORE
    return mask


def overlay(gray, mask):
    rgb = np.repeat(gray[..., None], 3, -1).astype(np.float32)
    for value, color in enumerate(COLORS):
        sel = mask == value
        rgb[sel] = .55*rgb[sel] + .45*color
    rgb[mask == IGNORE] = [0, 0, 0]
    return rgb.astype(np.uint8)


CONFIG = dict(threshold=150, close=3, hole=150, big=1200, peak=41, min_radius=10,
              line=2, solid=.9, rim=3, contrast=22, core=.6, window=21, crowd=.3, faint=12, max_half_width=3, min_crack=12, band=25)


def main(src, dst):
    img = np.asarray(Image.open(src).convert('RGB'))
    gray = img.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    mask = segment(gray, CONFIG)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out = Image.fromarray(mask, 'P')
    out.putpalette([*COLORS.ravel(), *[0]*(256*3-9)])
    out.save(f'{dst}_mask.png')
    Image.fromarray(overlay(gray.astype(np.uint8), mask)).save(f'{dst}_overlay.png')
    counts = {name: int(np.count_nonzero(mask == v)) for name, v in
              (('particle', PARTICLE), ('pore', PORE), ('crack', CRACK), ('ignore', IGNORE))}
    print(counts)


if __name__ == '__main__':
    main(*sys.argv[1:3])
