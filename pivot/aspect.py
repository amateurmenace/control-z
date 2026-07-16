"""Crop geometry: aspect math shared by the solver, renderer, and exports.

Coordinates are normalized: crop center ``cx`` in 0..1 across the source width
(``cy`` across height for vertical solves). The solver works in normalized
space; only ``rect_for_center`` touches pixels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


def parse_aspect(spec: str) -> float:
    """'9:16' / '9x16' / '0.5625' -> width/height ratio."""
    s = spec.strip().lower().replace("x", ":")
    if ":" in s:
        w, h = s.split(":", 1)
        num, den = float(w), float(h)
        if num <= 0 or den <= 0:
            raise ValueError(f"bad aspect {spec!r}")
        return num / den
    v = float(s)
    if v <= 0:
        raise ValueError(f"bad aspect {spec!r}")
    return v


@dataclass(frozen=True)
class CropGeometry:
    src_w: int
    src_h: int
    crop_w: int          # even pixels
    crop_h: int          # even pixels
    axis: str            # "x" = camera moves horizontally, "y" = vertically, "none" = same aspect

    @property
    def half_width_norm(self) -> float:
        """Half the crop extent along the moving axis, normalized to that axis."""
        if self.axis == "y":
            return (self.crop_h / 2) / self.src_h
        return (self.crop_w / 2) / self.src_w

    def punch_in_factor(self, out_w: int) -> float:
        """>1.0 means the crop is being scaled up past native detail (Rise territory)."""
        return out_w / self.crop_w


def _even(v: float) -> int:
    n = int(round(v))
    if n % 2:
        n -= 1
    return max(2, n)


def crop_geometry(src_w: int, src_h: int, target_aspect: float) -> CropGeometry:
    """Largest crop of the source that matches ``target_aspect`` (w/h)."""
    if src_w <= 0 or src_h <= 0:
        raise ValueError("source dimensions must be positive")
    src_aspect = src_w / src_h
    if abs(src_aspect - target_aspect) < 1e-9:
        return CropGeometry(src_w, src_h, _even(src_w), _even(src_h), "none")
    if target_aspect < src_aspect:
        # narrower than source: full height, camera pans in x (16:9 -> 9:16 case)
        crop_h = _even(src_h)
        crop_w = _even(crop_h * target_aspect)
        return CropGeometry(src_w, src_h, crop_w, crop_h, "x")
    # wider than source: full width, camera tilts in y
    crop_w = _even(src_w)
    crop_h = _even(crop_w / target_aspect)
    return CropGeometry(src_w, src_h, crop_w, crop_h, "y")


def rect_for_center(geom: CropGeometry, center_norm: float) -> Tuple[int, int, int, int]:
    """(x, y, w, h) pixel rect for a solved center along the moving axis, clamped in-frame."""
    if geom.axis == "y":
        y = int(round(center_norm * geom.src_h - geom.crop_h / 2))
        y = min(max(y, 0), geom.src_h - geom.crop_h)
        return (0, y, geom.crop_w, geom.crop_h)
    x = int(round(center_norm * geom.src_w - geom.crop_w / 2))
    x = min(max(x, 0), geom.src_w - geom.crop_w)
    return (x, 0, geom.crop_w, geom.crop_h)
