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
# The pure copy-assembly core, shared with the record's press so a kit opened
# at the desk and a kit read on the record are the same object (czcore/kit.py).
# Imported under the private names this module has always used internally, so
# every call site below — and `publisher.bundle`'s `from .kit import fmt_t`, and
# `tests.test_publisher`'s `from publisher.kit import copy_extractive` — is
# unchanged: the definitions moved, the surface did not.
from czcore.kit import (RATIO_NAMES, copy_extractive, fmt_t, kit_from_parts,
                        brief_text as _brief_text, clip_label as _clip_label,
                        sentences as _sentences, top_entities as _top_entities)

__all__ = ["RATIO_NAMES", "copy_extractive", "fmt_t", "kit_from_parts",
           "candidates", "meeting_meta", "new_kit", "sidecars", "load_kit",
           "save_kit", "copy_generative", "stamp_today"]


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
        # every folder a download can land in — Highlighter's own, and the
        # Downloads folder the Grabber (and full-video downloads) use now
        from suite.tools.highlighter import full_video_for
        return full_video_for(p.name)
    except ImportError:          # the package without the suite around it
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
    rendered yet. The review page edits this dict; renders fill `files`. The
    shape is assembled by `czcore.kit.kit_from_parts`, the core the record's
    press shares — the desk's only difference is where the parts come from
    (the sidecars beside a local video)."""
    ins = _read_json(sidecars(source)["insight"]) or {}
    return kit_from_parts(meeting_meta(source), candidates(source, n=n), ins)


# -- copy: extractive always lives in czcore.kit ------------------------------
# `_clip_label`, `_sentences`, `fmt_t`, `_top_entities`, `_brief_text` and
# `copy_extractive` moved to czcore/kit.py so the record's press shares one
# implementation; they are imported at the top of this module under their old
# names. `copy_generative` stays here — it is the one path that calls a model,
# and only the desk has the key.


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
