"""Per-town civic glossaries — versioned, reviewer-editable, honest.

Two layers: the seeds shipped in this package (interpreter/glossaries/
<town>.json) and the user's working copies in app support, which win the
moment they exist. Every term render carries a status — "suggested" is
what shipped or what a machine drafted; only a human reviewer flips it to
"vetted" in the UI. The seed ships suggested across the board on purpose:
a glossary nobody reviewed yet should say so.

Shape:
  {"version": 3, "town": "brookline", "label": "Brookline, MA",
   "keep": ["Coolidge Corner", ...],            # never translate these
   "terms": {"warrant article": {"es": {"text": "...",
                                        "status": "suggested|vetted"}, ...}}}
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

SEEDS = Path(__file__).parent / "glossaries"


def _user_dir(root: Optional[Path] = None) -> Path:
    if root is not None:
        return Path(root)
    from czcore.paths import support_dir
    return support_dir("interpreter") / "glossaries"


def _slug(town: str) -> str:
    s = re.sub(r"[^a-z0-9-]", "", town.strip().lower().replace(" ", "-"))
    if not s:
        raise ValueError("a town needs a name")
    return s


def towns(root: Optional[Path] = None) -> List[dict]:
    """Every glossary that exists, seed or working copy, as
    [{town, label, version, edited}] — edited says a working copy exists."""
    found = {}
    if SEEDS.is_dir():
        for f in sorted(SEEDS.glob("*.json")):
            try:
                d = json.loads(f.read_text())
                found[f.stem] = {"town": f.stem,
                                 "label": d.get("label") or f.stem,
                                 "version": int(d.get("version") or 0),
                                 "edited": False}
            except (OSError, ValueError):
                continue
    ud = _user_dir(root)
    if ud.is_dir():
        for f in sorted(ud.glob("*.json")):
            try:
                d = json.loads(f.read_text())
                found[f.stem] = {"town": f.stem,
                                 "label": d.get("label") or f.stem,
                                 "version": int(d.get("version") or 0),
                                 "edited": True}
            except (OSError, ValueError):
                continue
    return sorted(found.values(), key=lambda r: r["town"])


def load(town: str, root: Optional[Path] = None) -> dict:
    """The working copy when there is one, the packaged seed otherwise, an
    honest empty scaffold when neither — never an exception for a town we
    simply haven't met."""
    slug = _slug(town)
    for base in (_user_dir(root), SEEDS):
        f = base / f"{slug}.json"
        if f.exists():
            try:
                d = json.loads(f.read_text())
                d.setdefault("town", slug)
                d.setdefault("keep", [])
                d.setdefault("terms", {})
                return d
            except (OSError, ValueError):
                continue
    return {"version": 0, "town": slug, "label": town.strip() or slug,
            "keep": [], "terms": {}}


def save(town: str, data: dict, root: Optional[Path] = None) -> dict:
    """Write the working copy, version bumped — the seed in the package is
    never touched. Returns what was written."""
    slug = _slug(town)
    prev = load(slug, root)
    out = {"version": int(prev.get("version") or 0) + 1, "town": slug,
           "label": str(data.get("label") or prev.get("label") or slug),
           "keep": [str(t).strip() for t in (data.get("keep") or [])
                    if str(t).strip()],
           "terms": {}}
    for term, renders in (data.get("terms") or {}).items():
        term = str(term).strip()
        if not term or not isinstance(renders, dict):
            continue
        kept = {}
        for code, r in renders.items():
            if isinstance(r, str):
                r = {"text": r, "status": "suggested"}
            text = str((r or {}).get("text", "")).strip()
            if not text:
                continue
            status = "vetted" if (r or {}).get("status") == "vetted" \
                else "suggested"
            kept[str(code)] = {"text": text, "status": status}
        if kept:
            out["terms"][term] = kept
    ud = _user_dir(root)
    ud.mkdir(parents=True, exist_ok=True)
    (ud / f"{slug}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1))
    return out
