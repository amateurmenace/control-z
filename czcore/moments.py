"""Finding the moments — scored from the words, shown with receipts.

Detection-as-a-service (specs/12 §2): this engine grew up inside
Highlighter and now lives in czcore so the whole wing can call it —
Highlighter's detect route and analyzer vocab, Publisher's clip
candidates, Memory's issue inputs. One scorer, one set of receipts.
`highlighter/highlights.py` re-exports these names for its old callers.

No cloud model reads your meeting. The scorer is a transparent keyword +
emphasis pass tuned for civic footage (motions, money, public comment,
applause), optionally blended with audio energy. Every highlight carries
the list of reasons it was picked — that's the covenant surface here: you
can see exactly why, and overrule it in the text.

Stdlib-only at import time (numpy/av load lazily inside audio_energy) —
czcore stays importable everywhere, per the house dep-guard convention.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

# -- signal vocabulary (civic meetings first, but general footage benefits) --

KEYWORD_CLASSES = {
    "decision": (2.5, (
        "motion", "second the", "seconded", "vote", "voted", "voting",
        "approve", "approved", "approval", "denied", "deny", "passes",
        "passed", "carried", "carries", "unanimous", "adopted", "adopt",
        "resolution", "ordinance", "amendment", "amended", "so moved",
    )),
    "money": (1.5, (
        "budget", "dollar", "million", "thousand", "funding", "funded",
        "grant", "cost", "costs", "tax", "taxes", "fee", "appropriation",
        "$",
    )),
    "community": (1.2, (
        "resident", "residents", "neighbor", "public comment", "petition",
        "school", "park", "housing", "traffic", "safety", "library",
        "community", "families", "students", "seniors",
    )),
    "tension": (1.5, (
        "concern", "concerned", "opposed", "oppose", "objection", "disagree",
        "problem", "urgent", "emergency", "complaint", "frustrated",
        "unacceptable", "crisis",
    )),
    "reaction": (2.0, (
        "[applause]", "[laughter]", "[cheering]", "(applause)", "(laughter)",
    )),
}

_EMPHASIS = (
    (re.compile(r"!"), 0.6, "exclamation"),
    (re.compile(r"\?"), 0.3, "question"),
    (re.compile(r"\d"), 0.4, "numbers"),
    (re.compile(r"\b(first|biggest|largest|never|historic|record|finally)\b",
                re.I), 0.5, "superlative"),
)


def score_segments(segments: List[dict],
                   extra_keywords: Optional[List[str]] = None) -> List[dict]:
    """Score each {start,end,text} segment; returns [{...seg, score, reasons}].

    Scores are normalized to 0..1 across the meeting so the UI can draw them
    as a lane. reasons is a human list like ["decision: 'motion'", "numbers"].
    """
    extra = [k.lower() for k in (extra_keywords or []) if k.strip()]
    out = []
    for seg in segments:
        text = str(seg.get("text", ""))
        low = " " + text.lower() + " "
        score, reasons = 0.0, []
        for cls, (w, words) in KEYWORD_CLASSES.items():
            hits = [kw for kw in words if kw in low]
            if hits:
                score += w * min(len(hits), 3)
                reasons.append(f"{cls}: " + ", ".join(f"“{h}”" for h in hits[:3]))
        for rx, w, name in _EMPHASIS:
            if rx.search(text):
                score += w
                reasons.append(name)
        for kw in extra:
            if kw in low:
                score += 2.0
                reasons.append(f"your keyword: “{kw}”")
        # a long segment collects hits by surface area — take that back out
        n_words = max(len(text.split()), 1)
        score = score / (1.0 + n_words / 40.0)
        out.append({**seg, "score": score, "reasons": reasons})
    top = max((s["score"] for s in out), default=0.0)
    if top > 0:
        for s in out:
            s["score"] = round(s["score"] / top, 4)
    return out


def blend_energy(scored: List[dict], energy: List[tuple],
                 weight: float = 0.35) -> List[dict]:
    """Mix in audio energy (t, rms) — loud rooms mark their own moments."""
    if not energy:
        return scored
    values = sorted(r for _, r in energy)

    def rank(x: float) -> float:
        lo, hi = 0, len(values)
        while lo < hi:
            mid = (lo + hi) // 2
            if values[mid] <= x:
                lo = mid + 1
            else:
                hi = mid
        return lo / max(len(values), 1)

    for s in scored:
        peak = max((r for t, r in energy
                    if s["start"] - 0.5 <= t <= s["end"] + 0.5), default=None)
        if peak is None:
            continue
        r = rank(peak)
        if r > 0.85:
            s["score"] = min(1.0, s["score"] + weight * (r - 0.85) / 0.15)
            s["reasons"].append(f"room energy (top {max(1, round((1 - r) * 100))}%)")
    return scored


def audio_energy(path: str, hop: float = 0.5,
                 progress: Optional[Callable[[str], None]] = None) -> List[tuple]:
    """RMS per hop window, decoded locally. Returns [] when there's no audio."""
    import numpy as np

    try:
        import av
        acc, out, t = [], [], 0.0
        with av.open(path) as c:
            if not c.streams.audio:
                return []
            stream = c.streams.audio[0]
            rate = stream.rate or 48000
            win = int(rate * hop)
            for frame in c.decode(stream):
                a = frame.to_ndarray()
                mono = a.mean(axis=0) if a.ndim > 1 else a
                if mono.dtype.kind == "i":
                    mono = mono.astype("f4") / np.iinfo(mono.dtype).max
                acc.append(mono.astype("f4"))
                total = sum(len(x) for x in acc)
                while total >= win:
                    buf = np.concatenate(acc)[:win]
                    rest = np.concatenate(acc)[win:]
                    acc = [rest] if len(rest) else []
                    total = len(rest)
                    out.append((round(t, 3), float(np.sqrt((buf ** 2).mean()))))
                    t += hop
                    if progress and len(out) % 240 == 0:
                        progress(f"listening… {int(t) // 60}m in")
        return out
    except Exception:
        return []  # energy is a bonus signal, never a blocker


