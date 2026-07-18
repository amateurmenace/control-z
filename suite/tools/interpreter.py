"""Interpreter inside the suite — every read meeting, carried across.

A source is anything Highlighter can read (session folder or local file
with sidecars). Translation runs as one queue job across the chosen
languages — coalesce once, translate chunked through czcore.mt, land
.srt/.vtt/.json beside the meeting — and the kit sidecar
(*.interpreter.json) carries per-language provenance the page shows as
UI, not a footnote. Flags go to the review queue; corrections come back
through it and rewrite the tracks in place.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from czcore import mt

from interpreter import glossary as glossarymod
from interpreter import kit as kitmod
from interpreter import sources as sourcesmod
from interpreter.tracks import to_srt, to_vtt

_MEDIA_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4",
                ".webm": "video/webm", ".mov": "video/quicktime",
                ".mkv": "video/x-matroska"}


def _lang_entry(kit: dict, code: str) -> dict:
    return (kit.get("languages") or {}).get(code) or {}


def _note_for(code: str, model: str, town: str, gv: int,
              corrected: int = 0) -> str:
    name = (mt.lang(code) or {}).get("name", code)
    tail = (f" · {corrected} reviewer-corrected lines" if corrected else
            " · unreviewed")
    return (f"AI translation — beta · {name} · {model} · glossary {town} "
            f"v{gv}{tail} · control-z Community Interpreter")


def _write_tracks(source: str, code: str, cues, note: str) -> dict:
    tp = kitmod.track_paths(source, code)
    tp["srt"].write_text(to_srt(cues))
    tp["vtt"].write_text(to_vtt(cues, note=note))
    kitmod.save_cues(source, code, cues)
    return {"srt": str(tp["srt"]), "vtt": str(tp["vtt"])}


def register_interpreter(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import FileResponse, JSONResponse

    @app.get("/api/interpreter/status")
    def api_status():
        from czcore import llm
        return {"languages": mt.LANGUAGES, "engine": mt.available(),
                "ai": llm.status(), "towns": glossarymod.towns(),
                "queue_open": len(kitmod.read_queue())}

    @app.get("/api/interpreter/library")
    def api_library():
        return {"rows": sourcesmod.list_sources()}

    def _open_payload(src: str) -> dict:
        t, origin = sourcesmod.transcript(src)
        meta = sourcesmod.meta(src)
        kit = kitmod.load_kit(src) or kitmod.new_kit(src)
        langs = {}
        for l in mt.LANGUAGES:
            entry = _lang_entry(kit, l["code"])
            tp = kitmod.track_paths(src, l["code"])
            langs[l["code"]] = {
                **entry,
                "has": tp["vtt"].exists() and tp["cues"].exists(),
                "stale": bool(entry) and t is not None
                and entry.get("n_source_segments") != len(t["segments"]),
            }
        return {"source": src, "meta": meta,
                "session": Path(src).is_dir(),
                "video": sourcesmod.video_for(src),
                "n_segments": len(t["segments"]) if t else 0,
                "origin": origin, "languages": langs}

    @app.post("/api/interpreter/open")
    def api_open(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        p = Path(src)
        if not (p.is_file() or p.is_dir()):
            return JSONResponse({"error": f"nothing at {src}"},
                                status_code=404)
        payload = _open_payload(src)
        if not payload["n_segments"]:
            return JSONResponse(
                {"error": "no words yet — this meeting needs a read first. "
                          "Open it in Highlighter (or run Scribe) and come "
                          "back."}, status_code=409)
        app.state.session.add_recent(src, "interpreter")
        return payload

    @app.post("/api/interpreter/translate")
    def api_translate(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        codes = [c for c in (body.get("langs") or [])
                 if mt.lang(str(c)) is not None]
        town = str(body.get("town") or "brookline")
        fresh = bool(body.get("fresh"))
        if not codes:
            return JSONResponse({"error": "pick at least one language"},
                                status_code=422)
        if mt.available()["engine"] is None:
            return JSONResponse({"error": mt.available()["sentence"]},
                                status_code=409)
        t, _ = sourcesmod.transcript(src)
        if not t or not t.get("segments"):
            return JSONResponse({"error": "no words to carry across — read "
                                          "the meeting first"},
                                status_code=409)
        meta = sourcesmod.meta(src)
        title = meta.get("title") or Path(src).name
        segs = t["segments"]
        gloss = glossarymod.load(town)

        def work(job):
            from czcore import llm

            model = llm.status()["model"]
            cues_en = mt.coalesce(segs)
            kit = kitmod.load_kit(src) or kitmod.new_kit(src)
            done, skipped = [], []
            for li, code in enumerate(codes):
                job.check_cancel()
                name = mt.lang(code)["name"]
                entry = _lang_entry(kit, code)
                tp = kitmod.track_paths(src, code)
                if (not fresh and entry
                        and entry.get("n_source_segments") == len(segs)
                        and tp["vtt"].exists()):
                    job.message = f"{name} — already carried (cached)"
                    skipped.append(code)
                    continue

                def prog(frac, msg, base=li):
                    job.progress = (base + frac) / len(codes)
                    job.message = msg

                cues = mt.translate_cues(
                    cues_en, code, glossary=gloss, progress=prog,
                    check_cancel=job.check_cancel)
                n_fb = sum(1 for c in cues if c.get("fallback"))
                n_miss = sum(1 for c in cues if c.get("miss"))
                note = _note_for(code, model, gloss.get("town", town),
                                 int(gloss.get("version") or 0))
                paths = _write_tracks(src, code, cues, note)
                kit.setdefault("languages", {})[code] = {
                    "engine": "key", "model": model,
                    "glossary": {"town": gloss.get("town", town),
                                 "version": int(gloss.get("version") or 0)},
                    "created": int(time.time()),
                    "n_source_segments": len(segs),
                    "n_cues": len(cues), "n_fallback": n_fb,
                    "n_miss": n_miss, "n_corrected": 0,
                    "review": "unreviewed", **paths,
                }
                kitmod.save_kit(src, kit)
                done.append(code)
            said = []
            if done:
                said.append(f"{len(done)} track{'s' if len(done) != 1 else ''}"
                            f" written ({', '.join(done)})")
            if skipped:
                said.append(f"{len(skipped)} cached")
            job.message = " · ".join(said) or "nothing to do"
            return {"done": done, "skipped": skipped,
                    "n_cues": len(cues_en)}

        names = ", ".join(mt.lang(c)["name"] for c in codes[:3])
        if len(codes) > 3:
            names += f" +{len(codes) - 3}"
        return jobs.start("interpret", work, tool="interpreter",
                          label=f"carry across → {names} — {title[:44]}"
                          ).to_dict()

    @app.post("/api/interpreter/cues")
    def api_cues(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        code = str(body.get("lang", ""))
        cues = kitmod.load_cues(src, code)
        if not cues:
            return JSONResponse({"error": "no track in that language yet"},
                                status_code=404)
        return {"lang": code, "cues": cues}

    @app.post("/api/interpreter/flag")
    def api_flag(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        code = str(body.get("lang", ""))
        i = int(body.get("i", -1))
        note = str(body.get("note", ""))[:400]
        on = bool(body.get("on", True))
        cues = kitmod.load_cues(src, code)
        if not (0 <= i < len(cues)):
            return JSONResponse({"error": "that line isn't on this track"},
                                status_code=404)
        if on:
            cues[i]["flag"] = {"note": note, "at": int(time.time())}
        else:
            cues[i].pop("flag", None)
        kitmod.save_cues(src, code, cues)
        kit = kitmod.load_kit(src) or kitmod.new_kit(src)
        entry = kit.setdefault("languages", {}).setdefault(code, {})
        entry["n_flags"] = sum(1 for c in cues if c.get("flag"))
        kitmod.save_kit(src, kit)
        title = sourcesmod.meta(src).get("title") or Path(src).name
        kitmod.flag_line(src, title, code, i, cues[i].get("src", ""),
                         cues[i].get("text", ""), note=note, on=on)
        return {"i": i, "on": on, "n_flags": entry["n_flags"]}

    @app.get("/api/interpreter/queue")
    def api_queue():
        return {"items": kitmod.read_queue()}

    @app.post("/api/interpreter/resolve")
    def api_resolve(body: dict = Body(...)):
        src = str(body.get("source", ""))
        code = str(body.get("lang", ""))
        i = int(body.get("i", -1))
        correction = str(body.get("correction", "")).strip()
        cues = kitmod.load_cues(src, code)
        if not (0 <= i < len(cues)):
            kitmod.resolve_item(src, code, i)
            return {"ok": True, "applied": False,
                    "note": "the track moved on — flag dropped"}
        kit = kitmod.load_kit(src) or kitmod.new_kit(src)
        entry = kit.setdefault("languages", {}).setdefault(code, {})
        applied = False
        if correction:
            cues[i]["text"] = correction
            cues[i]["corrected"] = True
            cues[i].pop("miss", None)
            applied = True
        cues[i].pop("flag", None)
        kitmod.save_cues(src, code, cues)
        n_corr = sum(1 for c in cues if c.get("corrected"))
        entry["n_corrected"] = n_corr
        entry["n_flags"] = sum(1 for c in cues if c.get("flag"))
        if applied:
            entry["review"] = "corrected"
            g = entry.get("glossary") or {}
            note = _note_for(code, entry.get("model", "?"),
                             g.get("town", "?"), int(g.get("version") or 0),
                             corrected=n_corr)
            _write_tracks(src, code, cues, note)
        kitmod.save_kit(src, kit)
        kitmod.resolve_item(src, code, i)
        return {"ok": True, "applied": applied, "n_corrected": n_corr}

    @app.get("/api/interpreter/glossary")
    def api_glossary(town: str = "brookline"):
        try:
            return {"glossary": glossarymod.load(town),
                    "towns": glossarymod.towns()}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=422)

    @app.post("/api/interpreter/glossary")
    def api_glossary_save(body: dict = Body(...)):
        town = str(body.get("town", ""))
        data = body.get("data")
        if not isinstance(data, dict):
            return JSONResponse({"error": "that isn't a glossary"},
                                status_code=422)
        try:
            return {"glossary": glossarymod.save(town, data),
                    "towns": glossarymod.towns()}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=422)

    @app.get("/api/interpreter/track")
    def api_track(path: str, lang: str, fmt: str = "vtt", dl: int = 0):
        src = str(Path(path).expanduser())
        if lang == "en":
            from suite.tools.highlighter import _captions_for
            cap = _captions_for(Path(src))
            if cap is None:
                return JSONResponse({"error": "no English captions here"},
                                    status_code=404)
            f = cap
        else:
            tp = kitmod.track_paths(src, lang)
            f = tp.get(fmt if fmt in ("srt", "vtt") else "vtt")
            if f is None or not f.exists():
                return JSONResponse({"error": "no track in that language "
                                              "yet"}, status_code=404)
        headers = {"Cache-Control": "no-cache"}
        if dl:
            headers["Content-Disposition"] = \
                f'attachment; filename="{f.name}"'
        media = "text/vtt" if f.suffix == ".vtt" else "text/plain"
        return FileResponse(str(f), media_type=media, headers=headers)

    @app.get("/api/interpreter/media")
    def api_media(path: str):
        p = Path(path).expanduser()
        if not p.is_file():
            return JSONResponse({"error": "file moved or deleted"},
                                status_code=404)
        return FileResponse(str(p), media_type=_MEDIA_TYPES.get(
            p.suffix.lower(), "application/octet-stream"))
