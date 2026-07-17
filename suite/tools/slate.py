"""Slate inside the suite — the maker's bench.

The preview IS the renderer: every knob change re-renders a half-size
frame through the same code that writes the ProRes, so what you see is
what ships. Exports land in ~/Movies/control-z/slate.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from czcore.paths import media_dir


def _slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()
    return (s[:48] or fallback)


def register_slate(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse, Response

    from slate.fonts import discover
    from slate.lowerthird import LowerThird, Renderer, draw_safe_areas

    out_dir = media_dir("slate")

    @app.get("/api/slate/status")
    def api_status():
        return {"fonts": discover(), "out": str(out_dir)}

    @app.post("/api/slate/preview")
    def api_preview(body: dict = Body(...)):
        params = dict(body.get("params") or {})
        t = body.get("t")
        # preview at half size, same fractions — the renderer scales by height
        params["width"] = int(params.get("width", 1920)) // 2
        params["height"] = int(params.get("height", 1080)) // 2
        try:
            p = LowerThird.from_dict(params)
            r = Renderer(p)
            img = r.frame(float(t)) if t is not None else r.hold_frame()
            if body.get("safe"):
                img = draw_safe_areas(img)
        except Exception as e:
            return JSONResponse({"error": f"couldn't draw that: {e}"},
                                status_code=422)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return Response(content=buf.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    @app.post("/api/slate/render")
    def api_render(body: dict = Body(...)):
        from slate import render as slrender

        params = dict(body.get("params") or {})
        formats = [f for f in body.get("formats", ["prores"])
                   if f in ("prores", "png", "gif")]
        if not formats:
            return JSONResponse({"error": "pick at least one format"},
                                status_code=422)
        p = LowerThird.from_dict(params)
        stem = str(out_dir / _slug(p.line1, "lower-third"))

        def work(job):
            def prog(frac, m):
                job.progress = frac
                if m:
                    job.message = m

            wrote, notes = [], []
            for kind in formats:
                job.check_cancel()
                if kind == "prores":
                    job.message = "ProRes 4444 with alpha…"
                    wrote.append(slrender.write_prores4444(
                        p, stem, progress=prog,
                        cancelled=lambda: job.cancel_requested)["out"])
                elif kind == "png":
                    wrote.append(slrender.write_png(p, stem)["out"])
                else:
                    job.message = "GIF (web use)…"
                    r = slrender.write_gif(p, stem, progress=prog,
                                           cancelled=lambda: job.cancel_requested)
                    wrote.append(r["out"])
                    notes.append(r["note"])
            job.message = f"{len(wrote)} file{'s' if len(wrote) != 1 else ''} written"
            return {"written": wrote, "notes": notes}

        label = f"{p.line1 or 'lower third'} — {'+'.join(formats)}"
        return jobs.start("l3", work, tool="slate", label=label).to_dict()

    @app.post("/api/slate/generate")
    def api_generate(body: dict = Body(...)):
        from slate import generators

        kind = str(body.get("kind", ""))
        if kind not in ("bars", "countdown", "card"):
            return JSONResponse({"error": "unknown generator"}, status_code=422)

        def work(job):
            def prog(frac, m):
                job.progress = frac
                if m:
                    job.message = m

            cancelled = lambda: job.cancel_requested  # noqa: E731
            if kind == "bars":
                r = generators.bars_tone(
                    str(out_dir / "bars-tone"),
                    duration=float(body.get("duration", 30.0)),
                    progress=prog, cancelled=cancelled)
                job.message = r["note"]
                return r
            if kind == "countdown":
                r = generators.countdown(
                    str(out_dir / "countdown"),
                    seconds=int(body.get("seconds", 8)),
                    font=str(body.get("font", "")),
                    progress=prog, cancelled=cancelled)
                job.message = f"{r['seconds']}s leader with beeps"
                return r
            fields = dict(body.get("fields") or {})
            r = generators.slate_card(
                fields, str(out_dir / _slug(fields.get("program", ""), "slate-card")),
                font=str(body.get("font", "")),
                still_seconds=float(body.get("still", 0.0)),
                progress=prog, cancelled=cancelled)
            job.message = "slate card written"
            return r

        labels = {"bars": "SMPTE bars + tone", "countdown": "countdown leader",
                  "card": "program slate"}
        return jobs.start(kind, work, tool="slate", label=labels[kind]).to_dict()
