"""Shot boundary detection.

Every temporal tool in the suite (Pivot's solver, Stencil's propagation, Depth's
normalization) works per shot and must never smooth across a cut. The detector is
split in two so the decision logic is testable without video dependencies:

  frame_diffs(path)            -> [d_1 .. d_{n-1}]   (needs PyAV; d_i in 0..1)
  cuts_from_diffs(diffs, ...)  -> cut frame indices   (pure python)
  shots_from_cuts(cuts, n)     -> [(start, end_exclusive), ...]
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

Shot = Tuple[int, int]  # (start_frame, end_frame_exclusive)


def cuts_from_diffs(
    diffs: Sequence[float],
    threshold: float = 0.30,
    min_shot_len: int = 12,
    adaptive: bool = True,
    adaptive_mult: float = 6.0,
    adaptive_window: int = 24,
) -> List[int]:
    """Return frame indices where a new shot begins.

    ``diffs[i]`` is the dissimilarity between frame ``i`` and frame ``i+1``
    (mean |luma delta|, normalized 0..1); a cut detected there starts at frame
    ``i+1``. With ``adaptive`` on, a diff must also exceed ``adaptive_mult`` x
    the local median diff, so noisy/handheld footage doesn't fire on motion —
    a real cut is a spike *relative to its neighborhood*, not just a big number.
    ``min_shot_len`` suppresses double-triggers on flash frames.
    """
    cuts: List[int] = []
    last_cut = 0
    n = len(diffs)
    for i, d in enumerate(diffs):
        frame = i + 1
        if d < threshold:
            continue
        if adaptive:
            lo = max(0, i - adaptive_window)
            hi = min(n, i + adaptive_window + 1)
            neighborhood = sorted(list(diffs[lo:i]) + list(diffs[i + 1 : hi]))
            if neighborhood:
                local_median = neighborhood[len(neighborhood) // 2]
                if d < adaptive_mult * local_median and local_median > 1e-6:
                    continue
        if frame - last_cut < min_shot_len:
            continue
        cuts.append(frame)
        last_cut = frame
    return cuts


def shots_from_cuts(cuts: Sequence[int], n_frames: int) -> List[Shot]:
    """Turn cut frame indices into [start, end) shot spans covering all frames."""
    if n_frames <= 0:
        return []
    bounds = [0] + [c for c in cuts if 0 < c < n_frames] + [n_frames]
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]


def frame_diffs(path: str, analysis_height: int = 90) -> List[float]:
    """Decode ``path`` and return normalized mean-|luma-delta| between frames.

    Decodes a tiny grayscale analysis stream (default 90 px tall) — plenty for
    cut detection and ~50x faster than full-res. Requires PyAV.
    """
    try:
        import av
        import numpy as np
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "shot detection on real video needs PyAV + numpy — pip install av numpy"
        ) from e

    diffs: List[float] = []
    prev = None
    with av.open(path) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        for frame in container.decode(stream):
            h = analysis_height
            w = max(2, int(frame.width * h / max(1, frame.height)))
            gray = frame.reformat(width=w, height=h, format="gray")
            plane = np.frombuffer(bytes(gray.planes[0]), dtype=np.uint8)
            plane = plane.astype(np.int16)
            if prev is not None and prev.shape == plane.shape:
                diffs.append(float(np.abs(plane - prev).mean()) / 255.0)
            prev = plane
    return diffs
