"""The Pivot path solver: subject targets in, editor-grade camera path out.

Design (specs/01-pivot.md): shots are solved independently. Each shot resolves to
one of two modes:

  punch  — a static crop at the robust median of the targets. Editors punch, they
           don't drift; most shots should land here.
  follow — an offline camera operator: a deadzone with hysteresis (the camera
           *holds* until the subject genuinely leaves), lookahead anticipation
           (moves start slightly early, like a human), and a jerk-limited
           trapezoidal motion profile (accelerate, cruise, brake). Overshoot is
           bounded by ~4 acceleration quanta (~0.5% of frame width at defaults
           — an imperceptible ease past the mark, pinned by the golden tests).

Everything is pure python and deterministic; the golden tests in
tests/test_solver.py pin the math. Positions are normalized 0..1 along the
crop's moving axis (see pivot.aspect).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


@dataclass(frozen=True)
class SolverParams:
    """Per-frame units. The three shipped presets scale these; tests pin defaults."""

    deadzone: float = 0.06        # subject may drift this far before the camera moves
    settle: float = 0.015         # a move ends when within this of the reference
    lookahead: int = 12           # frames of anticipation (median of the window ahead)
    v_max: float = 0.010          # max camera speed, frame-widths per frame
    a_max: float = 0.0012         # max acceleration per frame
    punch_max_frames: int = 48    # shots shorter than this always punch (2 s @ 24)
    punch_range: float = 0.12     # targets spanning less than this (p5..p95) punch
    trim: float = 0.10            # robust-median trim fraction for punch mode


PRESETS = {
    "calm": SolverParams(deadzone=0.09, v_max=0.007, a_max=0.0008, punch_range=0.16),
    "standard": SolverParams(),
    "attentive": SolverParams(deadzone=0.04, lookahead=8, v_max=0.014, a_max=0.0018,
                              punch_max_frames=24, punch_range=0.08),
}


@dataclass
class SolvedPath:
    mode: str                     # "punch" | "follow"
    centers: List[float]          # one normalized center per frame
    moves: int = 0                # distinct camera moves (follow mode)
    params: SolverParams = field(default_factory=SolverParams)

    @property
    def is_static(self) -> bool:
        return self.mode == "punch" or self.moves == 0


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _fill_missing(targets: Sequence[Optional[float]]) -> List[float]:
    """Forward-fill then back-fill None gaps (lost detections)."""
    out: List[float] = []
    last: Optional[float] = None
    for t in targets:
        if t is not None:
            last = t
        out.append(last if last is not None else math.nan)
    nxt: Optional[float] = None
    for i in range(len(out) - 1, -1, -1):
        if not math.isnan(out[i]):
            nxt = out[i]
        elif nxt is not None:
            out[i] = nxt
    return out


def _robust_median(values: Sequence[float], trim: float) -> float:
    vals = sorted(values)
    k = int(len(vals) * trim)
    if len(vals) > 4 and k > 0:
        vals = vals[k:-k]
    n = len(vals)
    mid = n // 2
    return vals[mid] if n % 2 else 0.5 * (vals[mid - 1] + vals[mid])


def _percentile(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        return math.nan
    idx = _clamp(p * (len(sorted_vals) - 1), 0, len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def classify(
    targets: Sequence[Optional[float]],
    fps: float,
    params: SolverParams = SolverParams(),
) -> str:
    """Decide punch vs follow for one shot's targets."""
    valid = [t for t in targets if t is not None]
    if not valid:
        return "punch"
    max_frames = params.punch_max_frames
    if fps > 0:
        max_frames = int(round(params.punch_max_frames * fps / 24.0))
    if len(targets) < max_frames:
        return "punch"
    s = sorted(valid)
    spread = _percentile(s, 0.95) - _percentile(s, 0.05)
    if spread <= params.punch_range:
        return "punch"
    return "follow"


def solve(
    targets: Sequence[Optional[float]],
    half_width: float,
    fps: float = 24.0,
    params: SolverParams = SolverParams(),
    mode: str = "auto",
) -> SolvedPath:
    """Solve one shot. ``targets`` has one entry per frame (None = no detection);
    ``half_width`` is the crop's normalized half-extent along the moving axis."""
    n = len(targets)
    if n == 0:
        return SolvedPath("punch", [], 0, params)
    lo, hi = half_width, 1.0 - half_width
    if lo >= hi:  # crop as wide as the frame: only one possible center
        return SolvedPath("punch", [0.5] * n, 0, params)

    resolved = mode if mode != "auto" else classify(targets, fps, params)
    valid = [t for t in targets if t is not None]
    if not valid:
        return SolvedPath("punch", [_clamp(0.5, lo, hi)] * n, 0, params)

    if resolved == "punch":
        c = _clamp(_robust_median(valid, params.trim), lo, hi)
        return SolvedPath("punch", [c] * n, 0, params)

    filled = _fill_missing(targets)
    L = params.lookahead
    refs: List[float] = []
    for i in range(n):
        window = sorted(filled[i : min(n, i + L + 1)])
        refs.append(_clamp(window[len(window) // 2], lo, hi))

    centers: List[float] = []
    x = refs[0]
    v = 0.0
    chasing = False
    moves = 0
    for r in refs:
        err = r - x
        if not chasing and abs(err) > params.deadzone:
            chasing = True
            moves += 1
        if chasing:
            if abs(err) <= params.settle and abs(v) <= params.a_max:
                # end of a move: freeze here (no snap — keeps |dv| <= a_max)
                v = 0.0
                chasing = False
            else:
                # velocity setpoint from the braking parabola, then jerk-limit it
                v_des = math.copysign(
                    min(params.v_max, math.sqrt(2.0 * params.a_max * abs(err))), err
                )
                v = _clamp(v_des, v - params.a_max, v + params.a_max)
                x = _clamp(x + v, lo, hi)
        centers.append(x)
    return SolvedPath("follow", centers, moves, params)