def build_reel(scored: List[dict], target: float = 90.0, min_clip: float = 4.0,
               max_clip: float = 40.0, pad: float = 0.4,
               floor: float = 0.12) -> List[dict]:
    """Pick top moments until ~target seconds, merged and back in story order.

    Returns [{start, end, text, score, reasons}] — the reel's cut list.
    """
    ranked = sorted((s for s in scored if s["score"] > floor),
                    key=lambda s: -s["score"])
    picks: List[dict] = []
    total = 0.0
    for s in ranked:
        if total >= target:
            break
        start = max(0.0, float(s["start"]) - pad)
        end = float(s["end"]) + pad
        if end - start < min_clip:
            grow = (min_clip - (end - start)) / 2
            start, end = max(0.0, start - grow), end + grow
        end = min(end, start + max_clip)
        merged = False
        for p in picks:
            if start <= p["end"] + 1.0 and end >= p["start"] - 1.0:
                grew = max(end, p["end"]) - min(start, p["start"]) \
                    - (p["end"] - p["start"])
                p["start"] = min(p["start"], start)
                p["end"] = max(end, p["end"])
                p["reasons"] = list(dict.fromkeys(p["reasons"] + s["reasons"]))
                total += max(grew, 0.0)
                merged = True
                break
        if not merged:
            picks.append({"start": round(start, 3), "end": round(end, 3),
                          "text": s.get("text", ""), "score": s["score"],
                          "reasons": list(s["reasons"])})
            total += end - start
    # a merge can grow a pick into a neighbor it never got compared against —
    # one chronological sweep settles every overlap
    picks.sort(key=lambda p: p["start"])
    swept: List[dict] = []
    for p in picks:
        if swept and p["start"] <= swept[-1]["end"] + 1.0:
            last = swept[-1]
            last["end"] = max(last["end"], p["end"])
            last["score"] = max(last["score"], p["score"])
            last["reasons"] = list(dict.fromkeys(last["reasons"] + p["reasons"]))
        else:
            swept.append(p)
    for p in swept:
        p["start"], p["end"] = round(p["start"], 3), round(p["end"], 3)
    return swept


