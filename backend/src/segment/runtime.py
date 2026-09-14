from contextlib import nullcontext
from threading import RLock

import numpy as np
from fastapi import HTTPException

from src import ROOT
from src.config import config, CellposeParameters
from src.segment.encoder import EncoderCapture
from src.segment.flow import trace


class CellposeRuntime:
    def __init__(self):
        self.lock = RLock()
        self.model = None
        self.signature = None

    def load(self):
        cfg = config.cellpose
        signature = (cfg.checkpoint, cfg.device, cfg.threads)
        if self.model is not None and self.signature == signature:
            return self.model
        checkpoint = ROOT / cfg.checkpoint
        if not checkpoint.is_file():
            raise HTTPException(503, 'Cellpose weights are missing. Run `git lfs pull` from the repository root.')
        try:
            import torch
            from cellpose.models import CellposeModel
        except ImportError as error:
            raise HTTPException(503, 'Install backend requirements, including cellpose and dinov3.') from error

        device = ('cuda' if torch.cuda.is_available() else 'cpu') if cfg.device == 'auto' else cfg.device
        if device == 'cuda' and not torch.cuda.is_available():
            raise HTTPException(503, 'CUDA is unavailable. Set cellpose.device to auto or cpu.')
        torch.set_num_threads(cfg.threads)
        self.model = None
        self.signature = None
        self.model = CellposeModel(
            pretrained_model=str(checkpoint),
            device=torch.device(device),
            use_bfloat16=device == 'cuda' and torch.cuda.is_bf16_supported(),
        )
        self.signature = signature
        return self.model

    def run(self, image, capture=False, compute_masks=True, progress=lambda **kwargs: None, parameters=None, flow=False):
        cfg = config.cellpose
        parameters = parameters if parameters is not None else CellposeParameters.defaults()
        scale = 30./parameters.diameter if parameters.diameter is not None else 1.
        h, w = (int(size*scale) for size in image.shape[:2])
        if min(h, w) < 2:
            raise HTTPException(422, 'Diameter is too large for this image. Use a smaller value.')
        if max(image.shape[0]*image.shape[1], h*w) > cfg.max_pixels:
            raise HTTPException(422, 'Image is too large. Reduce the working width.')
        progress(stage='waiting', done=0, total=1)
        with self.lock:
            model = self.load()
            progress(stage='segmenting' if compute_masks else 'features', done=0, total=1)
            encoder = EncoderCapture(model, (h, w), image.shape[:2], cfg.tile_size, cfg.overlap) if capture else None
            with encoder if capture else nullcontext():
                masks, flows, _ = model.eval(
                    image, channel_axis=-1, batch_size=cfg.batch_size, normalize=True,
                    diameter=parameters.diameter, bsize=cfg.tile_size, tile_overlap=cfg.overlap,
                    flow_threshold=parameters.flow_threshold, cellprob_threshold=parameters.cellprob_threshold,
                    min_size=parameters.min_area, augment=False, compute_masks=compute_masks,
                    resample=True,
                )
            encoded = encoder.tokens() if capture else None
            logits = np.asarray(flows[2], np.float32)
            endpoints = None
            if flow:
                endpoints = trace(flows[1], logits, parameters.cellprob_threshold,
                                  int(200/scale), model.device)
            progress(stage='ready', done=1, total=1)
            return np.asarray(masks, np.int32), logits, encoded, endpoints


runtime = CellposeRuntime()
