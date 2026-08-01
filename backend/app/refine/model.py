from pathlib import Path
from threading import RLock
from uuid import uuid4

import numpy as np
import torch
from fastapi import HTTPException, status

from app.config import config
from app.refine import net
from app.segment import feature


class Refiner:
    def __init__(self, path: Path):
        self.path = path
        self.lock = RLock()
        self._cache = {}

    def load(
        self,
        classes: np.ndarray,
        rf_id: str,
        device: torch.device,
    ) -> net.UNet | None:
        if not self.path.exists():
            return None

        stamp = self.path.stat().st_mtime_ns
        key = (stamp, tuple(int(value) for value in classes), rf_id)
        if self._cache.get("key") == key:
            return self._cache["model"]

        try:
            saved = torch.load(self.path, map_location=device, weights_only=True)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="refine model could not be loaded.",
            ) from error
        if (
            not isinstance(saved, dict)
            or saved.get("features") != feature.config()
            or saved.get("classes") != list(key[1])
            or saved.get("rf_id") != rf_id
        ):
            return None

        corrector = net.UNet(len(classes)).to(device)
        try:
            corrector.load_state_dict(saved["state"])
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="refine model could not be loaded.",
            ) from error
        corrector.eval()
        self._cache.update(key=key, model=corrector)
        return corrector

    def save(
        self,
        corrector: net.UNet,
        classes: np.ndarray,
        rf_id: str,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        values = [int(value) for value in classes]
        try:
            torch.save(
                {
                    "features": feature.config(),
                    "classes": values,
                    "rf_id": rf_id,
                    "state": corrector.state_dict(),
                },
                tmp,
            )
            tmp.replace(self.path)
            key = (self.path.stat().st_mtime_ns, tuple(values), rf_id)
            self._cache.update(key=key, model=corrector)
        finally:
            tmp.unlink(missing_ok=True)

    def reset(self) -> None:
        with self.lock:
            self.path.unlink(missing_ok=True)
            self._cache.clear()

    def adjust(
        self,
        image: np.ndarray,
        probs: np.ndarray,
        classes: np.ndarray,
        rf_id: str,
    ) -> np.ndarray:
        if not self.path.exists():
            return probs

        device = net.device()
        with self.lock:
            corrector = self.load(classes, rf_id, device)
            if corrector is None:
                return probs
            value = torch.from_numpy(net.input(image, probs)[None]).to(device)
            use_amp = device.type == "cuda"
            with (
                torch.no_grad(),
                torch.autocast(
                    device_type=device.type,
                    dtype=torch.float16,
                    enabled=use_amp,
                ),
            ):
                output = torch.softmax(corrector(value), dim=1)[0]
            return output.float().cpu().numpy().transpose(1, 2, 0)
