from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from zipfile import ZIP_STORED, ZipFile

import numpy as np
from fastapi import HTTPException, status
from PIL import Image

from app import actions
from app.config import config
from app.data.image import read_bytes
from app.export.jobs import jobs
from app.segment.model import segmenter


def make_png(mask: np.ndarray, width: int, height: int) -> bytes:
    ignore = config.refine.ignore
    valid = (mask == ignore) | (
        (mask >= 0) & (mask < len(config.export.colors))
    )
    if not np.all(valid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="mask labels must be -1, 0, 1, 2, or 3.",
        )

    data = mask.astype(np.int16)
    data[data == ignore] = 255
    data = data.astype(np.uint8)
    image = Image.frombytes("P", (data.shape[1], data.shape[0]), data.tobytes())
    palette = [value for color in config.export.colors for value in color]
    image.putpalette(palette + [0] * (768 - len(palette)))
    image = image.resize((width, height), Image.Resampling.NEAREST)

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def make_archive(
    job_id: str,
    width: int,
    files: list[tuple[str, BinaryIO]],
) -> None:
    jobs.start(job_id, len(files))
    path = jobs.temp_path(job_id)
    model = segmenter.load()
    used = set()

    try:
        with ZipFile(path, "w", ZIP_STORED) as archive:
            for index, (name, file) in enumerate(files, start=1):
                image = read_bytes(file.read())
                height = max(1, round(image.shape[0] / image.shape[1] * width))
                resized = np.asarray(
                    Image.fromarray(image).resize(
                        (width, height),
                        Image.Resampling.LANCZOS,
                    )
                )
                mask = actions.predict(resized, model)
                png = make_png(mask, image.shape[1], image.shape[0])
                archive.writestr(_mask_name(name or f"image_{index}", used), png)
                jobs.update(job_id, index)
        jobs.finish(job_id, path)
    except Exception as error:
        Path(path).unlink(missing_ok=True)
        jobs.fail(job_id, str(error))
        raise


def _mask_name(name: str, used: set[str]) -> str:
    path = Path(name.replace("\\", "/")).name
    stem = Path(path).stem or "mask"
    value = f"{stem}_mask.png"
    number = 2
    while value.lower() in used:
        value = f"{stem}_mask_{number}.png"
        number += 1
    used.add(value.lower())
    return value
