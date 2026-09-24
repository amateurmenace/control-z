"""One answer for "this needs an AI key" — every key-gated route uses it.

The page's api() helper sees `need: "llm_key"` and opens the add-a-key
popup (what a key is, where to get one, a box to paste it) instead of
showing a dead-end error; when a key is saved there, the original request
is retried once. `alt` names a keyless road when one exists (an on-device
model on the Models page), so the popup never implies a key is the only way.
"""

from __future__ import annotations


def need_key(feature: str, alt: str = ""):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        {"error": f"{feature} needs an AI key — add yours in the popup "
                  "(or Settings → AI)" + (f"; or {alt}" if alt else ""),
         "need": "llm_key", "feature": feature, "alt": alt or None},
        status_code=409)
