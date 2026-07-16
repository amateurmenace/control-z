"""rise.engine — the upscaler behind both Rise-the-app and Pivot's punch-ins.

Frozen API (specs/00-overview.md):

    upscale(frames, scale, model="auto", device="auto", tile=512, on_progress=None)
    upscale_frame(bgr, scale, model="auto", ...)

Backends, in order of preference when model="auto":
  * "realesrgan-x4" / "realesrgan-x2" — ONNX Runtime, tiled with overlap blend.
    Registered in czcore.models once we've converted + hash-pinned our own
    export (Rise task); until then requesting it raises a clear error.
  * "lanczos" — Lanczos4 + edge-masked unsharp. Always available, honest
    fallback: real resampling, no invented detail, labeled in every report.

Every result carries which backend actually ran — Pivot's QC report and
Rise's UI must never imply reconstruction that didn't happen (covenant).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

from czcore import models


@dataclass
class EngineInfo:
    backend: str          # what actually ran, e.g. "realesrgan-x4" or "lanczos"
    scale: int
    synthesized: bool     # True when a generative model added texture


def available_backends() -> list:
    out = ["lanczos"]
    for name in ("realesrgan-x2", "realesrgan-x4"):
        key = name.replace("-", "_").replace("realesrgan", "realesrgan")
        if name.replace("-", "_") in models.REGISTRY or name in models.REGISTRY:
            out.append(name)
    return out


def resolve_model(model: str) -> str:
    if model == "auto":
        for m in ("realesrgan-x4", "realesrgan-x2"):
            if m in models.REGISTRY:
                return m
        return "lanczos"
    if model != "lanczos" and model not in models.REGISTRY:
        raise ValueError(
            f"rise backend {model!r} isn't available yet — the model hasn't been "
            f"converted and hash-pinned. Available: {available_backends()}"
        )
    return model


def _lanczos(bgr, scale: int):
    import cv2
    import numpy as np

    h, w = bgr.shape[:2]
    up = cv2.resize(bgr, (w * scale, h * scale), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(up, (0, 0), 1.0)
    sharp = cv2.addWeighted(up, 1.35, blur, -0.35, 0)
    # mask the sharpen off flat areas so we don't crisp the noise
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    edges = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) ** 2 + \
        cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) ** 2
    m = np.clip(edges / (edges.mean() * 4 + 1e-6), 0, 1)[..., None].astype(np.float32)
    out = up.astype(np.float32) * (1 - m) + sharp.astype(np.float32) * m
    return out.clip(0, 255).astype(np.uint8)


class _OnnxSR:
    """Tiled Real-ESRGAN-style x4/x2 runner (activated by the Rise task)."""

    def __init__(self, model_name: str, tile: int = 512, overlap: int = 16,
                 device: str = "auto"):
        import onnxruntime as ort

        self.tile, self.overlap = tile, overlap
        providers = ["CPUExecutionProvider"]
        if device in ("auto", "coreml"):
            avail = ort.get_available_providers()
            if "CoreMLExecutionProvider" in avail:
                providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        self.sess = ort.InferenceSession(str(models.model_path(model_name)),
                                         providers=providers)
        self.input_name = self.sess.get_inputs()[0].name
        self.scale = 4 if "x4" in model_name else 2

    def run(self, bgr):
        import numpy as np

        h, w = bgr.shape[:2]
        s, t, o = self.scale, self.tile, self.overlap
        out = np.zeros((h * s, w * s, 3), dtype=np.float32)
        weight = np.zeros((h * s, w * s, 1), dtype=np.float32)
        for y0 in range(0, h, t - 2 * o):
            for x0 in range(0, w, t - 2 * o):
                y1, x1 = min(y0 + t, h), min(x0 + t, w)
                patch = bgr[y0:y1, x0:x1].astype(np.float32) / 255.0
                inp = patch[..., ::-1].transpose(2, 0, 1)[None]  # RGB CHW
                res = self.sess.run(None, {self.input_name: inp})[0][0]
                res = res.transpose(1, 2, 0)[..., ::-1]  # BGR HWC
                rh, rw = res.shape[:2]
                ramp = np.ones((rh, rw), dtype=np.float32)
                oy, ox = min(o * s, rh // 2), min(o * s, rw // 2)
                # ramp only edges that overlap a neighboring tile
                if y0 > 0 and oy:
                    ramp[:oy] *= np.linspace(0, 1, oy, dtype=np.float32)[:, None]
                if y1 < h and oy:
                    ramp[-oy:] *= np.linspace(1, 0, oy, dtype=np.float32)[:, None]
                if x0 > 0 and ox:
                    ramp[:, :ox] *= np.linspace(0, 1, ox, dtype=np.float32)[None]
                if x1 < w and ox:
                    ramp[:, -ox:] *= np.linspace(1, 0, ox, dtype=np.float32)[None]
                out[y0 * s:y1 * s, x0 * s:x1 * s] += res * ramp[..., None]
                weight[y0 * s:y1 * s, x0 * s:x1 * s] += ramp[..., None]
        out /= np.maximum(weight, 1e-6)
        return (out.clip(0, 1) * 255).astype(np.uint8)


_onnx_cache = {}


def upscale_frame(bgr, scale: int = 2, model: str = "auto", device: str = "auto",
                  tile: int = 512):
    """One frame. Returns (frame, EngineInfo)."""
    import cv2

    name = resolve_model(model)
    if name == "lanczos":
        return _lanczos(bgr, scale), EngineInfo("lanczos", scale, synthesized=False)
    key = (name, device, tile)
    if key not in _onnx_cache:
        _onnx_cache[key] = _OnnxSR(name, tile=tile, device=device)
    sr = _onnx_cache[key]
    out = sr.run(bgr)
    if sr.scale != scale:  # model is x4 but caller wants x2 etc.
        h, w = bgr.shape[:2]
        out = cv2.resize(out, (w * scale, h * scale), interpolation=cv2.INTER_AREA)
    return out, EngineInfo(name, scale, synthesized=True)


def upscale(frames: Iterable, scale: int = 2, model: str = "auto",
            device: str = "auto", tile: int = 512,
            on_progress=None) -> Iterator:
    for i, f in enumerate(frames):
        out, info = upscale_frame(f, scale, model, device, tile)
        yield out
        if on_progress:
            on_progress(i, info)
