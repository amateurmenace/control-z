"""Moment detection, behind our own door.

PARALLEL's detection seam: lane A extracted Highlighter's moment scoring into
`czcore/moments.py` (landed on main), so Memory reads it there directly — the
callers below never changed across the swap. Everything here is local and
extractive; it reads the transcript and names its reasons.
"""

from __future__ import annotations

from typing import List, Optional

from czcore.moments import build_reel, score_segments


def scored(segments: List[dict],
           keywords: Optional[List[str]] = None) -> List[dict]:
    """Every segment, scored 0..1 with named reasons. The scrubber lane."""
    return score_segments(segments, extra_keywords=keywords or None)


def moments(segments: List[dict], keywords: Optional[List[str]] = None,
            target: float = 120.0) -> List[dict]:
    """The meeting's few most load-bearing moments, in story order, each with
    a timestamp and the reasons it was picked (decision, numbers, a keyword…)."""
    picks = build_reel(scored(segments, keywords), target=target)
    return [{"start": p.get("start", 0.0), "end": p.get("end", 0.0),
             "text": p.get("text", ""), "score": p.get("score", 0.0),
             "reasons": p.get("reasons", [])} for p in picks]
