"""DaVinci Tools — the site's Resolve resources, fetchable from the app.

Three artifacts live in this repo (grades/ and packs/) and on the site's
download links: the node-tree PowerGrade, the middle-gray anchor grade,
and the Fusion template pack. A dev checkout serves its own copies; the
packaged app fetches the same bytes from the project's GitHub — the one
place they're published. Files land in ~/Downloads and reveal themselves.
"""

from __future__ import annotations

import shutil
from pathlib import Path

RAW = "https://github.com/amateurmenace/control-z/raw/main/"

ITEMS = {
    "node-tree": {
        "label": "Node Tree PowerGrade",
        "what": "the 10-node starting tree for every grade — import once, "
                "right-click a still → Apply Grade",
        "file": "grades/control-z-node-tree.zip",
        "guide": "https://control-z.org/node-tree.html",
    },
    "middle-gray": {
        "label": "Middle Gray Contrast Anchor",
        "what": "the 18% gray curve pivot — contrast that keeps exposure "
                "honest, plus the how and why",
        "file": "grades/control-z-middle-gray-anchor.zip",
        "guide": "https://control-z.org/middle-gray.html",
    },
    "fusion-templates": {
        "label": "Fusion Template Pack",
        "what": "ten paste-tested setups — fog, rack focus, depth grade, "
                "parallax — driven by Depth and Stencil mattes",
        "file": "packs/control-z-fusion-templates.zip",
        "guide": "https://control-z.org/templates.html",
    },
}


def _repo_root() -> Path:
    # suite/tools/davinci.py → the checkout root, when we're running from one
    return Path(__file__).resolve().parents[2]


def register_davinci(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    @app.get("/api/davinci/list")
    def api_list():
        rows = []
        for key, it in ITEMS.items():
            local = _repo_root() / it["file"]
            rows.append({
                "id": key, "label": it["label"], "what": it["what"],
                "guide": it["guide"],
                "filename": Path(it["file"]).name,
                "local": local.is_file(),
                "size": local.stat().st_size if local.is_file() else None,
            })
        return {"items": rows, "site": "https://control-z.org"}

    @app.post("/api/davinci/get")
    def api_get(body: dict = Body(...)):
        key = str(body.get("id", ""))
        it = ITEMS.get(key)
        if not it:
            return JSONResponse({"error": f"no such resource: {key}"},
                                status_code=404)
        dest = Path.home() / "Downloads" / Path(it["file"]).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        local = _repo_root() / it["file"]
        if local.is_file():
            shutil.copy(local, dest)
            return {"path": str(dest), "source": "this checkout"}
        # packaged app: the repo isn't on disk — fetch the published bytes
        from urllib.request import Request, urlopen
        try:
            req = Request(RAW + it["file"],
                          headers={"User-Agent": "control-z-suite"})
            with urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
        except Exception as e:
            return JSONResponse(
                {"error": "couldn't fetch it from the project's GitHub "
                          f"({e.__class__.__name__}) — the site has the same "
                          f"download: {it['guide']}"}, status_code=502)
        return {"path": str(dest), "source": "github"}
