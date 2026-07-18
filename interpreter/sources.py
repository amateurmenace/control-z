"""Where readable meetings live — one thin adapter over Highlighter's
library, imported read-only (PARALLEL.md: other lanes' files are theirs;
the seam lives HERE so if lane A ever moves the internals, one file
swaps and the rest of Interpreter never notices).

A source is anything Highlighter can read: a URL-session folder under the
library's .meetings/, or a local file with a transcript sidecar. We only
list sources that already have words — translation starts from a read
meeting, never from raw video.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from suite.tools.highlighter import (VIDEO_EXTS, _is_session, _lib,
                                     _load_transcript, _meetings_dir,
                                     _session_meta, _sidecars)

# section clips carry a trailing [start-end] range yt-dlp stamps on them —
# they are pieces of the meeting, not the meeting
_SECTION = re.compile(r"\]\s*\[\d+-\d+\]$")


def list_sources() -> List[dict]:
    """Every meeting with words, newest first:
    [{source, title, duration, session, mtime, video}]."""
    rows = []
    md = _meetings_dir()
    if md.exists():
        for d in sorted(md.iterdir()):
            if not d.is_dir():
                continue
            sc, _, _ = _sidecars(str(d))
            if not sc.exists():
                continue
            meta = _session_meta(d)
            rows.append({"source": str(d), "title": meta["title"],
                         "duration": meta["duration"], "session": True,
                         "mtime": d.stat().st_mtime,
                         "video": video_for(str(d)) is not None})
    for p in sorted(_lib().iterdir()):
        if p.suffix.lower() not in VIDEO_EXTS or _SECTION.search(p.stem):
            continue
        sc, _, _ = _sidecars(str(p))
        if not sc.exists():
            continue
        rows.append({"source": str(p), "title": p.stem, "duration": None,
                     "session": False, "mtime": p.stat().st_mtime,
                     "video": True})
    rows.sort(key=lambda r: -r["mtime"])
    return rows


def transcript(source: str) -> Tuple[Optional[dict], Optional[str]]:
    """(scribe-shaped transcript, origin) — Highlighter's own loader."""
    return _load_transcript(source)


def meta(source: str) -> dict:
    p = Path(source)
    if _is_session(source):
        return _session_meta(p)
    return {"id": p.stem, "title": p.stem, "duration": None,
            "uploader": None, "url": None}


def video_for(source: str) -> Optional[str]:
    """The playable full recording for a source, if one exists locally:
    the file itself, or a session's library twin — the download whose name
    carries the session id but no section range. Section clips never
    qualify; a player with full-length tracks needs the full-length tape."""
    p = Path(source)
    if p.is_file():
        return str(p)
    if not p.is_dir():
        return None
    for f in sorted(_lib().iterdir()):
        if f.suffix.lower() in VIDEO_EXTS and f"[{p.name}]" in f.name \
                and not _SECTION.search(f.stem):
            return str(f)
    return None
