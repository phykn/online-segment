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


def append_pair(archive: ZipFile, name: str, image: np.ndarray, mask: np.ndarray) -> None:
    stem = Path(Path(name.replace('\\', '/')).name).stem or 'image'
    used = {value.lower() for value in archive.namelist()}
    base, number = stem, 2
    while any(f'{base}_{kind}.png'.lower() in used for kind in ('image', 'mask')):
        base = f'{stem}_{number}'
        number += 1
    output = BytesIO()
    Image.fromarray(image).save(output, format='PNG', compress_level=config.export.png_compress_level)
    archive.writestr(f'{base}_image.png', output.getvalue())
    archive.writestr(f'{base}_mask.png', make_png(mask, image.shape[1], image.shape[0]))


def make_pair_archive(name: str, image: np.ndarray, mask: np.ndarray) -> bytes:
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_STORED) as archive:
        append_pair(archive, name, image, mask)
    return output.getvalue()
