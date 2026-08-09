from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from typing import Any, BinaryIO, Protocol
from zipfile import ZIP_STORED, ZipFile

import numpy as np
from fastapi import HTTPException, status

from app.config import config
from app.data.image import read_bytes, resize_width
from app.export.archive import make_png, unique_png_name
from app.export.jobs import jobs
from app.segment import prediction
from app.segment.model import Segmenter


class ExportSession(Protocol):
    id: str
    lock: Any
    segmenter: Segmenter


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
    session: ExportSession,
) -> None:
    path = jobs.temp_path(job_id)

    with session.lock:
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
                            mask = prediction.predict_features(
                                stack,
                                segmenter,
                                model,
                            )
                        else:
                            mask = prediction.predict_features(
                                stack,
                                segmenter,
                                model,
                                predictor=predictor,
                            )
                        del stack
                        png = make_png(mask, output_width, output_height)
                        archive.writestr(unique_png_name(name, used), png)
                        done, total = jobs.advance(job_id, session.id)

            if done == total:
                jobs.finish(job_id, session.id, path)
        except Exception as error:
            Path(path).unlink(missing_ok=True)
            jobs.fail(job_id, session.id, str(error))
            raise
