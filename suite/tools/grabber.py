"""Grabber inside the suite — search the portal, queue the fetches, conform.

Search is synchronous (one API call, a sentence on failure); fetch and
conform are queue jobs like every other render. The tenant is remembered in
the session — Brookline out of the box, any CivicClerk town by name.
"""

from __future__ import annotations

from pathlib import Path

from czcore import ytdlp
from czcore.paths import media_dir

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".webm", ".m4v", ".mpg")


def register_grabber(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    from czcore.media import presets_report
    from grabber.civicclerk import DEFAULT_TENANT, search_events
    from grabber.convert import CONFORM_PRESETS

    lib = media_dir("grabber")

    @app.get("/api/grabber/status")
    def api_status():
        presets = [p for p in presets_report() if p["id"] in CONFORM_PRESETS]
        return {"ytdlp": ytdlp.status(), "library": str(lib),
                "default_tenant": DEFAULT_TENANT, "presets": presets}

    @app.post("/api/grabber/ytdlp-check")
    def api_ytdlp_check(body: dict = Body(default={})):
        return {"ytdlp": ytdlp.check_async(force=bool(body.get("force")))}

    @app.post("/api/grabber/search")
    def api_search(body: dict = Body(...)):
        tenant = str(body.get("tenant") or DEFAULT_TENANT).strip()
        date_from = str(body.get("from", "")).strip()
        date_to = str(body.get("to", "")).strip()
        if not (date_from and date_to):
            return JSONResponse({"error": "pick both dates"}, status_code=422)
        try:
            events = search_events(tenant, date_from, date_to)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=502)
        with_video = sum(1 for e in events
                         if any(l["videoish"] for l in e["links"]))
        return {"tenant": tenant, "events": events, "with_video": with_video}

    @app.post("/api/grabber/fetch")
    def api_fetch(body: dict = Body(...)):
        url = str(body.get("url", "")).strip()
        name = str(body.get("name", "")).strip()
        quality = str(body.get("quality", "best")) or "best"
        if not url.lower().startswith(("http://", "https://")):
            return JSONResponse({"error": "that link isn't a URL"},
                                status_code=422)

        def work(job):
            def prog(p, m):
                if p >= 0:
                    job.progress = p
                job.message = m or job.message

            from grabber import zoomshare
            if zoomshare.is_zoom_share(url):
                # zoomgov (and zoom.us) share pages: our own resolver — the
                # flow Puppeteer used to drive, now four plain requests
                got = zoomshare.download(url, lib, progress=prog,
                                         cancelled=lambda: job.cancel_requested,
                                         name=name)
            else:
                got = ytdlp.download(url, lib, quality=quality, progress=prog,
                                     cancelled=lambda: job.cancel_requested)
            job.message = f"fetched {Path(got['path']).name}" + (
                f" (+{got['clips'] - 1} more clips)" if got.get("clips", 1) > 1 else "")
            return got

        label = f"fetch — {name or url[:70]}"
        return jobs.start("fetch", work, tool="grabber", label=label).to_dict()

    @app.get("/api/grabber/library")
    def api_library():
        rows = [{"path": str(p), "name": p.name, "size": p.stat().st_size,
                 "mtime": p.stat().st_mtime}
                for p in sorted(lib.iterdir())
                if p.suffix.lower() in VIDEO_EXTS]
        rows.sort(key=lambda r: -r["mtime"])
        return rows

    @app.post("/api/grabber/convert")
    def api_convert(body: dict = Body(...)):
        from grabber.convert import convert

        path = str(Path(body["path"]).expanduser())
        preset = str(body.get("preset", "prores-422"))
        height = body.get("height")
        fps = body.get("fps")
        if not Path(path).is_file():
            return JSONResponse({"error": f"no such file: {path}"},
                                status_code=404)

        def work(job):
            def prog(frac, m):
                job.progress = frac
                if m:
                    job.message = m

            job.message = "conforming…"
            rep = convert(path, str(Path(path).parent), preset=preset,
                          fps=float(fps) if fps else None,
                          height=int(height) if height else None,
                          progress=prog,
                          cancelled=lambda: job.cancel_requested)
            job.message = (f"{rep['label']} · "
                           f"{'hardware' if rep['hardware'] else 'software'}")
            return rep

        label = f"{Path(path).name} — conform ({preset})"
        return jobs.start("convert", work, tool="grabber", label=label).to_dict()
