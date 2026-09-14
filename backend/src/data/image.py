import base64
import binascii
from io import BytesIO

import numpy as np
from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError


def read_bytes(raw: bytes) -> np.ndarray:
    try:
        with Image.open(BytesIO(raw)) as source:
            oriented = ImageOps.exif_transpose(source)
            return np.asarray(oriented.convert("RGB"))
    except (ValueError, UnidentifiedImageError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid image.",
        ) from error


def read(value: str) -> np.ndarray:
    encoded = value.split(",", 1)[1] if value.startswith("data:") else value

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid image.",
        ) from error
    return read_bytes(raw)


def resize_width(image: np.ndarray, width: int | None) -> np.ndarray:
    if width is None or width >= image.shape[1]:
        return image

    height = max(1, round(image.shape[0] / image.shape[1] * width))
    return np.asarray(
        Image.fromarray(image).resize(
            (width, height),
            Image.Resampling.LANCZOS,
        )
    )
