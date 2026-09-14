from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import numpy as np
from fastapi import HTTPException, status
from PIL import Image

from src.config import config
from src.data.mask import UNLABELED


def make_png(mask: np.ndarray, width: int, height: int) -> bytes:
    if mask.min() < UNLABELED or mask.max() >= len(config.export.colors):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="mask labels must be -1, 0, 1, 2, or 3.",
        )

    data = mask.astype(np.uint8, copy=False)
    image = Image.frombytes("P", (data.shape[1], data.shape[0]), data.tobytes())
    palette = [value for color in config.export.colors for value in color]
    image.putpalette(palette + [0] * (768 - len(palette)))
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.NEAREST)

    output = BytesIO()
    image.save(
        output,
        format="PNG",
        compress_level=config.export.png_compress_level,
    )
    return output.getvalue()


def make_mask_archive(
    files: list[tuple[str, np.ndarray]],
    width: int,
    height: int,
) -> bytes:
    output = BytesIO()
    used = set()
    with ZipFile(output, "w", ZIP_STORED) as archive:
        for name, mask in files:
            archive.writestr(
                unique_png_name(name, used),
                make_png(mask, width, height),
            )
    return output.getvalue()


def unique_png_name(name: str, used: set[str]) -> str:
    path = Path(name.replace("\\", "/")).name
    stem = Path(path).stem or "mask"
    value = f"{stem}.png"
    number = 2
    while value.lower() in used:
        value = f"{stem}_{number}.png"
        number += 1
    used.add(value.lower())
    return value
