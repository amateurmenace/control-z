"""Publisher inside the suite — the review queue around the kit.

A source is anything Highlighter can read (local file with sidecars, or a
URL-session folder). The kit sidecar (`*.publisher.json`) is the state the
page edits; renders and bundles run as queue jobs and report where they
landed. Copy is extractive until the user asks the guarded key for more.
"""

from __future__ import annotations

import re
from pathlib import Path

from czcore.paths import media_dir

from publisher import brand as brandmod
from publisher import bundle as bundlemod
from publisher import kit as kitmod
from publisher import render as rendermod


def _lt_lines(kit: dict, brand: dict) -> tuple:
    """Lower-third defaults: the station brands the clip when it has a name;
    the meeting titles it otherwise. Per-kit override wins."""
    lt = kit.get("lt") or {}
    meta = kit.get("meta", {})
    title = str(meta.get("title", ""))[:56]
    if lt.get("line1") or lt.get("line2"):
        return str(lt.get("line1", "")), str(lt.get("line2", ""))
    if brand.get("station"):
        return brand["station"], (title or brand.get("line2", ""))
    return title, str(meta.get("date", ""))


def register_publisher(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    out_dir = media_dir("publisher")

    @app.get("/api/publisher/status")
    def api_status():
        from czcore import llm
        return {"brand": brandmod.get_brand(), "out": str(out_dir),
                "ai": llm.status(), "voices": list(brandmod.VOICES)}

    @app.post("/api/publisher/brand")
    def api_brand(body: dict = Body(...)):
        return {"brand": brandmod.set_brand(dict(body.get("patch") or {}))}

    @app.post("/api/publisher/open")
    def api_open(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        p = Path(src)
        if not (p.is_file() or p.is_dir()):
            return JSONResponse({"error": f"nothing at {src}"}, status_code=404)
        sc = kitmod.sidecars(src)
        has = {k: sc[k].exists() for k in ("scribe", "highlights", "insight")}
        video = kitmod.video_path(src)
        kit = kitmod.load_kit(src)
        if kit is None and (has["scribe"] or has["highlights"]):
            kit = kitmod.new_kit(src)
            kitmod.save_kit(src, kit)
        app.state.session.add_recent(src, "publisher")
        return {"source": src, "meta": kitmod.meeting_meta(src), "has": has,
                "video": str(video) if video else None, "kit": kit}

    @app.post("/api/publisher/kit")
    def api_kit(body: dict = Body(...)):
        src = str(body.get("source", ""))
        kit = kitmod.new_kit(src)
        if not kit["candidates"]:
            return JSONResponse(
                {"error": "no transcript or highlights beside that source — "
                          "run it through Highlighter (or Scribe) first"},
                status_code=422)
        kitmod.save_kit(src, kit)
        return {"kit": kit}

    @app.post("/api/publisher/save")
    def api_save(body: dict = Body(...)):
        src = str(body.get("source", ""))
        kit = body.get("kit")
        if not isinstance(kit, dict) or kit.get("version") != 1:
            return JSONResponse({"error": "that isn't a kit"}, status_code=422)
        kitmod.save_kit(src, kit)
        return {"ok": True}

    @app.post("/api/publisher/copy-ai")
    def api_copy_ai(body: dict = Body(...)):
        src = str(body.get("source", ""))
        kit = kitmod.load_kit(src)
        if not kit:
            return JSONResponse({"error": "open a source first"},
                                status_code=422)
        brand = brandmod.get_brand()
        try:
            gen = kitmod.copy_generative(
                kit.get("meta", {}), kit.get("candidates", []),
                kitmod._read_json(kitmod.sidecars(src)["insight"]) or {},
                brandmod.VOICES[brand["voice"]],
                str(body.get("instruction", "")))
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        kit["copy_ai"] = gen
        kitmod.save_kit(src, kit)
        return {"kit": kit}

    @app.post("/api/publisher/render")
    def api_render(body: dict = Body(...)):
        src = str(body.get("source", ""))
        kit = kitmod.load_kit(src)
        if not kit:
            return JSONResponse({"error": "open a source first"},
                                status_code=422)
        video = kitmod.video_path(src)
        if not video:
            return JSONResponse(
                {"error": "no local recording yet — fetch the full video in "
                          "Highlighter first, then render the kit"},
                status_code=409)
        kept = [c for c in kit.get("clips", []) if c.get("keep")]
        tasks = [(ci, c, r) for ci, c in enumerate(kept)
                 for r in (c.get("ratios") or ["16x9"])
                 if r in rendermod.RATIOS]
        if not tasks:
            return JSONResponse({"error": "keep at least one clip (and one "
                                          "ratio) before rendering"},
                                status_code=422)
        brand = brandmod.get_brand()
        l1, l2 = _lt_lines(kit, brand)
        name = bundlemod.slug(kit.get("meta", {}).get("title", ""))[:40]
        segs = kitmod.segments(src) if brand.get("captions", True) else []

        def work(job):
            total = len(tasks) + len(kept)
            written, files = [], []
            for i, (ci, clip, ratio) in enumerate(tasks):
                job.check_cancel()
                job.message = f"clip {ci + 1} — {ratio}"
                cues = rendermod.cues_for_span(
                    segs, float(clip["start"]), float(clip["end"])) if segs else []

                def prog(frac, _m, base=i):
                    job.progress = (base + frac) / total
                r = rendermod.render_clip(
                    str(video), float(clip["start"]), float(clip["end"]),
                    str(out_dir / f"{name}-c{ci + 1:02d}"), ratio=ratio,
                    cues=cues, brand=brand, lt_line1=l1, lt_line2=l2,
                    offset=float(clip.get("offset") or 0), progress=prog,
                    cancelled=lambda: job.cancel_requested)
                written.append(r["out"])
                files.append({"kind": "clip", "path": r["out"], "ratio": ratio,
                              "clip": ci, "captions": r["captions"]})
            for ci, clip in enumerate(kept):
                job.check_cancel()
                job.message = f"thumbnail {ci + 1}"
                job.progress = (len(tasks) + ci) / total
                mid = (float(clip["start"]) + float(clip["end"])) / 2
                t = rendermod.thumbnail(
                    str(video), mid, str(clip.get("label", ""))[:80], brand,
                    str(out_dir / f"{name}-c{ci + 1:02d}-thumb.png"))
                written.append(t["out"])
                files.append({"kind": "thumb", "path": t["out"],
                              "ratio": t["ratio"], "clip": ci})
            kit["files"] = files
            kitmod.save_kit(src, kit)
            job.message = f"{len(tasks)} cuts + {len(kept)} thumbs rendered"
            return {"written": written, "files": files}

        label = f"publish kit — {len(tasks)} cuts"
        return jobs.start("pubkit", work, tool="publisher", label=label).to_dict()

    @app.post("/api/publisher/bundle")
    def api_bundle(body: dict = Body(...)):
        src = str(body.get("source", ""))
        kit = kitmod.load_kit(src)
        if not kit:
            return JSONResponse({"error": "open a source first"},
                                status_code=422)
        files = kit.get("files") or []
        clips = [f for f in files if f.get("kind") == "clip"]
        thumbs = [f for f in files if f.get("kind") == "thumb"]
        if not clips:
            return JSONResponse({"error": "nothing rendered yet — render the "
                                          "kit first"}, status_code=422)

        def work(job):
            job.message = "assembling the bundle…"
            out = bundlemod.assemble(src, kit, clips, thumbs)
            job.message = (f"{out['clips']} clips + {out['thumbs']} thumbs, "
                           f"copy.md, zip")
            return {"out": out["dir"], "written": [out["zip"]],
                    "bundle": out}

        return jobs.start("pubzip", work, tool="publisher",
                          label="export bundle").to_dict()
