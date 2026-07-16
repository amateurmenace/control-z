"""SAM 2.1 video propagation wrapper (PyTorch v0.1; ONNX diet is v0.3).

Flow: extract analysis-res JPEG frames per shot -> init_state -> add point
prompts -> propagate both directions -> per-frame mask + confidence (the
model's IoU prediction), upscaled to source res with an edge-aware filter.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from czcore import models

CHECKPOINT = "sam2.1_hiera_small.pt"
CONFIG = "configs/sam2.1/sam2.1_hiera_s.yaml"
ANALYSIS_HEIGHT = 720


@dataclass
class Prompt:
    frame: int                 # clip-relative frame index
    xy: Tuple[float, float]    # normalized 0..1
    label: int = 1             # 1 = include, 0 = exclude
    obj: int = 1


@dataclass
class ShotMattes:
    start: int
    end: int
    # obj -> list of (mask_u8 at analysis res) and confidence per frame
    masks: Dict[int, List] = field(default_factory=dict)
    confidence: Dict[int, List[float]] = field(default_factory=dict)


def _device():
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def extract_frames(path: str, start: int, end: int, out_dir: Path,
                   height: int = ANALYSIS_HEIGHT, progress=None) -> Tuple[int, int]:
    """Dump frames [start, end) as JPEGs SAM2's loader accepts. Returns (w, h)."""
    import av
    import cv2

    out_dir.mkdir(parents=True, exist_ok=True)
    w = h = 0
    with av.open(path) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        i = 0
        for frame in container.decode(stream):
            if i >= end:
                break
            if i >= start:
                img = frame.to_ndarray(format="bgr24")
                if not w:
                    sh, sw = img.shape[:2]
                    h = height
                    w = max(2, int(round(sw * h / sh / 2)) * 2)
                small = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(out_dir / f"{i - start:05d}.jpg"), small,
                            [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                if progress and (i - start) % 100 == 0:
                    progress(f"extracting {i - start}")
            i += 1
    return w, h


class StencilEngine:
    def __init__(self, model_size: str = "small"):
        from sam2.build_sam import build_sam2_video_predictor

        ckpt = models.model_path("sam21_small")  # auto-download, hash-verified
        self.device = _device()
        self.predictor = build_sam2_video_predictor(CONFIG, str(ckpt),
                                                    device=self.device)

    def run_shot(self, frames_dir: Path, prompts: List[Prompt],
                 progress=None) -> ShotMattes:
        import numpy as np
        import torch

        n_frames = len(list(frames_dir.glob("*.jpg")))
        state = self.predictor.init_state(video_path=str(frames_dir))
        for p in prompts:
            self.predictor.add_new_points_or_box(
                state, frame_idx=p.frame, obj_id=p.obj,
                points=np.array([[p.xy[0], p.xy[1]]], dtype=np.float32) *
                np.array([[state["video_width"], state["video_height"]]],
                         dtype=np.float32),
                labels=np.array([p.label], dtype=np.int32),
            )
        out = ShotMattes(0, n_frames)
        with torch.inference_mode():
            for fidx, obj_ids, logits in self.predictor.propagate_in_video(state):
                for oi, obj in enumerate(obj_ids):
                    prob = torch.sigmoid(logits[oi]).squeeze()
                    mask = (prob > 0.5).cpu().numpy()
                    # confidence = how certain the model is INSIDE its own matte
                    conf = float(prob[prob > 0.5].mean()) if mask.any() else 0.0
                    out.masks.setdefault(obj, [None] * n_frames)[fidx] = \
                        (mask * 255).astype("uint8")
                    out.confidence.setdefault(obj, [0.0] * n_frames)[fidx] = conf
                if progress and fidx % 25 == 0:
                    progress(f"propagating {fidx}/{n_frames}")
        return out
