"""Detection association + subject selection. Pure python — golden-testable.

Boxes are normalized (x, y, w, h) in 0..1 of the analysis frame. The tracker is
deliberately simple (greedy IoU / center-distance): Pivot follows *one subject
per shot*, so identity switches between similar faces matter less than
stability, and every decision here is visible in the path-trace QC view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

Box = Tuple[float, float, float, float]  # x, y, w, h normalized


def iou(a: Box, b: Box) -> float:
    ax2, ay2 = a[0] + a[2], a[1] + a[3]
    bx2, by2 = b[0] + b[2], b[1] + b[3]
    ix = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    iy = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def center(b: Box) -> Tuple[float, float]:
    return (b[0] + b[2] / 2.0, b[1] + b[3] / 2.0)


@dataclass
class Track:
    tid: int
    frames: List[int] = field(default_factory=list)
    boxes: List[Box] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)

    @property
    def last_frame(self) -> int:
        return self.frames[-1]

    @property
    def last_box(self) -> Box:
        return self.boxes[-1]

    def add(self, frame: int, box: Box, score: float) -> None:
        self.frames.append(frame)
        self.boxes.append(box)
        self.scores.append(score)

    def slice(self, start: int, end: int) -> "Track":
        """Detections within [start, end) — for per-shot subject selection."""
        t = Track(self.tid)
        for f, b, s in zip(self.frames, self.boxes, self.scores):
            if start <= f < end:
                t.add(f, b, s)
        return t


class Tracker:
    """Greedy frame-to-frame association."""

    def __init__(self, iou_min: float = 0.15, dist_mult: float = 1.2, max_gap: int = 30):
        self.iou_min = iou_min
        self.dist_mult = dist_mult
        self.max_gap = max_gap
        self.tracks: List[Track] = []
        self._next_id = 1

    def update(self, frame: int, detections: Sequence[Tuple[Box, float]]) -> None:
        active = [t for t in self.tracks if frame - t.last_frame <= self.max_gap]
        used = set()
        for box, score in sorted(detections, key=lambda d: -d[1]):
            best, best_iou = None, 0.0
            for t in active:
                if t.tid in used:
                    continue
                v = iou(box, t.last_box)
                if v > best_iou:
                    best, best_iou = t, v
            if best is not None and best_iou >= self.iou_min:
                best.add(frame, box, score)
                used.add(best.tid)
                continue
            # IoU failed (fast motion / sparse sampling): try center distance
            cx, cy = center(box)
            best, best_d = None, 1e9
            for t in active:
                if t.tid in used:
                    continue
                tx, ty = center(t.last_box)
                d = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
                reach = self.dist_mult * max(t.last_box[2], t.last_box[3])
                if d < reach and d < best_d:
                    best, best_d = t, d
            if best is not None:
                best.add(frame, box, score)
                used.add(best.tid)
            else:
                t = Track(self._next_id)
                self._next_id += 1
                t.add(frame, box, score)
                self.tracks.append(t)


def subject_score(track: Track) -> float:
    """Bigger, more central, more persistent wins. sqrt(area) keeps close-ups honest."""
    s = 0.0
    for b in track.boxes:
        cx, _ = center(b)
        area = max(b[2] * b[3], 0.0)
        s += (area ** 0.5) * (1.0 - 0.8 * abs(cx - 0.5))
    return s


def select_subject(tracks: Sequence[Track], min_detections: int = 3) -> Optional[Track]:
    candidates = [t for t in tracks if len(t.frames) >= min_detections]
    if not candidates:
        return None
    return max(candidates, key=subject_score)


def targets_from_track(
    track: Optional[Track], start: int, end: int, axis: str = "x", eyeline: float = 0.38
) -> List[Optional[float]]:
    """Per-frame target centers for frames [start, end).

    x-axis: face center. y-axis: place the face at ``eyeline`` from the crop top
    (headroom), i.e. target center = face_cy + (0.5 - eyeline) * 0 … solved by
    offsetting the face center downward in crop terms at the solver's caller —
    here we return the raw face center shifted so the *crop center* target puts
    the face at the eyeline: target_cy = face_cy - (eyeline - 0.5) * crop_h_norm.
    That crop-size shift needs geometry, so callers apply it; we return face
    centers. Between detections: linear interpolation. Outside: None.
    """
    n = end - start
    out: List[Optional[float]] = [None] * n
    if track is None or not track.frames:
        return out
    idx = 0 if axis == "x" else 1
    pts = [(f, center(b)[idx]) for f, b in zip(track.frames, track.boxes)
           if start <= f < end]
    if not pts:
        return out
    for (f0, v0), (f1, v1) in zip(pts, pts[1:]):
        span = max(1, f1 - f0)
        for f in range(f0, f1 + 1):
            out[f - start] = v0 + (v1 - v0) * (f - f0) / span
    f0, v0 = pts[0]
    out[f0 - start] = v0
    fl, vl = pts[-1]
    out[fl - start] = vl
    return out
