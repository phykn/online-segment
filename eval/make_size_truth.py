"""Build large / small particle truth masks for an SEM image with two particle sizes.

Both rules start from an Otsu foreground of the lightly blurred image:
- size: large where a disk of radius 10 px fits inside the particle, small where not even a disk of
  radius 7 px fits. Sizes in between, the particle edge and small grains touching a large or
  medium particle are unscored.
- area: a marker watershed splits touching particles, and each particle is labelled whole, rim
  included, by its equivalent diameter (large >= 26 px, small <= 18 px). It is a cross-check: the
  size rule uses morphological openings, and so do the RF's size channels. Watershed misses leave
  some small grains merged into large particles.

Values: 0 large, 1 small, 2 background, 255 ignored. Run with backend/.venv python:
    python eval/make_size_truth.py frontend/asset/sample3.png eval/truth/sample3
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

LARGE, SMALL, BACKGROUND, IGNORE = 0, 1, 2, 255
COLORS = np.array([[239, 71, 111], [17, 138, 178], [40, 40, 40]], np.uint8)


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))


def base(fg):
    truth = np.full(fg.shape, IGNORE, np.uint8)
    truth[cv2.dilate(fg, disk(1)) == 0] = BACKGROUND
    return truth


def by_size(fg, large=10, small=7):
    body = cv2.morphologyEx(fg, cv2.MORPH_OPEN, disk(large))
    medium = cv2.morphologyEx(fg, cv2.MORPH_OPEN, disk(small)).astype(bool) & ~body.astype(bool)
    near = cv2.dilate(body, disk(3)).astype(bool) | cv2.dilate(medium.astype(np.uint8), disk(2)).astype(bool)
    truth = base(fg)
    truth[(cv2.erode(fg, disk(1)) > 0) & ~near] = SMALL
    truth[cv2.erode(body, disk(1)) > 0] = LARGE
    return truth


def reconstruct(marker, mask):
    """Grayscale reconstruction by dilation of marker under mask."""
    current = np.minimum(marker, mask)
    while True:
        grown = np.minimum(cv2.dilate(current, np.ones((3, 3), np.uint8)), mask)
        if np.array_equal(grown, current):
            return current
        current = grown


def by_area(img, fg, large=26, small=18):
    dist = cv2.GaussianBlur(cv2.distanceTransform(fg, cv2.DIST_L2, 5), (0, 0), 1)
    # One seed per particle: distance maxima that stand at least 2 px above their surroundings.
    peaks = (dist - reconstruct(dist-2, dist) > 1.99) & (dist > 3)
    markers, count = ndi.label(cv2.dilate(peaks.astype(np.uint8), disk(1)))
    markers[cv2.erode(1-fg, np.ones((3, 3), np.uint8)) > 0] = count+1
    regions = cv2.watershed(cv2.GaussianBlur(img, (0, 0), 1)[..., ::-1].copy(), markers.astype(np.int32))
    regions[(regions == count+1) | (fg == 0)] = 0
    regions = np.maximum(regions, 0)
    diameter = 2*np.sqrt(ndi.sum(np.ones_like(regions), regions, np.arange(count+1))/np.pi)
    d = np.where(regions > 0, diameter[regions], 0)
    # Watershed lines and outer edges belong to two regions or none; they are not scored.
    inner = cv2.erode((regions > 0).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    truth = base(fg)
    truth[inner & (d >= large)] = LARGE
    truth[inner & (d > 0) & (d <= small)] = SMALL
    return truth


def overlay(gray, mask):
    rgb = np.repeat(gray[..., None], 3, -1).astype(np.float32)
    for value, color in enumerate(COLORS[:2]):
        sel = mask == value
        rgb[sel] = .55*rgb[sel] + .45*color
    rgb[mask == IGNORE] = .55*rgb[mask == IGNORE] + .45*np.array([255, 214, 10])
    return rgb.astype(np.uint8)


def main(src, dst):
    img = np.asarray(Image.open(src).convert('RGB'))
    gray = img.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    smooth = cv2.GaussianBlur(gray, (0, 0), 1)
    otsu = cv2.threshold(smooth.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]
    fg = (smooth > otsu).astype(np.uint8)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    for rule, mask in (('size', by_size(fg)), ('area', by_area(img, fg))):
        out = Image.fromarray(mask, 'P')
        out.putpalette([*COLORS.ravel(), *[0]*(256*3-COLORS.size)])
        out.save(f'{dst}_{rule}_mask.png')
        Image.fromarray(overlay(gray.astype(np.uint8), mask)).save(f'{dst}_{rule}_overlay.png')
        names = (('large', LARGE), ('small', SMALL), ('background', BACKGROUND), ('ignore', IGNORE))
        print(rule, 'otsu', otsu, {name: round(float(np.mean(mask == v)), 3) for name, v in names})


if __name__ == '__main__':
    main(*sys.argv[1:3])
