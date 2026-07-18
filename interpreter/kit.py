"""The interpreter sidecar and the review queue — state beside the meeting.

Tracks land beside their source the way every suite sidecar does
(meeting.translated.<code>.srt in a session folder, program.translated.
<code>.srt beside a local file). The `translated.` infix is load-bearing:
Highlighter falls back to "first caption file in the folder, sorted" when
a transcript sidecar is missing, and `en` must keep winning that sort —
meeting.en.vtt < meeting.translated.es.vtt holds alphabetically, so our
tracks can sit beside the meeting without ever becoming its transcript.

Three files per meeting and language:
  *.translated.<code>.srt / .vtt   — the tracks themselves
  *.translated.<code>.json         — cues with source text + review marks
plus one kit sidecar (*.interpreter.json) holding per-language provenance
and flags, and one global review-queue.json in app support that the UI
reads across meetings.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional

KIT_V = 1


def _stem(source: str) -> Path:
    p = Path(source)
    return (p / "meeting") if p.is_dir() else p.with_suffix("")


def sidecar(source: str) -> Path:
    return Path(str(_stem(source)) + ".interpreter.json")


def track_paths(source: str, code: str) -> dict:
    base = f"{_stem(source)}.translated.{code}"
    return {"srt": Path(base + ".srt"), "vtt": Path(base + ".vtt"),
            "cues": Path(base + ".json")}


def load_kit(source: str) -> Optional[dict]:
    f = sidecar(source)
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text())
        return d if d.get("version") == KIT_V else None
    except (OSError, ValueError):
        return None


def save_kit(source: str, kit: dict) -> None:
    kit["version"] = KIT_V
    sidecar(source).write_text(json.dumps(kit, ensure_ascii=False))


def new_kit(source: str) -> dict:
    return {"version": KIT_V, "source": str(source), "languages": {}}


def load_cues(source: str, code: str) -> List[dict]:
    f = track_paths(source, code)["cues"]
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text()).get("cues") or []
    except (OSError, ValueError):
        return []


def save_cues(source: str, code: str, cues: List[dict]) -> None:
    track_paths(source, code)["cues"].write_text(
        json.dumps({"cues": cues}, ensure_ascii=False))


# -- the review queue: one tap on a bad line, one honest list ---------------

def _queue_file(root: Optional[Path] = None) -> Path:
    if root is not None:
        return Path(root) / "review-queue.json"
    from czcore.paths import support_dir
    return support_dir("interpreter") / "review-queue.json"


def read_queue(root: Optional[Path] = None) -> List[dict]:
    f = _queue_file(root)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text()).get("items") or []
    except (OSError, ValueError):
        return []


def _write_queue(items: List[dict], root: Optional[Path] = None) -> None:
    _queue_file(root).write_text(
        json.dumps({"items": items}, ensure_ascii=False))


def flag_line(source: str, title: str, code: str, i: int, src: str,
              text: str, note: str = "", on: bool = True,
              root: Optional[Path] = None) -> List[dict]:
    """Toggle a flag on cue i of one language's track. The queue keeps one
    open item per (source, lang, cue); flagging twice updates the note,
    un-flagging removes it."""
    items = read_queue(root)
    key = lambda r: (r.get("source"), r.get("lang"), r.get("i"))
    items = [r for r in items if key(r) != (str(source), code, int(i))]
    if on:
        items.append({"source": str(source), "title": title, "lang": code,
                      "i": int(i), "src": src, "text": text,
                      "note": note, "at": int(time.time()), "status": "open"})
    _write_queue(items, root)
    return items


def resolve_item(source: str, code: str, i: int,
                 root: Optional[Path] = None) -> List[dict]:
    """Drop a queue item once a reviewer handled it (with or without a
    correction — the correction itself is applied to the cues by the
    caller, which owns the track files)."""
    items = read_queue(root)
    items = [r for r in items
             if (r.get("source"), r.get("lang"), r.get("i"))
             != (str(source), code, int(i))]
    _write_queue(items, root)
    return items
