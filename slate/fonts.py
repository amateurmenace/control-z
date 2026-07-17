"""System fonts, listed and found — no bundled type, no downloads.

Stations have opinions about type; we use what the machine has. Names are
file stems (HelveticaNeue, Arial Bold) — honest about what we can know
without a font-parsing dependency. A full path always works too.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

_EXTS = (".ttf", ".otf", ".ttc")

_DIRS_MAC = ("/System/Library/Fonts", "/System/Library/Fonts/Supplemental",
             "/Library/Fonts", "~/Library/Fonts")
_DIRS_LINUX = ("/usr/share/fonts", "/usr/local/share/fonts", "~/.fonts",
               "~/.local/share/fonts")
_DIRS_WIN = ("C:/Windows/Fonts",)

_DEFAULT_ORDER = ("HelveticaNeue", "Helvetica", "SFNS", "Arial",
                  "DejaVuSans", "LiberationSans-Regular", "NotoSans-Regular")


def _dirs() -> List[Path]:
    if sys.platform == "darwin":
        names = _DIRS_MAC
    elif sys.platform.startswith("win"):  # pragma: no cover
        names = _DIRS_WIN
    else:
        names = _DIRS_LINUX
    return [Path(n).expanduser() for n in names]


@lru_cache(maxsize=1)
def _discover_cached() -> tuple:
    return tuple((f["name"], f["path"]) for f in _discover())


def discover() -> List[dict]:
    """[{name, path}] for every usable font file, deduped by name.
    Cached for the session — a 700-file walk per preview keystroke is waste."""
    return [{"name": n, "path": p} for n, p in _discover_cached()]


def _discover() -> List[dict]:
    seen = {}
    for d in _dirs():
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.suffix.lower() in _EXTS and p.stem not in seen:
                seen[p.stem] = str(p)
    return [{"name": k, "path": v} for k, v in sorted(seen.items())]


def find(name_or_path: Optional[str]) -> str:
    """A font the renderer can open: exact path, name match, or the default."""
    if name_or_path:
        p = Path(str(name_or_path)).expanduser()
        if p.is_file():
            return str(p)
        low = str(name_or_path).lower()
        table = {f["name"].lower(): f["path"] for f in discover()}
        if low in table:
            return table[low]
        for n, path in table.items():
            if low in n:
                return path
    table = {f["name"]: f["path"] for f in discover()}
    for want in _DEFAULT_ORDER:
        if want in table:
            return table[want]
    if table:
        return next(iter(table.values()))
    raise RuntimeError("no usable fonts found on this system — point Slate "
                       "at a .ttf/.otf file directly")
