"""The kit: candidates + copy, read from the sidecars the suite already writes.

A Publisher source is anything Highlighter can read: a local video with
sidecars beside it, or a URL-session folder. Candidates come from
meeting.highlights.json when detection already ran, else straight from
czcore.moments on the transcript. Copy is extractive first — sentences
assembled from the transcript and labeled so — and generative only through
the user's own key (czcore.llm), labeled with the model that wrote it.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import List, Optional

from czcore.moments import build_reel, score_segments

RATIO_NAMES = ("16x9", "1x1", "9x16")


# -- sources & sidecars (the highlighter convention, restated) ----------------

def sidecars(source: str) -> dict:
    """{scribe, highlights, insight, kit} paths for a file or session dir."""
    p = Path(source)
    if p.is_dir():
        return {"scribe": p / "meeting.scribe.json",
                "highlights": p / "meeting.highlights.json",
                "insight": p / "insight.json",
                "kit": p / "meeting.publisher.json"}
    return {"scribe": p.with_suffix(".scribe.json"),
            "highlights": p.with_suffix(".highlights.json"),
            "insight": p.with_suffix(".insight.json"),
            "kit": p.with_suffix(".publisher.json")}


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".webm", ".m4v")


def video_path(source: str) -> Optional[Path]:
    """The playable file behind a source. A file is itself. A URL-session
    folder rarely holds video — Highlighter lands downloads in its media
    dir, named with the video id — so look there too, skipping the
    [start-end] span cuts: only the full recording can serve every clip."""
    p = Path(source)
    if p.is_file():
        return p
    if not p.is_dir():
        return None
    vids = [f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXTS]
    if vids:
        return max(vids, key=lambda f: f.stat().st_size)
    try:
        from czcore.paths import media_dir
        pool = [f for f in media_dir("highlighter").iterdir()
                if f.suffix.lower() in VIDEO_EXTS and f"[{p.name}]" in f.name
                and not re.search(r"\[\d+-\d+\]$", f.stem)]
        return max(pool, key=lambda f: f.stat().st_size, default=None)
    except OSError:
        return None


def meeting_meta(source: str) -> dict:
    """{title, date, source} — the session's info.json when there is one,
    the filename otherwise. Dates stay strings; honesty over parsing."""
    p = Path(source)
    title, when = "", ""
    info = None
    if p.is_dir():
        for name in ("meeting.info.json", "info.json"):
            info = _read_json(p / name)
            if info:
                break
    if info:
        title = str(info.get("title") or "")
        when = str(info.get("upload_date") or "")
        if re.fullmatch(r"\d{8}", when):
            when = f"{when[:4]}-{when[4:6]}-{when[6:8]}"
    if not title:
        stem = (video_path(source) or p).stem
        title = re.sub(r"\s*\[[\w-]{11}\]\s*", " ", stem)
        title = re.sub(r"[_.]+", " ", title).strip() or stem
    m = re.search(r"(\d{4}-\d{2}-\d{2})", title + " " + when)
    return {"title": title, "date": when or (m.group(1) if m else ""),
            "source": str(source)}


def segments(source: str) -> List[dict]:
    t = _read_json(sidecars(source)["scribe"])
    return list(t.get("segments") or []) if t else []


# -- candidates ---------------------------------------------------------------

def candidates(source: str, n: int = 5,
               extra_keywords: Optional[List[str]] = None) -> List[dict]:
    """3–5 clip candidates, chronological, each carrying its receipts.

    Detection that already ran wins (the picks the user saw in Highlighter);
    otherwise the shared scorer runs fresh on the transcript. Very short
    programs yield fewer candidates rather than padded ones (specs/13 edge)."""
    hl = _read_json(sidecars(source)["highlights"])
    picks = list((hl or {}).get("picks") or [])
    if not picks:
        segs = segments(source)
        if not segs:
            return []
        scored = score_segments(segs, extra_keywords=extra_keywords)
        picks = build_reel(scored, target=max(1, n) * 24.0,
                           min_clip=8.0, max_clip=45.0)
    picks = sorted(picks, key=lambda p: -float(p.get("score", 0)))[:max(1, n)]
    picks.sort(key=lambda p: float(p["start"]))
    return [{"start": float(p["start"]), "end": float(p["end"]),
             "text": str(p.get("text", "")),
             "score": float(p.get("score", 0)),
             "reasons": list(p.get("reasons") or [])} for p in picks]


# -- the kit sidecar ----------------------------------------------------------

def kit_path(source: str) -> Path:
    return sidecars(source)["kit"]


def load_kit(source: str) -> Optional[dict]:
    return _read_json(kit_path(source))


def save_kit(source: str, kit: dict) -> Path:
    p = kit_path(source)
    p.write_text(json.dumps(kit, indent=1))
    return p


def new_kit(source: str, n: int = 5) -> dict:
    """A fresh kit: candidates picked, extractive copy drafted, nothing
    rendered yet. The review page edits this dict; renders fill `files`."""
    meta = meeting_meta(source)
    cands = candidates(source, n=n)
    ins = _read_json(sidecars(source)["insight"]) or {}
    kit = {
        "version": 1,
        "meta": meta,
        "candidates": cands,
        "clips": [{**c, "keep": i < 3, "ratios": ["16x9", "9x16"],
                   "offset": 0.0, "label": _clip_label(c)}
                  for i, c in enumerate(cands)],
        "copy": copy_extractive(meta, cands, ins),
        "files": [],
    }
    return kit


# -- copy: extractive always --------------------------------------------------

def _clip_label(c: dict) -> str:
    """A human handle for a clip — its first strong words, tidied."""
    text = re.sub(r"\s+", " ", str(c.get("text", ""))).strip()
    text = re.sub(r"^\W+", "", text)
    return (text[:64].rsplit(" ", 1)[0] + "…") if len(text) > 64 else text


def _sentences(text: str, limit: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    out = ""
    for s in parts:
        if len(out) + len(s) + 1 > limit:
            break
        out = (out + " " + s).strip()
    return out or text[:limit].strip()


def fmt_t(t: float) -> str:
    """0:42 · 14:59 · 3:27:31 — hours only when the meeting earns them."""
    t = int(t)
    return (f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600
            else f"{t // 60}:{t % 60:02d}")


def _top_entities(insight: dict, k: int = 4) -> List[str]:
    ents = (insight.get("entities") or {})
    ranked: List[tuple] = []
    for kind in ("people", "places", "organizations", "things"):
        for e in ents.get(kind) or []:
            name = str(e.get("name", "")) if isinstance(e, dict) else str(e)
            count = int(e.get("count", 1)) if isinstance(e, dict) else 1
            if name:
                ranked.append((count, name))
    return [n for _, n in sorted(ranked, reverse=True)[:k]]


def _brief_text(insight: dict) -> str:
    """The extractive brief as prose — insight ships it as [{t, text}]
    sentences; older shapes were dict or plain string. Join, don't invent."""
    b = insight.get("brief")
    if isinstance(b, list):
        return " ".join(str(s.get("text", "")).strip().rstrip(".") + "."
                        for s in b if isinstance(s, dict) and s.get("text"))
    if isinstance(b, dict):
        return str(b.get("text") or b.get("summary") or "")
    return str(b or "")


