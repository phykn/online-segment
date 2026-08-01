import numpy as np
import torch
from scipy.ndimage import sobel
from torch import nn
from torch.nn import functional

from app.config import config
from app.segment import feature


cfg = config.refine


class Block(nn.Module):
    def __init__(self, input_count: int, output_count: int):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(input_count, output_count, 3, padding=1),
            nn.GroupNorm(4, output_count),
            nn.ReLU(inplace=True),
            nn.Conv2d(output_count, output_count, 3, padding=1),
            nn.GroupNorm(4, output_count),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.layers(x)


class Context(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.branches = nn.ModuleList(
            nn.Sequential(
                nn.Conv2d(
                    channels,
                    channels,
                    3,
                    padding=rate,
                    dilation=rate,
                ),
                nn.GroupNorm(4, channels),
                nn.ReLU(inplace=True),
            )
            for rate in cfg.dilations
        )
        self.merge = nn.Conv2d(channels * 3, channels, 1)
        self.act = nn.ReLU(inplace=True)

    def forward(self, x):
        values = torch.cat([branch(x) for branch in self.branches], dim=1)
        return self.act(x + self.merge(values))


class UNet(nn.Module):
    def __init__(self, count: int):
        super().__init__()
        self.pool = nn.MaxPool2d(2)
        self.enc1 = Block(count + 2, cfg.base)
        self.enc2 = Block(cfg.base, cfg.base * 2)
        self.mid = Block(cfg.base * 2, cfg.base * 4)
        self.context = Context(cfg.base * 4)
        self.dec2 = Block(cfg.base * 6, cfg.base * 2)
        self.dec1 = Block(cfg.base * 3, cfg.base)
        self.out = nn.Conv2d(cfg.base, count, 1)
        nn.init.zeros_(self.out.weight)
        nn.init.zeros_(self.out.bias)

    def forward(self, x):
        first = self.enc1(x)
        second = self.enc2(self.pool(first))
        middle = self.context(self.mid(self.pool(second)))
        up = functional.interpolate(
            middle,
            size=second.shape[-2:],
            mode="bilinear",
            align_corners=False,
        )
        up = self.dec2(torch.cat((up, second), dim=1))
        up = functional.interpolate(
            up,
            size=first.shape[-2:],
            mode="bilinear",
            align_corners=False,
        )
        delta = self.out(self.dec1(torch.cat((up, first), dim=1)))
        base = torch.log(x[:, 2:].clamp_min(1e-5))
        return base + delta


def device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def input(image: np.ndarray, probs: np.ndarray) -> np.ndarray:
    gray = feature.normalize(image)
    edge = np.hypot(
        sobel(gray, axis=1, mode="reflect"),
        sobel(gray, axis=0, mode="reflect"),
    )
    high = np.percentile(edge, 99.0)
    if high > 0:
        edge = np.clip(edge / high, 0.0, 1.0)
    return np.concatenate(
        (gray[None], edge[None], probs.transpose(2, 0, 1)),
        axis=0,
    ).astype(np.float32, copy=False)
