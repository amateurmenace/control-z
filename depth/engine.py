"""Per-frame relative depth with temporal EMA and edge-guided upsampling.

Backend v0.1: MiDaS-small (MIT) at 256px. The interface is model-agnostic —
Video-Depth-Anything-Small (Apache) slots in behind estimate() for v0.2.
Depth is RELATIVE (bigger = nearer after normalization); we normalize per shot
so grades stay stable within a cut and say so in the sidecar.
"""

from __future__ import annotations

from typing import Optional

_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD = (0.229, 0.224, 0.225)


def guided_filter(guide, src, radius: int = 8, eps: float = 1e-3):
    """He et al. guided filter (gray guide) — edge-aware depth upsampling."""
    import cv2
    import numpy as np

    I = guide.astype(np.float32) / 255.0
    p = src.astype(np.float32)
    k = (2 * radius + 1, 2 * radius + 1)
    mean_I = cv2.blur(I, k)
    mean_p = cv2.blur(p, k)
    corr_Ip = cv2.blur(I * p, k)
    corr_II = cv2.blur(I * I, k)
    var_I = corr_II - mean_I * mean_I
    cov_Ip = corr_Ip - mean_I * mean_p
    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I
    mean_a = cv2.blur(a, k)
    mean_b = cv2.blur(b, k)
    return mean_a * I + mean_b


class DepthEngine:
    def __init__(self, device: str = "auto"):
        import onnxruntime as ort

        from czcore.models import model_path

        providers = ["CPUExecutionProvider"]
        if device in ("auto", "coreml") and \
                "CoreMLExecutionProvider" in ort.get_available_providers():
            providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        self.sess = ort.InferenceSession(str(model_path("midas_small")),
                                         providers=providers)
        self.input_name = self.sess.get_inputs()[0].name
        self._ema: Optional["object"] = None

    def reset_temporal(self):
        """Call at every shot boundary — depth must never smooth across a cut."""
        self._ema = None

    def estimate(self, bgr, ema: float = 0.7, refine: bool = True):
        """HxWx3 uint8 -> float32 HxW relative depth (unnormalized)."""
        import cv2
        import numpy as np

        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(bgr, (256, 256), cv2.INTER_AREA),
                           cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        rgb = (rgb - _IMAGENET_MEAN) / _IMAGENET_STD
        blob = rgb.transpose(2, 0, 1)[None].astype(np.float32)
        d = self.sess.run(None, {self.input_name: blob})[0][0]
        if self._ema is not None and ema > 0:
            d = ema * self._ema + (1 - ema) * d
        self._ema = d
        up = cv2.resize(d, (w, h), interpolation=cv2.INTER_LINEAR)
        if refine:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            up = guided_filter(gray, up, radius=max(4, w // 240))
        return up


def normalize_shot(depths, lo_pct: float = 2.0, hi_pct: float = 98.0,
                   invert: bool = False, gamma: float = 1.0):
    """Normalize a shot's depth list to 0..1 with robust percentiles."""
    import numpy as np

    all_vals = np.concatenate([d.ravel()[::7] for d in depths])
    lo = np.percentile(all_vals, lo_pct)
    hi = np.percentile(all_vals, hi_pct)
    span = max(hi - lo, 1e-6)
    out = []
    for d in depths:
        n = np.clip((d - lo) / span, 0.0, 1.0)
        if invert:
            n = 1.0 - n
        if gamma != 1.0:
            n = n ** gamma
        out.append(n.astype(np.float32))
    return out, {"lo": float(lo), "hi": float(hi)}