def copy_extractive(meta: dict, cands: List[dict], insight: dict) -> dict:
    """Copy assembled from the record itself, labeled so. Every field is a
    working draft a producer can ship or rewrite — never placeholder-speak."""
    title = meta.get("title") or "Community program"
    when = meta.get("date", "")
    names = _top_entities(insight)
    brief = _brief_text(insight)
    top = cands[0] if cands else {}

    dated = bool(re.search(r"\d{4}|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|"
                           r"oct|nov|dec)", title, re.I))
    titles = [t for t in [
        _sentences(str(top.get("text", "")), 70) if top else "",
        title + (f" — {when}" if when and not dated else ""),
        (f"{names[0]} and {names[1]}: {title}" if len(names) > 1 else ""),
    ] if t]
    chapters = [{"t": float(c["start"]), "label": _clip_label(c)}
                for c in cands]
    desc_lines = [title + (f" · {when}" if when and not dated else ""), ""]
    if brief:
        desc_lines += [_sentences(brief, 500), ""]
    if chapters:
        desc_lines += ["Moments:"] + [
            f"{fmt_t(ch['t'])} — {ch['label']}" for ch in chapters] + [""]
    desc_lines += ["Full program and record at the station. "
                   "Assembled locally from the transcript."]
    alt = [f"Video clip from {title}: {_clip_label(c)}" for c in cands]
    blurb = _sentences(brief or (top.get("text") or title), 320)
    social = {
        "vertical": (_clip_label(top) if top else title)
        + (f" — {title}" if top else ""),
        "feed": _sentences(brief or str(top.get("text") or ""), 200)
        + " (full program at the station)",
    }
    return {"origin": "extractive — assembled from the transcript, no model",
            "titles": titles, "description": "\n".join(desc_lines),
            "chapters": chapters, "alt_text": alt,
            "newsletter": blurb, "social": social}


# -- copy: generative only with the user's key --------------------------------

def copy_generative(meta: dict, cands: List[dict], insight: dict,
                    voice_note: str, instruction: str = "") -> dict:
    """One guarded call (czcore.llm). Raises RuntimeError sentences when
    there's no key or the API says no — the extractive draft stands."""
    from czcore import llm

    digest = {
        "title": meta.get("title"), "date": meta.get("date"),
        "clips": [{"start": c["start"], "end": c["end"],
                   "text": c.get("text", "")[:400]} for c in cands[:6]],
        "entities": _top_entities(insight, 8),
    }
    b = insight.get("brief")
    if isinstance(b, dict):
        digest["brief"] = str(b.get("text") or "")[:1200]
    prompt = (
        "You draft publish copy for a community media station. Voice: "
        + voice_note + ". Accuracy over reach; never invent facts, names or "
        "outcomes not present in the material; no hashtags unless asked; "
        "no engagement bait.\n\nMaterial (JSON):\n" + json.dumps(digest)
        + ("\n\nProducer instruction: " + instruction if instruction else "")
        + "\n\nAnswer with ONLY a JSON object: {\"titles\": [3 options ≤70 "
        "chars], \"description\": str (platform-ready, with the moment list "
        "kept), \"alt_text\": [one per clip, concrete and visual], "
        "\"newsletter\": str (≤320 chars), \"social\": {\"vertical\": str, "
        "\"feed\": str}}")
    text = llm.complete(prompt, max_tokens=1400)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("the model answered without JSON — kept the "
                           "extractive draft")
    try:
        d = json.loads(m.group(0))
    except ValueError as e:
        raise RuntimeError("the model's JSON didn't parse — kept the "
                           "extractive draft") from e
    model = llm.get_config().get("model", "model")
    out = {"origin": f"drafted by {model} on your key — review before use",
           "titles": [str(t)[:90] for t in (d.get("titles") or [])][:3] or None,
           "description": str(d.get("description") or "") or None,
           "alt_text": [str(a) for a in (d.get("alt_text") or [])] or None,
           "newsletter": str(d.get("newsletter") or "") or None,
           "social": d.get("social") if isinstance(d.get("social"), dict)
           else None}
    return {k: v for k, v in out.items() if v is not None}


def stamp_today() -> str:
    return date.today().isoformat()
