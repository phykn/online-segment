from dataclasses import dataclass
from importlib.metadata import version

import numpy as np
from fastapi import HTTPException


class EncoderCapture:
    """Capture normalized spatial tokens without changing Cellpose's forward pass."""

    def __init__(self, model, shape, output_shape, tile_size, overlap):
        self.model = model
        self.shape = shape
        self.output_shape = output_shape
        self.tile_size = tile_size
        self.overlap = overlap
        self.tiles = []
        self.hook = None

    def __enter__(self):
        dimensions = {'dino_vitb': 768, 'dino_vitl': 1024}
        channels = dimensions.get(self.model.backbone)
        if (version('cellpose') != '4.2.1.1' or channels is None
                or self.model.net.ps != 8 or self.model.net.out.in_features != channels):
            raise HTTPException(503, 'Encoder features require Cellpose 4.2.1.1 CPDINO ViT-B or ViT-L with stride 8.')
        self.side = self.tile_size // self.model.net.ps
        self.channels = channels
        self.hook = self.model.net.out.register_forward_pre_hook(self.collect)
        return self

    def collect(self, module, args):
        import torch
        value = args[0].detach().to(device='cpu', dtype=torch.float32).numpy()
        if value.shape[1:] != (self.side*self.side, self.channels):
            raise ValueError('Unexpected CPDINO token geometry.')
        self.tiles.extend(value.reshape(-1, self.side, self.side, self.channels))

    def __exit__(self, *args):
        self.hook.remove()

    def tokens(self):
        from cellpose.transforms import get_pad_yx
        h, w = self.shape
        pad = get_pad_yx(h, w, min_size=(self.tile_size, self.tile_size))
        ly, lx = h+pad[0]+pad[1], w+pad[2]+pad[3]
        ny = 1 if ly <= self.tile_size else int(np.ceil((1+2*self.overlap)*ly/self.tile_size))
        nx = 1 if lx <= self.tile_size else int(np.ceil((1+2*self.overlap)*lx/self.tile_size))
        regions = [(int(y), int(x)) for y in np.linspace(0, ly-self.tile_size, ny).astype(int)
                   for x in np.linspace(0, lx-self.tile_size, nx).astype(int)]
        if len(self.tiles) != len(regions):
            raise ValueError('Unexpected Cellpose tile count.')
        return Tokens(self.tiles, self.shape, regions, pad, self.tile_size, self.output_shape)


@dataclass
class Tokens:
    tiles: list
    shape: tuple
    regions: list
    padding: tuple
    tile_size: int
    output_shape: tuple | None = None

    @property
    def nbytes(self):
        return sum(tile.nbytes for tile in self.tiles)

    def sample(self, limit):
        if limit <= 0:
            return np.empty((0, self.tiles[0].shape[-1]), np.float32)
        total = sum(tile.shape[0]*tile.shape[1] for tile in self.tiles)
        count = min(limit, total)
        indices = ((np.arange(count)+.5)*total/count).astype(int)
        values = []
        offset = 0
        for tile in self.tiles:
            flat = tile.reshape(-1, tile.shape[-1])
            selected = indices[(indices >= offset) & (indices < offset+len(flat))]-offset
            values.append(flat[selected].astype(np.float32))
            offset += len(flat)
        return np.concatenate(values)

    def project(self, pca):
        tiles = [pca.transform(tile.reshape(-1, tile.shape[-1]).astype(np.float32))
                 .reshape(*tile.shape[:2], -1).astype(np.float32) for tile in self.tiles]
        return Tokens(tiles, self.shape, self.regions, self.padding, self.tile_size, self.output_shape)

    def pixels(self, indices):
        if self.output_shape is None or self.output_shape == self.shape:
            return self._pixels(indices)
        # Match Cellpose's final OpenCV resize after tile blending and unpadding.
        y, x = np.divmod(indices, self.output_shape[1])
        y = np.clip((y+.5)*self.shape[0]/self.output_shape[0]-.5, 0, self.shape[0]-1)
        x = np.clip((x+.5)*self.shape[1]/self.output_shape[1]-.5, 0, self.shape[1]-1)
        iy, ix = y.astype(int), x.astype(int)
        wy, wx = y-iy, x-ix
        result = np.zeros((len(indices), self.tiles[0].shape[-1]), np.float32)
        for dy, dx, weights in ((0, 0, (1-wy)*(1-wx)), (0, 1, (1-wy)*wx),
                                (1, 0, wy*(1-wx)), (1, 1, wy*wx)):
            selected = np.minimum(iy+dy, self.shape[0]-1)*self.shape[1]+np.minimum(ix+dx, self.shape[1]-1)
            result += self._pixels(selected)*weights[:, None]
        return result

    def _pixels(self, indices):
        from cellpose.transforms import _taper_mask
        y, x = np.divmod(indices, self.shape[1])
        y, x = y+self.padding[0], x+self.padding[2]
        result = np.zeros((len(indices), self.tiles[0].shape[-1]), np.float32)
        weights = np.zeros(len(indices), np.float32)
        taper = _taper_mask(self.tile_size, self.tile_size)
        for tile, (y0, x0) in zip(self.tiles, self.regions, strict=True):
            selected = np.flatnonzero((y >= y0) & (y < y0+self.tile_size) &
                                      (x >= x0) & (x < x0+self.tile_size))
            if not len(selected):
                continue
            yy, xx = y[selected]-y0, x[selected]-x0
            # OpenCV half-pixel interpolation evaluated at requested pixels only.
            fy = np.clip((yy+.5)*tile.shape[0]/self.tile_size-.5, 0, tile.shape[0]-1)
            fx = np.clip((xx+.5)*tile.shape[1]/self.tile_size-.5, 0, tile.shape[1]-1)
            iy, ix = fy.astype(int), fx.astype(int)
            jy, jx = np.minimum(iy+1, tile.shape[0]-1), np.minimum(ix+1, tile.shape[1]-1)
            wy, wx = (fy-iy)[:, None], (fx-ix)[:, None]
            value = (tile[iy, ix]*(1-wx)+tile[iy, jx]*wx)*(1-wy) + (tile[jy, ix]*(1-wx)+tile[jy, jx]*wx)*wy
            weight = taper[yy, xx]
            result[selected] += value * weight[:, None]
            weights[selected] += weight
        if np.any(weights == 0):
            raise ValueError('Encoder tiles do not cover the image.')
        return result / weights[:, None]


