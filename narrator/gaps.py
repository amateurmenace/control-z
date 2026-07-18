"""The dialogue-gap map — where narration can live without stepping on
anyone. Pure math over transcript segments; no video, no models.

DCMP practice: description speaks in the pauses, never over speech, and
a description that doesn't fit its gap belongs in the transcript (and
the extended web mode) rather than crammed. The fit budget here is
deliberately conservative — ~2.6 words/second is a clear human read;
the lint layer flags anything over.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

WPS = 2.6            # words per second a narrator can speak clearly
EDGE_PAD = 0.25      # seconds shaved off each gap edge — never clip a word


def speech_spans(segments: List[dict],
                 merge_within: float = 0.4) -> List[Tuple[float, float]]:
    """Transcript segments -> merged [start, end) speech intervals.
    Segments closer than merge_within fuse — a breath is not a gap."""
    spans = sorted((float(s.get("start", 0)), float(s.get("end", 0)))
                   for s in segments
                   if str(s.get("text", "")).strip()
                   and float(s.get("end", 0)) > float(s.get("start", 0)))
    out: List[Tuple[float, float]] = []
    for a, b in spans:
        if out and a - out[-1][1] <= merge_within:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def gap_map(segments: List[dict], duration: float,
            min_gap: float = 2.0, lead_in: bool = True) -> List[dict]:
    """The gaps narration can use: [{start, end, dur, words_budget}].

    The complement of speech within [0, duration], edges padded so the
    voice never brushes a word, gaps shorter than min_gap dropped. The
    opening silence before the first line counts (lead_in) — it is where
    'A wide shot of the council chamber' belongs.
    """
    duration = max(0.0, float(duration))
    spans = speech_spans(segments)
    gaps: List[dict] = []

    def add(a: float, b: float):
        a, b = a + EDGE_PAD, b - EDGE_PAD
        if b - a >= min_gap:
            gaps.append({"start": round(a, 3), "end": round(b, 3),
                         "dur": round(b - a, 3),
                         "words_budget": int((b - a) * WPS)})

    if not spans:
        if duration:
            add(0.0, duration)
        return gaps
    if lead_in and spans[0][0] > 0:
        add(0.0, spans[0][0])
    for (_, e1), (s2, _) in zip(spans, spans[1:]):
        add(e1, s2)
    if duration > spans[-1][1]:
        add(spans[-1][1], duration)
    return gaps


def fits(text: str, gap_dur: float) -> bool:
    return len(str(text).split()) <= max(1, int(gap_dur * WPS))


def graphic_shots(shots_s: List[Tuple[float, float]],
                  motion: List[float],
                  min_dur: float = 12.0,
                  max_motion: float = 0.012) -> List[dict]:
    """The meeting-graphics wedge, found by stillness: shots (in seconds)
    that hold long and barely move are slides, charts, site plans — the
    information a blind viewer never receives. motion[i] is the shot's
    mean internal frame diff (0..1). Returns [{start, end, dur}]."""
    out = []
    for (a, b), m in zip(shots_s, motion):
        if (b - a) >= min_dur and m <= max_motion:
            out.append({"start": round(a, 3), "end": round(b, 3),
                        "dur": round(b - a, 3)})
    return out


def shot_seconds(shots: List[Tuple[int, int]], fps: float
                 ) -> List[Tuple[float, float]]:
    """czcore.shots frame spans -> second spans."""
    fps = float(fps) or 30.0
    return [(round(a / fps, 3), round(b / fps, 3)) for a, b in shots]


def shot_motion(diffs: List[float],
                shots: List[Tuple[int, int]]) -> List[float]:
    """Mean internal diff per shot — diffs[i] sits between frames i and
    i+1, so a shot [a, b) owns diffs[a : b-1]."""
    out = []
    for a, b in shots:
        window = diffs[a:max(a, b - 1)]
        out.append(round(sum(window) / len(window), 5) if window else 0.0)
    return out


def plan_cues(gaps: List[dict], graphics: List[dict],
              max_cues: Optional[int] = None) -> List[dict]:
    """Marry the two maps into the draft cue list the reviewer sees.

    Every usable gap becomes a cue slot. A graphic stretch becomes a cue
    even when no gap serves it — its description always reaches the
    transcript (and the extended mode); the gap-fitted subset reaches the
    broadcast mix. kind: "scene" | "graphic"; at: where the describing
    frame is pulled.
    """
    cues: List[dict] = []
    for g in gaps:
        cues.append({"start": g["start"], "end": g["end"], "dur": g["dur"],
                     "kind": "scene", "at": round(g["start"] + min(1.0, g["dur"] / 2), 3),
                     "words_budget": g["words_budget"],
                     "text": "", "status": "empty"})
    for gr in graphics:
        host = next((c for c in cues
                     if c["start"] < gr["end"] and gr["start"] < c["end"]), None)
        if host is not None:
            host["kind"] = "graphic"
            host["at"] = round(max(gr["start"] + 0.5,
                                   min(host["at"], gr["end"] - 0.5)), 3)
        else:
            cues.append({"start": gr["start"], "end": gr["end"],
                         "dur": gr["dur"], "kind": "graphic",
                         "at": round(gr["start"] + min(1.0, gr["dur"] / 2), 3),
                         "words_budget": 0,   # no gap: transcript/extended only
                         "text": "", "status": "empty"})
    cues.sort(key=lambda c: c["start"])
    if max_cues is not None:
        cues = cues[:max_cues]
    return cues
