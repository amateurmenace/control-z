"""Extractive cleanup proposals from a transcript — never touching the media.

Two reads over the words Scribe already wrote:

  - **filler strip**: every "um / uh / er…" (plus a caller's own list) as a
    removal, with its exact word timing;
  - **silence tightening**: every gap between speech longer than a threshold,
    as a removal (padded so speech keeps its breath).

Both return removals that stay a *pull-list* — the editor sees every one before
anything is cut. ``keep_ranges`` inverts them into the selects a CMX3600 EDL
conforms, so the tightened cut is a proposal you import and relink, never a
destructive edit to the source. Pure and stdlib-only; the route probes fps and
writes the EDL through ``scribe.exports``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .exports import Select
from .transcript import Transcript

# common English disfluencies — a word matches when its letters-only lowercase
# equals one of these (so "Um," and "uh." match). Kept deliberately tight: only
# sounds that are almost never meant, never real words like "like" or "so"
# whose removal would change meaning. The caller may add its own via `extra`.
FILLERS = {"um", "uh", "erm", "er", "ah", "eh", "hmm", "mm", "mhm", "uhh",
           "umm", "uhm", "huh", "hm"}


@dataclass(frozen=True)
class Removal:
    start: float
    end: float
    kind: str          # "filler" | "silence"
    text: str = ""     # the filler word said, or "" for a silence


def _letters(w: str) -> str:
    return "".join(ch for ch in w.lower() if ch.isalpha())


def filler_removals(t: Transcript,
                    extra: Optional[List[str]] = None) -> List[Removal]:
    """Every filler word with real timing, in order. A transcript without
    word-level timings simply yields nothing here (there is no honest span to
    cut) — silence tightening still works segment-wide."""
    vocab = set(FILLERS) | {_letters(x) for x in (extra or []) if _letters(x)}
    out = []
    for seg in t.segments:
        for w in seg.words:
            if w.e > w.s and _letters(w.w) in vocab:
                out.append(Removal(round(w.s, 3), round(w.e, 3), "filler",
                                   w.w.strip()))
    return out


def _speech_intervals(t: Transcript) -> List[Tuple[float, float]]:
    """Where speech actually is: word spans when the transcript has them, else
    the whole segment. Sorted, so gaps between them are the silences."""
    ivs = []
    for seg in t.segments:
        if seg.words:
            ivs.extend((w.s, w.e) for w in seg.words if w.e > w.s)
        elif seg.end > seg.start:
            ivs.append((seg.start, seg.end))
    ivs.sort()
    return ivs


def silence_removals(t: Transcript, min_gap: float = 0.7,
                     pad: float = 0.08) -> List[Removal]:
    """Gaps between speech longer than ``min_gap`` seconds, trimmed by ``pad``
    on each side so the cut never clips a breath or a word's tail."""
    out = []
    ivs = _speech_intervals(t)
    for (_s1, e1), (s2, _e2) in zip(ivs, ivs[1:]):
        if s2 - e1 >= min_gap:
            s, e = e1 + pad, s2 - pad
            if e - s > 0.05:
                out.append(Removal(round(s, 3), round(e, 3), "silence"))
    return out


def keep_ranges(duration: float, removals: List[Removal],
                min_keep: float = 0.04) -> List[Select]:
    """Invert the removals over [0, duration] into the keep-selects a cut list
    conforms. Overlapping removals merge; a keep shorter than ``min_keep`` is
    dropped (a frame of nothing between two cuts helps no one)."""
    cuts = sorted((max(0.0, r.start), min(duration, r.end)) for r in removals
                  if r.end > r.start)
    merged: List[List[float]] = []
    for s, e in cuts:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    keeps, pos = [], 0.0
    for s, e in merged:
        if s - pos > min_keep:
            keeps.append(Select(round(pos, 3), round(s, 3)))
        pos = max(pos, e)
    if duration - pos > min_keep:
        keeps.append(Select(round(pos, 3), round(duration, 3)))
    return keeps


def summarize(duration: float, removals: List[Removal]) -> dict:
    """What the pull-list adds up to — said out loud before anything commits."""
    removed = sum(r.end - r.start for r in removals if r.end > r.start)
    removed = min(removed, duration)
    return {"removed_seconds": round(removed, 2),
            "kept_seconds": round(max(0.0, duration - removed), 2),
            "n_fillers": sum(1 for r in removals if r.kind == "filler"),
            "n_silences": sum(1 for r in removals if r.kind == "silence")}
