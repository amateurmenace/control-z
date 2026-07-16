"""Matte post-processing chain: grow/shrink -> feather -> temporal smooth.

Pure numpy/cv2 on uint8 masks (0/255). The temporal 3-frame morphological
majority kills single-frame flicker without lag — golden-tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Optional


@dataclass(frozen=True)
class PostParams:
    grow: int = 0          # +grow / -shrink, pixels
    feather: float = 0.0   # gaussian sigma, pixels
    despeckle: int = 0     # drop components smaller than this many px
    temporal: bool = True  # 3-frame majority


def grow_shrink(mask, px: int):
    import cv2
    import numpy as np

    if px == 0:
        return mask
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (abs(px) * 2 + 1,) * 2)
    op = cv2.dilate if px > 0 else cv2.erode
    return op(mask, k)


def feather(mask, sigma: float):
    import cv2

    if sigma <= 0:
        return mask
    k = int(sigma * 4) | 1
    return cv2.GaussianBlur(mask, (k, k), sigma)


def despeckle(mask, min_area: int):
    import cv2
    import numpy as np

    if min_area <= 0:
        return mask
    binary = (mask > 127).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    out = mask.copy()
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            out[labels == i] = 0
    return out


def temporal_majority(prev, cur, nxt):
    """Per-pixel 2-of-3 vote on binarized masks; returns cur cleaned (uint8)."""
    import numpy as np

    votes = (prev > 127).astype(np.uint8) + (cur > 127).astype(np.uint8) \
        + (nxt > 127).astype(np.uint8)
    return np.where(votes >= 2, np.uint8(255), np.uint8(0))


def apply_chain(masks: List, params: PostParams) -> Iterator:
    """masks: list of HxW uint8. Yields processed masks in order."""
    n = len(masks)
    for i in range(n):
        m = masks[i]
        if params.temporal and n >= 3:
            prev = masks[max(0, i - 1)]
            nxt = masks[min(n - 1, i + 1)]
            m = temporal_majority(prev, m, nxt)
        m = despeckle(m, params.despeckle)
        m = grow_shrink(m, params.grow)
        m = feather(m, params.feather)
        yield m
