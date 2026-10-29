"""Frozen DINOv3 patch tokens at several input magnifications.

Upscaling the image before encoding shrinks each 16px token to 16/scale original pixels, so thin
structures such as cracks reach token resolution while the 1x level keeps wide semantic context.
"""
from dataclasses import dataclass
from threading import RLock

import numpy as np
from fastapi import HTTPException

from src import ROOT
from src.config import config

MEAN = np.array([.485, .456, .406], np.float32)
STD = np.array([.229, .224, .225], np.float32)
PATCH = 16
# Fewer tiles than this give a per-position mean that is mostly image content, not artifact.
MIN_TILES = 8


def channels(image, mode):
    rgb = image.astype(np.float32) / 255
    if mode == 'rgb':
        return rgb
    import cv2
    gray = rgb @ np.array([.2126, .7152, .0722], np.float32)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    contrast = gray - cv2.GaussianBlur(gray, (0, 0), 8)
    tophat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    return np.stack([gray, stretch(contrast), stretch(tophat)], -1).astype(np.float32)


def stretch(value):
    low, high = np.percentile(value, [1, 99])
    return np.clip((value-low)/(high-low), 0, 1) if high > low else np.zeros_like(value)


@dataclass
class Level:
    grid: np.ndarray  # (gh, gw, 768) tokens of the upscaled, padded image
    scale: tuple      # upscaled size / original size per axis

    def sample(self, limit):
        flat = self.grid.reshape(-1, self.grid.shape[-1])
        count = min(limit, len(flat))
        return flat[((np.arange(count)+.5)*len(flat)/count).astype(int)].astype(np.float32)

    def pixels(self, indices, width):
        y, x = np.divmod(indices, width)
        # Token j is centred at upscaled pixel 16j+8.
        ty = np.clip(((y+.5)*self.scale[0]-PATCH/2)/PATCH, 0, self.grid.shape[0]-1)
        tx = np.clip(((x+.5)*self.scale[1]-PATCH/2)/PATCH, 0, self.grid.shape[1]-1)
        iy, ix = ty.astype(int), tx.astype(int)
        jy, jx = np.minimum(iy+1, self.grid.shape[0]-1), np.minimum(ix+1, self.grid.shape[1]-1)
        wy, wx = (ty-iy)[:, None], (tx-ix)[:, None]
        g = self.grid
        return ((g[iy, ix]*(1-wx) + g[iy, jx]*wx)*(1-wy) + (g[jy, ix]*(1-wx) + g[jy, jx]*wx)*wy).astype(np.float32)


@dataclass
class Pyramid:
    levels: list
    shape: tuple
    field: np.ndarray | None = None  # (pixels, dims) projected tokens, filled by project

    @property
    def nbytes(self):
        return self.field.nbytes if self.field is not None else sum(level.grid.nbytes for level in self.levels)

    def sample(self, limit):
        return [level.sample(limit) for level in self.levels]

    def project(self, pcas):
        # PCA and bilinear interpolation are both linear (weights sum to 1), so projecting each
        # token grid first equals interpolating all 768 dims. Every brush edit refits the trees
        # and predicts every pixel again, so the interpolated field is built once per image.
        levels = [Level(pca.transform(level.grid.reshape(-1, level.grid.shape[-1]).astype(np.float32))
                        .reshape(*level.grid.shape[:2], -1).astype(np.float32), level.scale)
                  for level, pca in zip(self.levels, pcas, strict=True)]
        size = self.shape[0]*self.shape[1]
        field = np.empty((size, sum(level.grid.shape[-1] for level in levels)), np.float32)
        for start in range(0, size, 1 << 20):
            idx = np.arange(start, min(size, start + (1 << 20)))
            field[idx] = np.concatenate([level.pixels(idx, self.shape[1]) for level in levels], axis=1)
        return Pyramid(levels, self.shape, field)

    def pixels(self, indices):
        return self.field[indices]


