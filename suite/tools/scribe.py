"""Scribe inside the suite — the transcript-first workspace (specs/03 v0.2).

Transcription and diarization are the CLI's own calls; the suite adds the
editor surface: word-click navigation, inline edits saved back to the
sidecar, speaker renames, caption/marker exports, and the pull list →
CMX3600 selects EDL (the paper edit).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from czcore.tools import ToolNotFound
from scribe.transcript import Transcript

from .clear import NoAudioError, _audio_source


def _sidecar(path: str) -> Path:
    return Path(path).with_suffix(".scribe.json")


def register_scribe(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import FileResponse, JSONResponse

    from czcore.media import probe

    @app.post("/api/scribe/load")
    def api_load(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        sc = _sidecar(path)
        if not sc.exists():
            return {"transcript": None}
        try:
            return {"transcript": json.loads(sc.read_text())}
        except ValueError:
            return {"transcript": None,
                    "warning": "sidecar exists but couldn't be parsed — re-transcribe"}

    @app.post("/api/scribe/transcribe")
    def api_transcribe(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        model = body.get("model", "base")
        language = body.get("language") or None
        do_diarize = bool(body.get("diarize", True))
        speakers = int(body.get("speakers", -1))
        # proper names the audio likely carries — biased into the decoder so
        # people and places transcribe as themselves (capped: it's a bias,
        # not a document)
        hotwords = str(body.get("hotwords", "")).strip()[:1200] or None
        name = Path(path).name
        if not Path(path).is_file():
            return JSONResponse({"error": f"no such file: {path}"}, status_code=404)
        try:
            # fail with a sentence NOW rather than queueing a doomed job
            if probe(path).audio_streams == 0:
                return JSONResponse(
                    {"error": f"{name} has no audio track — there's nothing to "
                              "transcribe. Open the clip that has the sound."},
                    status_code=415)
        except Exception:
            pass  # unprobeable: let the job try and report honestly

        def work(job):
            from scribe.transcribe import transcribe

            job.message = "extracting audio…"
            wav = str(_audio_source(path))
            # ASR wants 16k mono; resample the cached extract to a temp wav
            import subprocess

            from czcore.tools import ffmpeg_path
            with tempfile.TemporaryDirectory(prefix="scribe-suite-") as td:
                wav16 = str(Path(td) / "audio.16k.wav")
                exe = ffmpeg_path()
                subprocess.run([exe, "-y", "-v", "quiet", "-i", wav, "-ac", "1",
                                "-ar", "16000", wav16], check=True)
                job.check_cancel()

                def prog(m):
                    job.message = m[:120]

                t = transcribe(wav16, model=model, language=language,
                               progress=prog, hotwords=hotwords)
                t.source = str(Path(path).resolve())
                job.check_cancel()
                if do_diarize:
                    from scribe import diarize as dz
                    if dz.available():
                        job.message = "labeling speakers…"
                        dz.diarize(t, wav16, num_speakers=speakers,
                                   progress=prog)
                    else:
                        job.message = "diarization models missing — skipped"
            _sidecar(path).write_text(t.to_json())
            job.message = (f"{len(t.segments)} segments · {t.language}"
                           + (f" · {len(t.speakers)} speakers" if t.speakers else ""))
            return json.loads(t.to_json())

        label = (f"{name} — transcribe ({model}"
                 f"{', speakers' if do_diarize else ''}"
                 f"{', names taught' if hotwords else ''})")
        return jobs.start("transcribe", work, tool="scribe", label=label).to_dict()

    @app.post("/api/scribe/save")
    def api_save(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        try:
            # validate by round-tripping the model
            t = Transcript.from_json(json.dumps(body["transcript"]))
        except (KeyError, TypeError, ValueError) as e:
            return JSONResponse({"error": f"transcript didn't validate: {e}"},
                                status_code=422)
        _sidecar(path).write_text(t.to_json())
        return {"ok": True, "segments": len(t.segments)}

    @app.post("/api/scribe/export")
    def api_export(body: dict = Body(...)):
        from scribe.exports import to_marker_edl, to_srt, to_vtt

        path = str(Path(body["path"]).expanduser())
        kinds = body.get("kinds", ["srt"])
        preset = body.get("captions", "standard")
        sc = _sidecar(path)
        if not sc.exists():
            return JSONResponse({"error": "transcribe first — no transcript sidecar"},
                                status_code=409)
        t = Transcript.from_json(sc.read_text())
        p = Path(path)
        info = None
        try:
            info = probe(path)
        except Exception:
            pass
        fps = info.video.fps if info and info.video else 24.0
        written = []
        if "srt" in kinds:
            f = p.with_suffix(".srt"); f.write_text(to_srt(t, preset)); written.append(str(f))
        if "vtt" in kinds:
            f = p.with_suffix(".vtt"); f.write_text(to_vtt(t, preset)); written.append(str(f))
        if "txt" in kinds:
            f = p.with_suffix(".txt"); f.write_text(t.full_text() + "\n"); written.append(str(f))
        if "markers" in kinds:
            start_tc = (info.timecode if info and info.timecode else "01:00:00:00")
            f = p.with_name(p.stem + ".markers.edl")
            f.write_text(to_marker_edl(t, fps, record_start_tc=start_tc))
            written.append(str(f))
        return {"written": written,
                "note": "Resolve: import the .srt onto a subtitle track; "
                        "Timeline → Import → Timeline Markers From EDL for markers"}

    @app.post("/api/scribe/selects")
    def api_selects(body: dict = Body(...)):
        from scribe.exports import Select, to_selects_edl

        path = str(Path(body["path"]).expanduser())
        sels_in = body.get("selects", [])
        handles = float(body.get("handles", 0.5))
        if not sels_in:
            return JSONResponse({"error": "pull list is empty — select words first"},
                                status_code=422)
        p = Path(path)
        info = None
        try:
            info = probe(path)
        except Exception:
            pass
        fps = info.video.fps if info and info.video else 24.0
        sels = [Select(start=float(s["start"]), end=float(s["end"]),
                       label=str(s.get("label", ""))) for s in sels_in]
        edl = to_selects_edl(
            sels, fps, reel=p.stem[:8].upper() or "AX",
            source_start_tc=(info.timecode if info and info.timecode else "00:00:00:00"),
            handles=handles, clip_name=p.name)
        out = p.with_suffix(".selects.edl")
        out.write_text(edl)
        return {"out": str(out), "selects": len(sels),
                "note": "Resolve: File → Import → Timeline → EDL, then relink "
                        "to the source clip"}

    @app.post("/api/scribe/tighten")
    def api_tighten(body: dict = Body(...)):
        """Extractive cleanup, visible before commit: propose the fillers and
        the long silences to cut, and (on write) leave a CMX3600 cut list of
        what's left. Nothing touches the source — the EDL is a proposal you
        import and relink, exactly like the manual pull list."""
        from scribe import tighten as tt
        from scribe.exports import to_selects_edl

        path = str(Path(body["path"]).expanduser())
        sc = _sidecar(path)
        if not sc.exists():
            return JSONResponse({"error": "transcribe first — no transcript "
                                          "sidecar to read"}, status_code=409)
        t = Transcript.from_json(sc.read_text())
        do_fillers = body.get("fillers", True)
        do_silence = body.get("silence", True)
        min_gap = max(0.2, float(body.get("min_gap", 0.7)))
        extra = [str(x) for x in (body.get("extra_fillers") or [])]
        removals = []
        if do_fillers:
            removals += tt.filler_removals(t, extra=extra)
        if do_silence:
            removals += tt.silence_removals(t, min_gap=min_gap)
        removals.sort(key=lambda r: r.start)
        summary = tt.summarize(t.duration, removals)
        pull = [{"start": r.start, "end": r.end, "kind": r.kind,
                 "text": r.text} for r in removals]
        if not body.get("write"):
            # the pull-list, visible — nothing written yet
            return {"removals": pull, **summary, "duration": t.duration}
        if not removals:
            return JSONResponse({"error": "nothing to tighten — no fillers or "
                                          "long silences found"},
                                status_code=409)
        p = Path(path)
        info = None
        try:
            info = probe(path)
        except Exception:
            pass
        fps = info.video.fps if info and info.video else 24.0
        keeps = tt.keep_ranges(t.duration, removals)
        edl = to_selects_edl(
            keeps, fps, reel=p.stem[:8].upper() or "AX",
            source_start_tc=(info.timecode if info and info.timecode
                             else "00:00:00:00"),
            clip_name=p.name)
        out = p.with_name(p.stem + ".tighten.edl")
        out.write_text(edl)
        return {"out": str(out), "keeps": len(keeps), "removals": pull,
                **summary,
                "note": "Resolve: File → Import → Timeline → EDL, then relink "
                        "to the source clip — the cut skips every filler and "
                        "long pause, and the original is untouched"}

    @app.get("/api/scribe/audio")
    def api_audio(path: str):
        p = str(Path(path).expanduser())
        if not Path(p).is_file():
            return JSONResponse({"error": "file moved or deleted"}, status_code=404)
        try:
            f = _audio_source(p)
        except ToolNotFound as e:
            # missing dependency = OUR failure (500), never the file's (415)
            return JSONResponse({"error": str(e)}, status_code=500)
        except (NoAudioError, RuntimeError) as e:
            return JSONResponse({"error": str(e)}, status_code=415)
        except Exception as e:
            return JSONResponse(
                {"error": f"couldn't pull audio out of {Path(p).name} "
                          f"({e.__class__.__name__})"}, status_code=415)
        return FileResponse(str(f), media_type="audio/wav")

    @app.get("/api/scribe/status")
    def api_status():
        from scribe import diarize as dz
        return {"diarize_available": dz.available(),
                "diarize_hint": None if dz.available()
                else dz.install_hint().splitlines()[0]}
