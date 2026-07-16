"""YOLOX-s person detection (ONNX Runtime) — the wide-shot fallback.

Faces are Pivot's primary signal; this catches podium speakers, walking
subjects, and backs-of-heads that YuNet can't see. Raw YOLOX output needs
grid/stride decoding (the export has no post-processing baked in).
"""

from __future__ import annotations

from typing import List, Tuple

from czcore import models

Box = Tuple[float, float, float, float]

_INPUT = 640
_STRIDES = (8, 16, 32)
_PERSON_CLASS = 0  # COCO


class PersonDetector:
    def __init__(self, score_threshold: float = 0.35, nms_threshold: float = 0.45):
        import numpy as np
        import onnxruntime as ort

        self.np = np
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        path = str(models.model_path("yolox_s"))
        self.sess = ort.InferenceSession(
            path, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.sess.get_inputs()[0].name
        # precompute the anchor grid for the fixed 640 input
        grids, strides = [], []
        for s in _STRIDES:
            n = _INPUT // s
            yv, xv = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
            grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
            strides.append(np.full((n * n, 1), s))
        self.grid = np.concatenate(grids, 0).astype(np.float32)
        self.stride = np.concatenate(strides, 0).astype(np.float32)

    def detect(self, bgr) -> List[Tuple[Box, float]]:
        """bgr: HxWx3 uint8 analysis frame. Returns normalized ((x,y,w,h), score)."""
        np = self.np
        import cv2

        h, w = bgr.shape[:2]
        scale = min(_INPUT / w, _INPUT / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        canvas = np.full((_INPUT, _INPUT, 3), 114, dtype=np.uint8)
        canvas[:nh, :nw] = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        blob = canvas.astype(np.float32).transpose(2, 0, 1)[None]

        out = self.sess.run(None, {self.input_name: blob})[0][0]  # (anchors, 85)
        xy = (out[:, :2] + self.grid) * self.stride
        wh = np.exp(out[:, 2:4]) * self.stride
        obj = out[:, 4]
        cls = out[:, 5 + _PERSON_CLASS]
        scores = obj * cls
        keep = scores >= self.score_threshold
        if not keep.any():
            return []
        xy, wh, scores = xy[keep], wh[keep], scores[keep]
        x1y1 = xy - wh / 2
        rects = [(float(a[0]), float(a[1]), float(b[0]), float(b[1]))
                 for a, b in zip(x1y1, wh)]
        idxs = cv2.dnn.NMSBoxes(rects, scores.astype(float).tolist(),
                                self.score_threshold, self.nms_threshold)
        dets: List[Tuple[Box, float]] = []
        for i in np.array(idxs).flatten():
            x, y, bw, bh = rects[int(i)]
            dets.append((
                (x / scale / w, y / scale / h, bw / scale / w, bh / scale / h),
                float(scores[int(i)]),
            ))
        return dets
