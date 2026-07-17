"""Index inside the suite — the librarian's desk.

One catalog in app support; scans are queue jobs (they read every new
file's header), search is instant, selects leave as an FCPXML stringout or
CSV into ~/Movies/control-z/index.
"""

from __future__ import annotations

import time
from pathlib import Path

from czcore.paths import media_dir


def register_indexer(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    from indexer.catalog import Catalog

    cat = Catalog()

    @app.get("/api/index/status")
    def api_status():
        return {"folders": cat.folders(), "stats": cat.stats(),
                "exports": str(media_dir("index"))}

    @app.post("/api/index/folders")
    def api_folders(body: dict = Body(...)):
        try:
            if body.get("add"):
                cat.add_folder(str(body["add"]))
            if body.get("remove"):
                cat.remove_folder(str(body["remove"]))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=422)
        return {"folders": cat.folders()}

    @app.post("/api/index/scan")
    def api_scan():
        if not cat.folders():
            return JSONResponse({"error": "add a folder first — Index only "
                                          "reads where you point it"},
                                status_code=409)

        def work(job):
            st = cat.scan(progress=lambda m: setattr(job, "message", m[:120]),
                          cancelled=lambda: job.cancel_requested)
            job.message = (f"{st['seen']} seen · {st['added']} added · "
                           f"{st['updated']} updated · {st['missing']} missing")
            return st

        return jobs.start("scan", work, tool="index",
                          label="library scan").to_dict()

    @app.get("/api/index/search")
    def api_search(q: str = "", limit: int = 60):
        rows = cat.search(q, limit=max(1, min(500, limit)))
        return {"q": q, "rows": rows, "fts": cat.fts}

    @app.post("/api/index/export")
    def api_export(body: dict = Body(...)):
        from czcore.exports.fcpxml import selects_csv, stringout

        paths = body.get("paths") or []
        kind = str(body.get("kind", "fcpxml"))
        clips = cat.get_clips([str(p) for p in paths])
        if not clips:
            return JSONResponse({"error": "nothing selected — tick some clips "
                                          "first"}, status_code=422)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out = media_dir("index") / f"selects-{stamp}.{ 'csv' if kind == 'csv' else 'fcpxml' }"
        # the catalog stores audio as a stream count; fcpxml wants a flag
        for c in clips:
            c["audio"] = bool(c.get("audio"))
        out.write_text(selects_csv(clips) if kind == "csv" else stringout(clips))
        note = ("open in a spreadsheet" if kind == "csv" else
                "Resolve: File → Import → Timeline → the .fcpxml — it arrives "
                "as a stringout of your selects")
        return {"out": str(out), "clips": len(clips), "note": note}

    @app.get("/api/index/clip")
    def api_clip(path: str):
        rows = cat.get_clips([path])
        if not rows:
            return JSONResponse({"error": "not in the catalog"}, status_code=404)
        return rows[0]
