"""Where the tools put things by default.

Media that belongs to the user lands in the user's media folder, one
subfolder per tool — never in app support, never scattered. App support
(model store, caches, catalogs) stays in czcore.models / suite.sessions.
"""

from __future__ import annotations

import sys
from pathlib import Path


def media_root() -> Path:
    """~/Movies/control-z on macOS, ~/Videos/control-z elsewhere — unless
    the user pointed the suite somewhere else (Settings → outputs; the
    choice lives in app support as outputs.json)."""
    try:
        import json
        f = support_dir() / "outputs.json"
        if f.exists():
            root = json.loads(f.read_text()).get("root", "")
            if root:
                return Path(root).expanduser()
    except (OSError, ValueError):
        pass
    base = Path.home() / ("Movies" if sys.platform == "darwin" else "Videos")
    return base / "control-z"


def set_media_root(root: str) -> Path:
    """Write (or clear, with "") the user's chosen output root. The
    downloads choice riding in the same file is kept either way."""
    d = _outputs_json()
    if not root:
        d.pop("root", None)
    else:
        d["root"] = str(Path(root).expanduser())
    _write_outputs_json(d)
    return media_root()


def media_dir(tool: str) -> Path:
    """The tool's output folder, created on first ask."""
    d = media_root() / tool
    d.mkdir(parents=True, exist_ok=True)
    return d


# -- downloads: where fetched videos land -------------------------------------
#
# "Where did my download go?" deserves a one-word answer: Downloads. Videos
# the suite FETCHES (Grabber, Highlighter's full-video download) land in
# ~/Downloads/Civic Media Studio unless the person picks another folder —
# separate from the outputs root above, which holds what the suite MAKES
# (renders, reels, kits) and the record's own files (Memory's corpus lives
# there; moving that root would orphan it, so it stays put).

DOWNLOADS_FOLDER = "Civic Media Studio"


def _outputs_json() -> dict:
    import json
    try:
        return json.loads((support_dir() / "outputs.json").read_text())
    except (OSError, ValueError):
        return {}


def _write_outputs_json(d: dict):
    import json
    f = support_dir() / "outputs.json"
    if d:
        f.write_text(json.dumps(d))
    else:
        f.unlink(missing_ok=True)


def downloads_root() -> Path:
    """The fetch destination (not created — see downloads_dir)."""
    chosen = str(_outputs_json().get("downloads") or "")
    if chosen:
        return Path(chosen).expanduser()
    return Path.home() / "Downloads" / DOWNLOADS_FOLDER


def downloads_chosen() -> bool:
    """True once the person confirmed or picked the folder themselves."""
    return bool(_outputs_json().get("downloads_confirmed")
                or _outputs_json().get("downloads"))


def set_downloads_root(root: str, confirm: bool = True) -> Path:
    """Point fetches somewhere else ("" = back to ~/Downloads/Civic Media
    Studio). Either way the choice counts as confirmed."""
    d = _outputs_json()
    if root:
        d["downloads"] = str(Path(root).expanduser())
    else:
        d.pop("downloads", None)
    if confirm:
        d["downloads_confirmed"] = True
    _write_outputs_json(d)
    return downloads_root()


def downloads_dir() -> Path:
    """The fetch destination, created on first ask."""
    d = downloads_root()
    d.mkdir(parents=True, exist_ok=True)
    return d


def support_dir(sub: str = "") -> Path:
    """control-z app support (models, bins, catalogs live under here)."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):  # pragma: no cover
        import os
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".local" / "share"
    d = base / "control-z"
    if sub:
        d = d / sub
    d.mkdir(parents=True, exist_ok=True)
    return d
