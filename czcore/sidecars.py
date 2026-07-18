"""What a clip already knows — the desk's sidecar law, in one place.

Every tool leaves its work beside the source: Scribe writes ``.scribe.json``,
Highlighter ``.highlights.json``, Publisher ``.publisher.json``, and so on.
Until now only each tool knew its own suffix; the library couldn't say what a
clip carries without opening every drawer. This module is the one table of
those suffixes and the one reader — Index scans with it, and any tool may ask
"what does this clip already have?" without re-learning the naming.

Stdlib only. A *kind* is the user-facing word; a kind may have several
suffixes (captions are .srt or .vtt); the tool id ties each kind to its
accent color in the UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

# (kind, suffixes, owning tool id) — order is display order.
KINDS: Tuple[Tuple[str, Tuple[str, ...], str], ...] = (
    ("words",    (".scribe.json",),      "scribe"),
    ("captions", (".srt", ".vtt"),       "scribe"),
    ("cut",      (".selects.edl",),      "scribe"),
    ("moments",  (".highlights.json",),  "highlighter"),
    ("insight",  (".insight.json",),     "highlighter"),
    ("kit",      (".publisher.json",),   "publisher"),
    ("pivot",    (".pivot.json",),       "pivot"),
    ("clear",    (".clear.wav",),        "clear"),
)

KIND_TOOL: Dict[str, str] = {k: tool for k, _s, tool in KINDS}


def collect(path: str | Path) -> Dict[str, float]:
    """Which sidecars sit beside this clip: kind → newest mtime.

    A kind with several suffixes reports the newest one present; a kind with
    none present is simply absent from the dict (the caller reads absence as
    "not yet", never as an error).
    """
    p = Path(path)
    found: Dict[str, float] = {}
    for kind, suffixes, _tool in KINDS:
        newest = 0.0
        for suf in suffixes:
            sc = p.with_suffix(suf)
            try:
                m = sc.stat().st_mtime
            except OSError:
                continue
            newest = max(newest, m)
        if newest:
            found[kind] = newest
    return found


def signature(found: Dict[str, float]) -> str:
    """A stable string of kind:mtime pairs — the scan's freshness check.

    Two scans of an untouched clip produce the identical signature; any
    sidecar appearing, vanishing, or being rewritten changes it, which is
    exactly when the catalog row deserves a refresh.
    """
    return ",".join(f"{k}:{found[k]:.0f}" for k in sorted(found))


def kinds_present(found: Iterable[str]) -> list:
    """The found kinds in display order (KINDS order, not dict order)."""
    have = set(found)
    return [k for k, _s, _t in KINDS if k in have]
