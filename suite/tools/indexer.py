"""Index inside the suite — the librarian's desk.

One catalog in app support; scans are queue jobs (they read every new
file's header), search is instant, selects leave as an FCPXML stringout or
CSV into ~/Movies/control-z/index. The catalog also knows what every clip
already carries (czcore.sidecars) — and the coverage band turns each gap
into one click of work (the batch line's first road: words for the
wordless, Scribe's engine, one queue job).
"""

from __future__ import annotations

import tempfile
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

    @app.get("/api/index/gaps")
    def api_gaps(kind: str = "words"):
        return {"kind": kind, "clips": cat.gaps(kind)}

    @app.post("/api/index/transcribe-missing")
    def api_transcribe_missing(body: dict = Body(...)):
        """The batch line, first road: words for every clip that has sound
        and no transcript. Scribe's engine, imported never reimplemented;
        one queue job; per-clip failures reported by name, not swallowed.
        Speakers are the desk's craft — the batch writes words only and
        says so."""
        model = str(body.get("model", "base"))
        clips = ([c for c in cat.gaps("words")
                  if c["path"] in {str(p) for p in body["paths"]}]
                 if body.get("paths") else cat.gaps("words"))
        if not clips:
            return JSONResponse(
                {"error": "every clip with sound already has its words — "
                          "there is no gap to fill"}, status_code=409)

        def work(job):
            import subprocess

            from czcore.tools import ffmpeg_path
            from scribe.transcribe import transcribe

            done, failed = [], []
            exe = ffmpeg_path()
            for i, c in enumerate(clips, 1):
                job.check_cancel()
                p = Path(c["path"])
                if not p.is_file():
                    failed.append(f"{p.name}: drive unplugged?")
                    continue
                job.message = f"{i}/{len(clips)} · {p.name}"
                try:
                    with tempfile.TemporaryDirectory(
                            prefix="index-batch-") as td:
                        wav16 = str(Path(td) / "audio.16k.wav")
                        subprocess.run(
                            [exe, "-y", "-v", "quiet", "-i", str(p),
                             "-ac", "1", "-ar", "16000", wav16], check=True)
                        job.check_cancel()
                        t = transcribe(
                            wav16, model=model,
                            progress=lambda m, i=i: setattr(
                                job, "message",
                                f"{i}/{len(clips)} · {p.name} — {m}"[:120]))
                    t.source = str(p.resolve())
                    p.with_suffix(".scribe.json").write_text(t.to_json())
                    done.append(str(p))
                except (ImportError, OSError) as e:
                    # a missing runtime dooms every clip the same way —
                    # stop with the sentence instead of failing N times
                    raise RuntimeError(
                        f"the ASR engine isn't ready ({e}) — open Scribe "
                        "once, or Settings → runtimes, then run the batch "
                        "again") from e
                except Exception as e:
                    failed.append(f"{p.name}: {e}")
            job.message = "re-logging the fresh words…"
            cat.scan(only=done)
            msg = f"{len(done)} of {len(clips)} clips got their words"
            if failed:
                msg += f" · {len(failed)} failed"
            job.message = msg + " (words only — open a clip in Scribe for speakers)"
            return {"done": done, "failed": failed}

        label = (f"the batch line — words for {len(clips)} "
                 f"clip{'s' if len(clips) != 1 else ''} ({model})")
        return jobs.start("index-words", work, tool="index",
                          label=label).to_dict()
