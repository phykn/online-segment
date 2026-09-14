from pathlib import Path
from typing import Any, BinaryIO, Protocol
from zipfile import ZIP_STORED, ZipFile
from fastapi import HTTPException
from src.data.image import read_bytes, resize_width
from src.data.mask import decode
from src.export.archive import append_pair
from src.export.jobs import jobs
from src.segment import prediction
from src.segment.model import Segmenter

class ExportSession(Protocol):
    id: str
    lock: Any
    segmenter: Segmenter

def append_archive_batch(job_id: str, width: int | None,
        files: list[tuple[str, BinaryIO]], session: ExportSession,
        diameter: float | None = None, edits=None) -> None:
    path = jobs.temp_path(job_id)
    with session.lock:
        state = jobs.get(job_id, session.id)
        remaining = state['total']-state['done']
        if state['status'] != 'running' or not files or len(files) > remaining:
            raise HTTPException(409, 'export job is not accepting images.')
        def check(**kwargs):
            if jobs.get(job_id, session.id)['status'] != 'running':
                raise HTTPException(409, 'export job is not accepting images.')
        try:
            with ZipFile(path, 'a', ZIP_STORED) as archive:
                for index, (name, source) in enumerate(files):
                    check()
                    image = read_bytes(source.read())
                    resized = resize_width(image, width)
                    correction = decode(edits[index]) if edits and edits[index] is not None else None
                    mask = prediction.predict(resized, session.segmenter,
                        diameter, image.shape[1], correction, check)
                    check()
                    append_pair(archive, name, image, mask)
                    done, total = jobs.advance(job_id, session.id)
            if done == total:
                jobs.finish(job_id, session.id, path)
        except Exception as error:
            Path(path).unlink(missing_ok=True)
            jobs.fail(job_id, session.id, str(error))
            raise
