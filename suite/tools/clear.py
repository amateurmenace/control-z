"""Clear inside the suite — dialogue rescue with the covenant surfaces:
the residual monitor ("listen to what was removed"), before/after spectra,
and a null-test readout (residual RMS by band — energy in the presence band
means you're eating words).

Engine calls are exactly the CLI's (clear.dsp / .loudness / .roomtone /
.isolate); video sources get their audio extracted to the cache and the
cleaned track remuxed against the untouched video stream.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from czcore.tools import ToolNotFound

AUDIO_SUFFIXES = {".wav", ".aif", ".aiff", ".flac"}


def _cache_dir(path: str) -> Path:
    p = Path(path)
    tag = hashlib.md5(f"{p.resolve()}:{p.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    d = Path.home() / "Library" / "Caches" / "control-z" / "suite" / "clear" / tag
    d.mkdir(parents=True, exist_ok=True)
    return d


class NoAudioError(RuntimeError):
    """The source carries no audio track — a sentence, not an ffmpeg code."""


def _audio_source(path: str) -> Path:
    """Path to a soundfile-readable copy of the source's audio (cached).

    Raises NoAudioError (a sentence) rather than letting ffmpeg's exit code
    reach the user — a silent clip is a normal thing to open by mistake.
    """
    from czcore.media import probe

    p = Path(path)
    if p.suffix.lower() in AUDIO_SUFFIXES:
        return p
    wav = _cache_dir(path) / "extracted.wav"
    if wav.exists():
        return wav
    from czcore.tools import ffmpeg_path

    exe = ffmpeg_path()  # raises the honest sentence if truly absent
    try:
        if probe(str(p)).audio_streams == 0:
            raise NoAudioError(
                f"{p.name} has no audio track — open the clip that has the "
                "sound.")
    except NoAudioError:
        raise
    except Exception:
        pass  # unprobeable: let ffmpeg have its say below
    r = subprocess.run([exe, "-y", "-v", "error", "-i", str(p), "-vn",
                        "-acodec", "pcm_f32le", str(wav)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not wav.exists():
        wav.unlink(missing_ok=True)
        detail = (r.stderr or "").strip().splitlines()
        raise RuntimeError(
            f"couldn't pull audio out of {p.name}"
            + (f" — {detail[-1]}" if detail else "")
            + ". If it plays sound elsewhere, please file this clip's format "
              "at github.com/amateurmenace/control-z/issues")
    return wav


def _read(path: Path):
    import soundfile as sf

    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return audio, sr


def _peaks(audio, bins: int = 1200):
    """Per-bin min/max of the mono mix — the waveform the UI draws."""
    import numpy as np

    mono = audio.mean(axis=1)
    n = len(mono)
    if n == 0:
        return []
    edges = np.linspace(0, n, bins + 1).astype(int)
    out = []
    for i in range(bins):
        seg = mono[edges[i]:max(edges[i] + 1, edges[i + 1])]
        out.append([round(float(seg.min()), 4), round(float(seg.max()), 4)])
    return out


def _spectrogram_uri(audio, sr, width=1200, height=232) -> str:
    """Log-mag STFT as an amber-on-ink JPEG data URI (the design's colors)."""
    import base64

    import cv2
    import numpy as np

    mono = audio.mean(axis=1)
    nfft = 1024
    hop = max(1, len(mono) // width)
    frames = []
    win = np.hanning(nfft).astype(np.float32)
    for i in range(0, max(1, len(mono) - nfft), hop):
        seg = mono[i:i + nfft]
        if len(seg) < nfft:
            seg = np.pad(seg, (0, nfft - len(seg)))
        frames.append(np.abs(np.fft.rfft(seg * win))[: nfft // 2])
    if not frames:
        frames = [np.zeros(nfft // 2, np.float32)]
    spec = np.log10(np.stack(frames, axis=1) + 1e-6)
    spec = (spec - spec.min()) / max(spec.max() - spec.min(), 1e-6)
    spec = np.flipud(spec)  # low freq at the bottom
    spec = cv2.resize(spec.astype(np.float32), (width, height))
    # ink -> amber -> cream ramp
    ink = np.array([18, 18, 25], np.float32)
    amber = np.array([53, 168, 229], np.float32)   # BGR of #E5A835
    cream = np.array([238, 243, 245], np.float32)  # BGR of #F5F3EE
    t = spec[..., None]
    img = np.where(t < 0.6, ink + (amber - ink) * (t / 0.6),
                   amber + (cream - amber) * ((t - 0.6) / 0.4))
    ok, buf = cv2.imencode(".jpg", img.astype(np.uint8),
                           [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _band_rms(audio, sr):
    """Residual null-test: each band's share of the removed energy, in dB
    relative to the whole residual. Words live in 'presence' — a strong
    presence band in the residual means the pass is eating dialogue.

    Welch accumulation rather than one transform of the whole file: rfft
    promotes to complex128, so a feature-length interview would ask for tens
    of gigabytes to produce four numbers. Hann at 50% overlap keeps the
    spectral leakage of a loud hum out of the presence band.
    """
    import numpy as np

    mono = audio.mean(axis=1)
    bands = [("low", 0, 120), ("low-mid", 120, 1000),
             ("presence", 1000, 4000), ("high", 4000, sr / 2)]
    block = min(65536, len(mono))
    if block < 2:
        return [{"band": name, "rel_db": -180.0} for name, _, _ in bands]
    win = np.hanning(block).astype(np.float32)
    freqs = np.fft.rfftfreq(block, 1 / sr)
    masks = [(freqs >= lo) & (freqs < hi) for _, lo, hi in bands]
    energy = [0.0] * len(bands)
    for i in range(0, max(1, len(mono) - block + 1), block // 2):
        spec2 = np.abs(np.fft.rfft(mono[i:i + block] * win)) ** 2
        for k, m in enumerate(masks):
            energy[k] += float(spec2[m].sum())
    total = sum(energy) or 1e-18
    return [{"band": name,
             "rel_db": round(float(10 * np.log10(max(e, 1e-18) / total)), 1)}
            for (name, _, _), e in zip(bands, energy)]


def _overview(audio, sr) -> dict:
    from clear.loudness import measure_lufs
    import numpy as np

    peak = float(np.abs(audio).max())
    return {
        "peaks": _peaks(audio),
        "spectrogram": _spectrogram_uri(audio, sr),
        "lufs": round(measure_lufs(audio, sr), 1),
        "sample_peak_db": round(20 * np.log10(max(peak, 1e-9)), 1),
    }


def register_clear(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import FileResponse, JSONResponse

    from czcore.media import probe

    @app.post("/api/clear/overview")
    def api_overview(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        if not Path(path).is_file():
            return JSONResponse({"error": f"no such file: {path}"}, status_code=404)
        try:
            src = _audio_source(path)
            audio, sr = _read(src)
        except NoAudioError as e:
            return JSONResponse(
                {"error": f"{e} There's nothing here for Clear to rescue."},
                status_code=415)
        except ToolNotFound as e:
            # missing ffmpeg = OUR failure (500) — before the RuntimeError
            # clause, which must stay 415 for genuine extraction failures
            return JSONResponse({"error": str(e)}, status_code=500)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=415)
        except Exception as e:
            return JSONResponse(
                {"error": f"couldn't read {Path(path).name} as audio "
                          f"({e.__class__.__name__}) — if it plays elsewhere, "
                          "please file its format at "
                          "github.com/amateurmenace/control-z/issues"},
                status_code=415)
        if len(audio) == 0:
            return JSONResponse(
                {"error": f"{Path(path).name}'s audio track is empty — "
                          "nothing to rescue"}, status_code=415)
        has_video = False
        try:
            has_video = probe(path).video is not None
        except Exception:
            pass
        from clear import isolate as iso
        state = _load_state(path)
        return {
            "sr": sr, "channels": audio.shape[1],
            "duration": round(len(audio) / sr, 3),
            "has_video": has_video,
            "isolate_available": iso.available(),
            "isolate_hint": None if iso.available() else iso.install_hint().splitlines()[0],
            "original": _overview(audio, sr),
            "processed": state,   # earlier result for this exact file, if any
        }

    def _state_file(path: str) -> Path:
        return _cache_dir(path) / "result.json"

    def _load_state(path: str):
        f = _state_file(path)
        if f.exists():
            try:
                d = json.loads(f.read_text())
                if Path(d.get("out", "")).exists():
                    return d
            except ValueError:
                pass
        return None

    @app.post("/api/clear/process")
    def api_process(body: dict = Body(...)):
        import numpy as np
        import soundfile as sf

        from clear.dsp import declick, deess, dehum, detect_hum
        from clear.loudness import TARGETS, normalize

        path = str(Path(body["path"]).expanduser())
        dehum_mode = str(body.get("dehum", "auto"))
        do_declick = bool(body.get("declick", True))
        iso_amt = float(body.get("isolate", 0.0))
        deess_amt = float(body.get("deess", 0.0))
        loud = body.get("loudness")  # None | preset | LUFS number
        remux = bool(body.get("remux", True))
        name = Path(path).name

        def work(job):
            src = _audio_source(path)
            audio, sr = _read(src)
            original = audio.copy()
            log = []
            job.message = "processing…"

            if dehum_mode != "off":
                base = (float(dehum_mode) if dehum_mode not in ("auto",)
                        else detect_hum(audio, sr))
                if base:
                    audio = dehum(audio, sr, base)
                    log.append(f"de-hum: notched {base:.0f} Hz + harmonics")
                else:
                    log.append("de-hum: no mains hum detected (skipped)")
            job.check_cancel()
            if do_declick:
                audio, nfix = declick(audio, sr)
                log.append(f"de-click: repaired {nfix} samples" if nfix
                           else "de-click: clean")
            job.check_cancel()
            if iso_amt > 0:
                from clear import isolate as iso
                if iso.available():
                    job.message = "voice isolation (DeepFilterNet3)…"
                    audio = iso.isolate(audio, sr, mix_back=1.0 - iso_amt)
                    log.append(f"voice isolation: DF3, {1 - iso_amt:.0%} room kept")
                else:
                    log.append("voice isolation: binary not installed — skipped")
            if deess_amt > 0:
                audio = deess(audio, sr, amount=deess_amt)
                log.append(f"de-ess: {deess_amt:.0%}")
            job.check_cancel()
            loud_report = None
            if loud not in (None, "", "off"):
                target = TARGETS.get(loud)
                target = float(loud) if target is None else target
                audio, loud_report = normalize(audio, sr, target)
                # numpy scalars don't survive json.dumps
                loud_report = {k: (v.item() if hasattr(v, "item") else v)
                               for k, v in loud_report.items()}
                log.append(
                    f"loudness: {loud_report['measured_lufs']} LUFS → {target}"
                    f" (gain {loud_report['applied_db']:+.1f} dB"
                    + (", PEAK-LIMITED — needs dynamics work"
                       if loud_report["limited_by_peak"] else "") + ")")

            out = str(Path(path).with_suffix(".clear.wav"))
            sf.write(out, audio, sr)
            n = min(len(original), len(audio))
            residual = original[:n] - audio[:n]
            res_path = _cache_dir(path) / "residual.wav"
            sf.write(str(res_path), residual, sr)

            report = {
                "out": out, "log": log, "loudness": loud_report,
                "processed": _overview(audio, sr),
                "residual_bands": _band_rms(residual, sr),
                "residual_rms_db": round(20 * np.log10(
                    max(float(np.sqrt((residual ** 2).mean())), 1e-9)), 1),
            }
            job.check_cancel()
            if remux:
                try:
                    if probe(path).video is not None:
                        mux = str(Path(path).with_name(
                            f"{Path(path).stem}.clear{Path(path).suffix}"))
                        from czcore.tools import ffmpeg_path
                        exe = ffmpeg_path()  # raises, never passes None to subprocess
                        subprocess.run(
                            [exe, "-y", "-v", "quiet", "-i", path, "-i", out,
                             "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                             "-c:a", "pcm_s16le", "-shortest", mux], check=True)
                        report["remux"] = mux
                except Exception as e:
                    report["remux_error"] = f"remux failed: {e}"
            _state_file(path).write_text(json.dumps(report))
            job.message = "done"
            return report

        return jobs.start("process", work, tool="clear",
                          label=f"{name} — rescue pass").to_dict()

    @app.post("/api/clear/roomtone")
    def api_roomtone(body: dict = Body(...)):
        import soundfile as sf

        from clear.roomtone import find_quietest, generate, profile

        path = str(Path(body["path"]).expanduser())
        length = float(body.get("len", 30.0))
        src = _audio_source(path)
        audio, sr = _read(src)
        if body.get("from") is not None:
            s = int(float(body["from"]) * sr)
            e = s + int(2.0 * sr)
        else:
            s, e = find_quietest(audio, sr, 2.0)
        prof = profile(audio[s:e], sr)
        tone = generate(prof, length)
        out = str(Path(path).with_suffix(".roomtone.wav"))
        sf.write(out, tone, sr)
        tone_cache = _cache_dir(path) / "roomtone.wav"
        sf.write(str(tone_cache), tone, sr)
        return {"out": out, "profiled": [round(s / sr, 2), round(e / sr, 2)],
                "seconds": length}

    @app.get("/api/clear/audio")
    def api_audio(path: str, kind: str = "original"):
        p = str(Path(path).expanduser())
        if kind == "original":
            f = _audio_source(p)
        elif kind == "cleaned":
            f = Path(p).with_suffix(".clear.wav")
        elif kind == "residual":
            f = _cache_dir(p) / "residual.wav"
        elif kind == "roomtone":
            f = _cache_dir(p) / "roomtone.wav"
        else:
            return JSONResponse({"error": f"unknown kind {kind!r}"}, status_code=422)
        if not Path(f).exists():
            return JSONResponse(
                {"error": f"no {kind} audio yet — run the rescue pass first"},
                status_code=404)
        return FileResponse(str(f), media_type="audio/wav")