# -- YouTube caption VTT -> transcript segments ------------------------------

_TS = r"(\d+):(\d{2}):(\d{2})[.,](\d{3})"
_CUE = re.compile(_TS + r"\s+-->\s+" + _TS)
_WORDTAG = re.compile(r"<(\d+):(\d{2}):(\d{2})[.,](\d{3})>")
_TAG = re.compile(r"<[^>]+>")


def _secs(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(text: str) -> List[dict]:
    """Caption file -> transcript-shaped segments (words carry timing when
    YouTube's word tags are present — karaoke without running a model).

    YouTube auto-caption VTTs repeat each line as a rolling two-liner; cues
    that only re-show the previous text are dropped.
    """
    segments: List[dict] = []
    lines = text.replace("\r\n", "\n").split("\n")
    i, last_text = 0, ""
    while i < len(lines):
        m = _CUE.search(lines[i])
        if not m:
            i += 1
            continue
        start, end = _secs(*m.groups()[:4]), _secs(*m.groups()[4:])
        i += 1
        raw = []
        while i < len(lines) and lines[i].strip() and not _CUE.search(lines[i]):
            raw.append(lines[i])
            i += 1
        body = "\n".join(raw)
        # tokens between YouTube's <t> marks start at the mark before them
        words: List[dict] = []
        if _WORDTAG.search(body):
            words = _words_from_tagged(body, start, end)
        clean = _TAG.sub("", body).replace("\n", " ")
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean or clean == last_text or (last_text and clean.startswith(last_text)
                                               and len(last_text) > 20):
            # rolling repeat — keep only what's new
            if clean.startswith(last_text) and len(clean) > len(last_text):
                clean = clean[len(last_text):].strip()
                words = [w for w in words if w["s"] >= start - 0.01] if words else []
            else:
                continue
        if not clean:
            continue
        last_text = _TAG.sub("", body).replace("\n", " ").strip()
        segments.append({"start": round(start, 3), "end": round(end, 3),
                         "text": clean, "speaker": None,
                         "words": words or None})
    # drop empty / zero-length leftovers, ensure order
    segments = [s for s in segments if s["text"] and s["end"] > s["start"]]
    segments.sort(key=lambda s: s["start"])
    return segments


def _words_from_tagged(body: str, start: float, end: float) -> List[dict]:
    flat = body.replace("\n", " ")
    parts = re.split(r"(<\d+:\d{2}:\d{2}[.,]\d{3}>)", flat)
    words: List[dict] = []
    t = start
    for part in parts:
        m = _WORDTAG.fullmatch(part)
        if m:
            t = _secs(*m.groups())
            continue
        for tok in _TAG.sub("", part).split():
            words.append({"w": tok, "s": round(t, 3), "e": None, "p": 0.9})
    for k, w in enumerate(words):
        w["e"] = words[k + 1]["s"] if k + 1 < len(words) else round(end, 3)
        if w["e"] <= w["s"]:
            w["e"] = round(w["s"] + 0.05, 3)
    return words


def transcript_dict(segments: List[dict], source: str, language: str = "en",
                    origin: str = "captions") -> Dict:
    """Wrap segments in the scribe sidecar shape so every tool can read it."""
    speakers = sorted({s["speaker"] for s in segments if s.get("speaker")})
    return {"version": 1, "source": source, "language": language,
            "model": origin, "speakers": speakers,
            "segments": [{"start": s["start"], "end": s["end"],
                          "text": s["text"], "speaker": s.get("speaker"),
                          "words": s.get("words") or []} for s in segments]}
