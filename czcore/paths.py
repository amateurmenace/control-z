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
    """Write (or clear, with "") the user's chosen output root."""
    import json
    f = support_dir() / "outputs.json"
    if not root:
        f.unlink(missing_ok=True)
    else:
        f.write_text(json.dumps({"root": str(Path(root).expanduser())}))
    return media_root()


def media_dir(tool: str) -> Path:
    """The tool's output folder, created on first ask."""
    d = media_root() / tool
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
