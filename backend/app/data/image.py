import base64
import binascii
from io import BytesIO

import numpy as np
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError


def read_bytes(raw: bytes) -> np.ndarray:
    try:
        with Image.open(BytesIO(raw)) as source:
            return np.asarray(source.convert("RGB"))
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
