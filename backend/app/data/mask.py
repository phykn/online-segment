import numpy as np
from fastapi import HTTPException, status

from app.api.schema import Mask, TrainItem
from app.data.image import read as read_image

UNLABELED = -1


def decode(mask: Mask) -> np.ndarray:
    size = mask.width * mask.height
    data = np.empty(size, dtype=np.int8)
    offset = 0

    for value, length in mask.runs:
        if length <= 0 or offset + length > size:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="invalid mask RLE.",
            )
        data[offset : offset + length] = value
        offset += length

    if offset != size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid mask RLE.",
        )
    return data.reshape(mask.height, mask.width)


def encode(mask: np.ndarray) -> Mask:
    flat = mask.ravel()
    runs = []
    value = int(flat[0])
    length = 1

    for current in flat[1:]:
        current = int(current)
        if current == value:
            length += 1
        else:
            runs.append((value, length))
            value = current
            length = 1

    runs.append((value, length))
    height, width = mask.shape
    return Mask(width=width, height=height, runs=runs)


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


def read_item(item: TrainItem) -> tuple[np.ndarray, np.ndarray]:
    mask = decode(item.mask)
    image = read_image(item.image)
    if image.shape[:2] != mask.shape:
        mask = resize(mask, image.shape[1], image.shape[0])
    return image, mask
