""".czsession — quitting is never destructive (specs/08 §2).

One lightweight JSON document: recent media, per-tool state blobs, UI
preferences (the Easy/Studio density per tool). Atomic writes; corrupt or
missing files degrade to a fresh session, never a crash.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

VERSION = 1
MAX_RECENTS = 12


def app_support() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:  # pragma: no cover — Windows lands in v1.x
        import os
        base = Path(os.environ.get("APPDATA", Path.home()))
    d = base / "control-z" / "suite"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fresh() -> dict:
    return {"version": VERSION, "recents": [], "tools": {}, "ui": {"density": {}}}


class Session:
    def __init__(self, path: Path = None):
        self.path = path or (app_support() / "session.czsession")
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            d = json.loads(self.path.read_text())
            if not isinstance(d, dict) or d.get("version") != VERSION:
                return _fresh()
            base = _fresh()
            base.update(d)
            # recents pointing at files that vanished are dropped quietly
            base["recents"] = [r for r in base.get("recents", [])
                               if Path(r.get("path", "")).is_file()][:MAX_RECENTS]
            return base
        except (OSError, ValueError):
            return _fresh()

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=1))
        tmp.replace(self.path)

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._data))

    def add_recent(self, path: str, tool: str = ""):
        with self._lock:
            rec = [r for r in self._data["recents"] if r["path"] != path]
            rec.insert(0, {"path": path, "tool": tool, "opened_at": time.time()})
            self._data["recents"] = rec[:MAX_RECENTS]
            self._save()

    def patch(self, updates: dict):
        """Shallow-merge per top-level key ('tools' and 'ui' merge one level deeper)."""
        with self._lock:
            for k, v in updates.items():
                if k in ("tools", "ui") and isinstance(v, dict):
                    for k2, v2 in v.items():
                        cur = self._data.setdefault(k, {})
                        if isinstance(v2, dict) and isinstance(cur.get(k2), dict):
                            cur[k2].update(v2)
                        else:
                            cur[k2] = v2
                elif k not in ("version", "recents"):
                    self._data[k] = v
            self._save()
