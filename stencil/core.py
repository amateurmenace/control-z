"""SAM 2.1 video propagation wrapper (PyTorch v0.1; ONNX diet is v0.3).

Flow: extract analysis-res JPEG frames per shot -> init_state -> add point
prompts -> propagate both directions -> per-frame mask + confidence (the
model's IoU prediction), upscaled to source res with an edge-aware filter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from czcore import models

# the engine file owns the model constants (it also runs as the signed
# app's helper, where nothing but itself is importable)
from .sam2_engine import CONFIG, WINDOW_FRAMES  # noqa: F401

CHECKPOINT = "sam2.1_hiera_small.pt"
ANALYSIS_HEIGHT = 720

# one cached image predictor for click-preview — the model loads once and
# every later click answers in well under a second
_img_pred = None
_img_lock = None


def preview_mask(img_bgr, points_norm, labels):
    """One frame, one answer: the mask SAM 2.1 cuts for these clicks RIGHT
    NOW, before any propagation — the feedback loop clicking deserves.
    points_norm: [(x, y)] in 0..1 of the given image. Returns (mask u8, conf).
    In-process (a source checkout's venv); the signed app goes through
    stencil.helper instead — same engine file, its own Python."""
    global _img_pred, _img_lock
    import threading

    from .sam2_engine import Preview

    if _img_lock is None:
        _img_lock = threading.Lock()
    with _img_lock:
        if _img_pred is None:
            _img_pred = Preview(str(models.model_path("sam21_small")), CONFIG)
        # the BGR→RGB flip is a negative-stride view; Preview makes it
        # contiguous before torch wraps it
        return _img_pred.mask(img_bgr[:, :, ::-1], points_norm, labels)


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
    """In-process SAM 2.1 (a source checkout with torch in its venv). The
    work lives in stencil/sam2_engine.py, shared with the signed app's
    helper process — one implementation, two ways to run it."""

    def __init__(self, model_size: str = "small"):
        from .sam2_engine import Engine

        ckpt = models.model_path("sam21_small")  # auto-download, hash-verified
        self._eng = Engine(str(ckpt), CONFIG)
        self.device = self._eng.device

    def run_shot(self, frames_dir: Path, prompts: List[Prompt],
                 progress=None) -> ShotMattes:
        dicts = [{"frame": p.frame, "x": p.xy[0], "y": p.xy[1],
                  "label": p.label, "obj": p.obj} for p in prompts]
        masks, conf = self._eng.run_shot(frames_dir, dicts, progress=progress)
        n = len(next(iter(masks.values()), []))
        out = ShotMattes(0, n)
        out.masks, out.confidence = masks, conf
        return out
