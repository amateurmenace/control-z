"""The AD script beside the meeting — sidecar, transcript, outputs.

One sidecar (*.narrator.json) holds the whole review state: the cue
list with drafts, statuses and lint. The descriptions transcript
(*.described.vtt) always carries EVERY description — gap-fitted or not
— because a description that can't fit on air still belongs to the
record (and the extended web mode). The interpreter package's writers
are reused: one wing, one caption pen.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from interpreter.tracks import to_vtt

SCRIPT_V = 1


def _stem(source: str) -> Path:
    p = Path(source)
    return (p / "meeting") if p.is_dir() else p.with_suffix("")


def sidecar(source: str) -> Path:
    return Path(str(_stem(source)) + ".narrator.json")


def out_paths(source: str) -> dict:
    base = str(_stem(source))
    return {"vtt": Path(base + ".described.vtt"),
            "ad": Path(base + ".ad.wav"),
            "mix_audio": Path(base + ".ad-mix.m4a"),
            "mix_video": Path(base + ".ad-mix.mp4"),
            "work": Path(base + ".ad-work")}


def load(source: str) -> Optional[dict]:
    f = sidecar(source)
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text())
        return d if d.get("version") == SCRIPT_V else None
    except (OSError, ValueError):
        return None


def save(source: str, script: dict) -> None:
    script["version"] = SCRIPT_V
    sidecar(source).write_text(json.dumps(script, ensure_ascii=False))


def new(source: str) -> dict:
    return {"version": SCRIPT_V, "source": str(source), "cues": [],
            "voice": None, "model": None, "review": "unreviewed"}


def described_vtt(cues: List[dict], note: str) -> str:
    """Every described cue, as WebVTT — the braille-display and search
    surface. Empty or unaccepted drafts stay out; the reviewer's word is
    the record's word."""
    rows = [{"start": c["start"], "end": c["end"], "text": c["text"]}
            for c in cues
            if c.get("text") and c.get("status") in ("accepted", "edited")]
    return to_vtt(rows, note=note)