class DinoEncoder:
    def __init__(self):
        self.lock = RLock()
        self.model = None
        self.device = None
        self.signature = None

    def load(self):
        cfg = config.dino
        signature = (cfg.checkpoint, cfg.arch, cfg.device)
        if self.model is not None and self.signature == signature:
            return self.model
        checkpoint = ROOT / cfg.checkpoint
        if not checkpoint.is_file():
            raise HTTPException(503, f'DINOv3 weights are missing: {cfg.checkpoint}.')
        try:
            import torch
            from dinov3.hub import backbones
        except ImportError as error:
            raise HTTPException(503, 'Install backend requirements, including torch and dinov3.') from error
        if cfg.device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
        else:
            device = cfg.device
        model = getattr(backbones, f'dinov3_{cfg.arch}')(pretrained=False)
        model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True))
        self.model, self.device, self.signature = model.eval().to(device), device, signature
        return self.model

    def run(self, image, progress=lambda **kwargs: None):
        cfg = config.dino
        x = (channels(image, cfg.channels) - MEAN) / STD
        with self.lock:
            model = self.load()
            levels = []
            for i, scale in enumerate(cfg.scales):
                progress(stage='features', done=i, total=len(cfg.scales))
                levels.append(self.encode(model, x, scale))
        return Pyramid(levels, image.shape[:2])

    def encode(self, model, x, scale):
        import torch
        import torch.nn.functional as F
        cfg = config.dino
        h, w = x.shape[:2]
        sh, sw = max(1, round(h*scale)), max(1, round(w*scale))
        if -(-sh//PATCH) * -(-sw//PATCH) > cfg.max_tokens:
            raise HTTPException(422, f'Image is too large for DINO scale {scale:g}. Reduce the working width or dino.scales.')
        image = torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1)))[None]
        image = F.interpolate(image, size=(sh, sw), mode='bilinear', align_corners=False, antialias=scale < 1)
        tile, overlap = cfg.tile, cfg.overlap
        ph, pw = max(tile, -(-sh//PATCH)*PATCH), max(tile, -(-sw//PATCH)*PATCH)
        image = F.pad(image, (0, pw-sw, 0, ph-sh), mode='replicate')
        side = tile // PATCH
        ramp = torch.minimum(torch.arange(side)+1, side-torch.arange(side)).float().clamp(max=max(1, overlap//PATCH))
        taper = (ramp[:, None]*ramp[None])[..., None]
        total = torch.zeros(ph//PATCH, pw//PATCH, model.embed_dim)
        weight = torch.zeros(ph//PATCH, pw//PATCH, 1)
        position = torch.zeros(side, side, model.embed_dim)
        corners = []
        with torch.no_grad():
            for y0 in starts(ph, tile, tile-overlap):
                for x0 in starts(pw, tile, tile-overlap):
                    crop = image[..., y0:y0+tile, x0:x0+tile].to(self.device)
                    tokens = model.get_intermediate_layers(crop, n=1, reshape=True, norm=True)[0][0]
                    tokens = tokens.permute(1, 2, 0).float().cpu()
                    ty, tx = y0//PATCH, x0//PATCH
                    total[ty:ty+side, tx:tx+side] += tokens*taper
                    weight[ty:ty+side, tx:tx+side] += taper
                    position += tokens
                    corners.append((ty, tx))
        if cfg.debias and len(corners) >= MIN_TILES:
            # A magnified tile is nearly uniform, so its tokens largely encode their place in the
            # tile. That pattern repeats in every tile; the per-position mean over tiles estimates it.
            bias = position/len(corners)
            bias -= bias.mean((0, 1))
            for ty, tx in corners:
                total[ty:ty+side, tx:tx+side] -= bias*taper
        grid = (total/weight)[:-(-sh//PATCH), :-(-sw//PATCH)]
        return Level(grid.numpy().astype(np.float16), (sh/h, sw/w))


def starts(size, tile, step):
    values = list(range(0, size-tile+1, step))
    if values[-1] != size-tile:
        values.append(size-tile)
    return values


encoder = DinoEncoder()
