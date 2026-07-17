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

# one cached image predictor for click-preview — the model loads once and
# every later click answers in well under a second
_img_pred = None
_img_lock = None


def preview_mask(img_bgr, points_norm, labels):
    """One frame, one answer: the mask SAM 2.1 cuts for these clicks RIGHT
    NOW, before any propagation — the feedback loop clicking deserves.
    points_norm: [(x, y)] in 0..1 of the given image. Returns (mask u8, conf)."""
    global _img_pred, _img_lock
    import threading

    import numpy as np
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    if _img_lock is None:
        _img_lock = threading.Lock()
    with _img_lock:
        if _img_pred is None:
            ckpt = models.model_path("sam21_small")
            _img_pred = SAM2ImagePredictor(
                build_sam2(CONFIG, str(ckpt), device=_device()))
        h, w = img_bgr.shape[:2]
        pts = np.array([[x * w, y * h] for x, y in points_norm],
                       dtype=np.float32)
        with torch.inference_mode():
            # ascontiguousarray: the BGR→RGB flip is a negative-stride view,
            # which torch refuses to wrap
            _img_pred.set_image(np.ascontiguousarray(img_bgr[:, :, ::-1]))
            masks, scores, _ = _img_pred.predict(
                point_coords=pts,
                point_labels=np.array(labels, dtype=np.int32),
                multimask_output=False)
    m = (masks[0] > 0.5).astype("uint8") * 255
    return m, float(scores[0])


@dataclass
class Prompt:
    frame: int                 # clip-relative frame index
    xy: Tuple[float, float]    # normalized 0..1
    label: int = 1             # 1 = include, 0 = exclude
    obj: int = 1


def group_prompts(prompts: List[Prompt]) -> Dict[Tuple[int, int], List[Prompt]]:
    """Group points by (frame, object).

    SAM2's add_new_points_or_box defaults to clear_old_points=True, so every
    point for one frame+object MUST go in a single call — feeding them one at a
    time silently keeps only the last (an exclude point alone = empty matte).
    """
    grouped: Dict[Tuple[int, int], List[Prompt]] = {}
    for p in prompts:
        grouped.setdefault((p.frame, p.obj), []).append(p)
    return grouped


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
        scale = np.array([[state["video_width"], state["video_height"]]],
                         dtype=np.float32)
        for (frame_idx, obj_id), pts in sorted(group_prompts(list(prompts)).items()):
            self.predictor.add_new_points_or_box(
                state, frame_idx=frame_idx, obj_id=obj_id,
                points=np.array([[p.xy[0], p.xy[1]] for p in pts],
                                dtype=np.float32) * scale,
                labels=np.array([p.label for p in pts], dtype=np.int32),
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
