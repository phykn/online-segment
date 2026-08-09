from dataclasses import dataclass
from typing import Protocol

import numpy as np
from fastapi import HTTPException, status

from app.data.image import read as read_image

UNLABELED = -1
MAX_DECODED_PIXELS = 128 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class EncodedMask:
    width: int
    height: int
    runs: list[tuple[int, int]]


class MaskLike(Protocol):
    width: int
    height: int
    runs: list[tuple[int, int]]


class TrainItemLike(Protocol):
    image: str
    mask: MaskLike


def _invalid_rle() -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="invalid mask RLE.",
    )


def _decoded_size(width: int, height: int) -> int:
    if width <= 0 or height <= 0:
        _invalid_rle()
    size = width * height
    if size > MAX_DECODED_PIXELS:
        _invalid_rle()
    return size


def decode(mask: MaskLike) -> np.ndarray:
    size = _decoded_size(mask.width, mask.height)
    runs = tuple(mask.runs)
    if not runs:
        _invalid_rle()

    values, lengths = zip(*runs, strict=True)
    if any(length <= 0 for length in lengths) or sum(lengths) != size:
        _invalid_rle()

    try:
        data = np.repeat(
            np.asarray(values, dtype=np.int8),
            np.asarray(lengths, dtype=np.intp),
        )
    except (MemoryError, OverflowError, ValueError):
        _invalid_rle()
    return data.reshape(mask.height, mask.width)


def encode(mask: np.ndarray) -> EncodedMask:
    flat = mask.ravel()
    boundaries = np.flatnonzero(flat[1:] != flat[:-1]) + 1
    starts = np.concatenate(([0], boundaries))
    lengths = np.diff(np.concatenate((starts, [flat.size])))
    runs = list(
        zip(
            flat[starts].astype(int).tolist(),
            lengths.tolist(),
            strict=True,
        )
    )
    height, width = mask.shape
    return EncodedMask(width=width, height=height, runs=runs)


def resize(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    if mask.shape == (height, width):
        return mask

    source_y = np.minimum(
        mask.shape[0] - 1,
        np.arange(height, dtype=np.int64) * mask.shape[0] // height,
    )
    source_x = np.minimum(
        mask.shape[1] - 1,
        np.arange(width, dtype=np.int64) * mask.shape[1] // width,
    )
    return mask[np.ix_(source_y, source_x)]


def read_item(item: TrainItemLike) -> tuple[np.ndarray, np.ndarray]:
    mask = decode(item.mask)
    image = read_image(item.image)
    if image.shape[:2] != mask.shape:
        mask = resize(mask, image.shape[1], image.shape[0])
    return image, mask
