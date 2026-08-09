from collections.abc import Iterator
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from zipfile import ZIP_STORED, ZipFile

import numpy as np
from fastapi import HTTPException, status
from PIL import Image

from app import actions
from app.config import config
from app.data.image import read_bytes, resize_width
from app.data.mask import UNLABELED
from app.export.jobs import jobs
from app.segment.model import Segmenter
from app.session import ModelSession


def make_png(mask: np.ndarray, width: int, height: int) -> bytes:
    ignore = UNLABELED
    if mask.min() < ignore or mask.max() >= len(config.export.colors):
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
    # Fast compression shrinks spatial masks before disk and network I/O.
    image.save(
        output,
        format="PNG",
        compress_level=config.performance.export.png_compress_level,
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
                _unique_png_name(name, "", used),
                make_png(mask, width, height),
            )
    return output.getvalue()


def _prepare_file(
    name: str,
    source: BinaryIO,
    width: int | None,
    segmenter: Segmenter,
) -> tuple[str, int, int, np.ndarray]:
    image = read_bytes(source.read())
    resized = resize_width(image, width)
    stack = segmenter.features(resized, cached=False)
    return name, image.shape[1], image.shape[0], stack


def _prepared_files(
    files: list[tuple[str, BinaryIO]],
    width: int | None,
    segmenter: Segmenter,
) -> Iterator[tuple[str, int, int, np.ndarray]]:
    if len(files) == 1:
        name, source = files[0]
        yield _prepare_file(name, source, width, segmenter)
        return

    items = iter(files)
    name, source = next(items)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(_prepare_file, name, source, width, segmenter)

        for name, source in items:
            prepared = pending.result()
            pending = pool.submit(_prepare_file, name, source, width, segmenter)
            yield prepared

        yield pending.result()


def append_archive_batch(
    job_id: str,
    width: int | None,
    files: list[tuple[str, BinaryIO]],
    session: ModelSession,
) -> None:
    path = jobs.temp_path(job_id)
    state = jobs.get(job_id, session.id)
    remaining = state["total"] - state["done"]
    if (
        state["status"] != "running"
        or not files
        or len(files) > remaining
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="export job is not accepting images.",
        )

    try:
        with session.lock:
            segmenter = session.segmenter
            model = segmenter.load()
            with ZipFile(path, "a", ZIP_STORED) as archive:
                used = {value.lower() for value in archive.namelist()}
                with closing(
                    _prepared_files(files, width, segmenter)
                ) as prepared:
                    predictor = None
                    predictor_checked = False
                    for name, output_width, output_height, stack in prepared:
                        if jobs.get(job_id, session.id)["status"] != "running":
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail="export job is not accepting images.",
                            )

                        if not predictor_checked:
                            predictor_checked = True
                            pixels = stack.shape[0] * stack.shape[1]
                            threshold = config.performance.export.gpu_min_pixels
                            if pixels * state["total"] >= threshold:
                                predictor = segmenter.batch_predictor(model)

                        if predictor is None:
                            mask = actions.predict_features(
                                stack, segmenter, model
                            )
                        else:
                            mask = actions.predict_features(
                                stack, segmenter, model, predictor=predictor
                            )
                        del stack
                        png = make_png(mask, output_width, output_height)
                        archive.writestr(
                            _unique_png_name(name, "", used),
                            png,
                        )
                        done, total = jobs.advance(job_id, session.id)

            if done == total:
                jobs.finish(job_id, session.id, path)
    except Exception as error:
        Path(path).unlink(missing_ok=True)
        jobs.fail(job_id, session.id, str(error))
        raise


def _unique_png_name(name: str, suffix: str, used: set[str]) -> str:
    path = Path(name.replace("\\", "/")).name
    stem = Path(path).stem or "mask"
    value = f"{stem}{suffix}.png"
    number = 2
    while value.lower() in used:
        value = f"{stem}{suffix}_{number}.png"
        number += 1
    used.add(value.lower())
    return value
