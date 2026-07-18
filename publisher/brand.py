"""The station's brand kit — config, not code (specs/13 §P0.7).

One JSON in app support: station name, accent, lower-third style, caption
preference, voice preset. Every export reads it; the multi-station future
(In-a-Box) makes this file per-tenant instead of rewriting anything.
"""

from __future__ import annotations

import json

from czcore.paths import support_dir

DEFAULTS = {
    "station": "",                # "Brookline Interactive Group"
    "line2": "",                  # lower-third second line ("community media")
    "accent": "#3A9E8E",          # publisher mint until the station says otherwise
    "plate": "#14141A",
    "style": "bar",               # slate lower-third style: bar|block|line|clean
    "lt_seconds": 4.5,            # how long the lower-third holds on a clip
    "captions": True,             # burn captions on every cut
    "voice": "station",           # copy voice preset: station|casual|series
}

VOICES = {
    "station": "plain, factual, station-formal; no hype, no exclamation marks",
    "casual": "warm and conversational, still accurate; contractions welcome",
    "series": "match the tone of this show's prior episodes; consistent recurring format",
}


def _file():
    return support_dir() / "publisher-brand.json"


def get_brand() -> dict:
    """Defaults overlaid with whatever the station has set. Unknown keys are
    dropped so a stale file can't smuggle settings the code no longer reads."""
    out = dict(DEFAULTS)
    try:
        d = json.loads(_file().read_text())
        for k in DEFAULTS:
            if k in d:
                out[k] = d[k]
    except (OSError, ValueError):
        pass
    out["lt_seconds"] = max(0.0, min(10.0, float(out["lt_seconds"] or 0)))
    if out["voice"] not in VOICES:
        out["voice"] = "station"
    return out


def set_brand(patch: dict) -> dict:
    """Merge a patch into the saved brand; empty-string station stays legal
    (a station may prefer bare clips)."""
    cur = get_brand()
    for k in DEFAULTS:
        if k in patch:
            cur[k] = patch[k]
    _file().write_text(json.dumps(cur, indent=1))
    return get_brand()
