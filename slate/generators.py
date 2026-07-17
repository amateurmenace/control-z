"""The rest of the kit: bars & tone, countdown leader, program slate.

Bars come from ffmpeg's own smptehdbars source (they're the standard, why
redraw them); the tone is a −20 dBFS 1 kHz sine, the broadcast reference.
The countdown is drawn — big numeral, sweep, beep each second — and the
program slate is a card with the fields master control actually reads.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Callable, Optional

from czcore import ffrun
from czcore.media import resolve_preset


def bars_tone(out_path: str, duration: float = 30.0, width: int = 1920,
              height: int = 1080, fps: float = 29.97, tone_db: float = -20.0,
              preset: str = "prores-hq",
              progress: Optional[Callable[[float, str], None]] = None,
              cancelled: Optional[Callable[[], bool]] = None) -> dict:
    spec = resolve_preset(preset)
    out = str(Path(out_path).with_suffix("." + spec["container"]))
    rate = {29.97: "30000/1001", 59.94: "60000/1001",
            23.976: "24000/1001"}.get(round(fps, 3), f"{fps:g}")
    amp = 10 ** (tone_db / 20.0)
    args = ["-f", "lavfi", "-i",
            f"smptehdbars=size={width}x{height}:rate={rate}",
            "-f", "lavfi", "-i",
            f"sine=frequency=1000:sample_rate=48000,volume={amp:.6f}",
            "-t", f"{duration:.3f}"]
    args += ffrun.encoder_args(spec)
    args += [out]
    ffrun.run(args, duration=duration, progress=progress, cancelled=cancelled)
    return {"out": out, "duration": duration,
            "note": f"SMPTE HD bars + 1 kHz at {tone_db:g} dBFS"}


def _beep_wav(path: str, seconds: int, sr: int = 48000, hz: float = 1000.0,
              beep_len: float = 0.07, db: float = -12.0):
    import numpy as np
    import soundfile as sf

    n = int(seconds * sr)
    audio = np.zeros(n, dtype="f4")
    amp = 10 ** (db / 20.0)
    blip = (amp * np.sin(2 * math.pi * hz *
                         np.arange(int(beep_len * sr)) / sr)).astype("f4")
    fade = np.linspace(1, 0, len(blip), dtype="f4")
    blip *= fade
    for s in range(seconds):
        i = s * sr
        audio[i:i + len(blip)] = blip[:max(0, min(len(blip), n - i))]
    sf.write(path, audio, sr)


def countdown(out_path: str, seconds: int = 8, width: int = 1920,
              height: int = 1080, fps: float = 29.97,
              font: str = "", preset: str = "prores-422",
              progress: Optional[Callable[[float, str], None]] = None,
              cancelled: Optional[Callable[[], bool]] = None) -> dict:
    """Leader that counts seconds..1 — numeral, sweep, beep each second."""
    import av
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    from .fonts import find

    seconds = max(2, min(60, int(seconds)))
    spec = resolve_preset(preset)
    out = str(Path(out_path).with_suffix(".mov"))
    big = ImageFont.truetype(find(font), size=round(height * 0.42))
    small = ImageFont.truetype(find(font), size=round(height * 0.032))
    n = round(seconds * fps)
    rate = {29.97: "30000/1001", 59.94: "60000/1001",
            23.976: "24000/1001"}.get(round(fps, 3), None)

    with tempfile.TemporaryDirectory(prefix="slate-count-") as td:
        vid = str(Path(td) / "count.mov")
        wav = str(Path(td) / "count.wav")
        _beep_wav(wav, seconds)
        c = av.open(vid, "w")
        vs = c.add_stream(spec["codec"], rate=rate or round(fps))
        vs.width, vs.height = width, height
        vs.pix_fmt = spec["pix_fmt"]
        vs.options = {str(k): str(v) for k, v in spec["options"].items()}
        cx, cy, r = width / 2, height / 2, height * 0.46
        for i in range(n):
            if cancelled and cancelled():
                c.close()
                raise RuntimeError("cancelled")
            t = i / fps
            remain = seconds - int(t)
            frac = t - int(t)
            img = Image.new("RGB", (width, height), (18, 18, 24))
            d = ImageDraw.Draw(img)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(60, 60, 72),
                      width=max(2, height // 300))
            d.pieslice([cx - r, cy - r, cx + r, cy + r], start=-90,
                       end=-90 + frac * 360, fill=(36, 48, 31))
            num = str(remain)
            bb = d.textbbox((0, 0), num, font=big)
            d.text((cx - (bb[2] - bb[0]) / 2 - bb[0],
                    cy - (bb[3] - bb[1]) / 2 - bb[1]), num, font=big,
                   fill=(245, 243, 238))
            cap = "control-z · slate countdown"
            bb2 = d.textbbox((0, 0), cap, font=small)
            d.text((cx - (bb2[2] - bb2[0]) / 2, height * 0.93), cap,
                   font=small, fill=(126, 125, 117))
            vf = av.VideoFrame.from_ndarray(np.asarray(img), format="rgb24")
            for pkt in vs.encode(vf):
                c.mux(pkt)
            if progress and i % 10 == 0:
                progress(i / n * 0.85, f"frame {i + 1}/{n}")
        for pkt in vs.encode():
            c.mux(pkt)
        c.close()
        if progress:
            progress(0.9, "adding the beeps")
        ffrun.run(["-i", vid, "-i", wav, "-map", "0:v", "-map", "1:a",
                   "-c:v", "copy", "-c:a", "pcm_s16le", "-shortest", out])
    return {"out": out, "seconds": seconds}


def slate_card(fields: dict, out_path: str, width: int = 1920,
               height: int = 1080, font: str = "",
               still_seconds: float = 0.0, preset: str = "prores-422",
               progress: Optional[Callable[[float, str], None]] = None,
               cancelled: Optional[Callable[[], bool]] = None) -> dict:
    """Program slate PNG (and optional held ProRes still of it).

    fields: program, episode, producer, station, date, trt, audio, notes —
    all optional, drawn in that order when present.
    """
    from PIL import Image, ImageDraw, ImageFont

    from .fonts import find

    fpath = find(font)
    head = ImageFont.truetype(fpath, size=round(height * 0.058))
    label = ImageFont.truetype(fpath, size=round(height * 0.024))
    value = ImageFont.truetype(fpath, size=round(height * 0.034))

    img = Image.new("RGB", (width, height), (20, 20, 26))
    d = ImageDraw.Draw(img)
    mx, my = round(width * 0.10), round(height * 0.10)
    d.rectangle([mx, my, width - mx, height - my], outline=(50, 50, 62),
                width=max(2, height // 400))
    d.rectangle([mx, my, mx + round(width * 0.006), height - my],
                fill=(229, 168, 53))
    x = mx + round(width * 0.035)
    y = my + round(height * 0.045)
    d.text((x, y), str(fields.get("program") or "PROGRAM SLATE"),
           font=head, fill=(245, 243, 238))
    y += round(height * 0.105)
    rows = [(k.upper(), str(fields[k])) for k in
            ("episode", "producer", "station", "date", "trt", "audio", "notes")
            if fields.get(k)]
    for k, v in rows:
        d.text((x, y), k, font=label, fill=(126, 125, 117))
        d.text((x + round(width * 0.16), y - round(height * 0.006)), v,
               font=value, fill=(217, 214, 204))
        y += round(height * 0.062)
    png = str(Path(out_path).with_suffix(".png"))
    img.save(png)
    outs = {"png": png}
    if still_seconds > 0:
        import av
        import numpy as np

        spec = resolve_preset(preset)
        mov = str(Path(out_path).with_suffix(".mov"))
        c = av.open(mov, "w")
        vs = c.add_stream(spec["codec"], rate=25)
        vs.width, vs.height = width, height
        vs.pix_fmt = spec["pix_fmt"]
        vs.options = {str(k): str(v) for k, v in spec["options"].items()}
        arr = np.asarray(img)
        n = round(still_seconds * 25)
        for i in range(n):
            if cancelled and cancelled():
                c.close()
                raise RuntimeError("cancelled")
            for pkt in vs.encode(av.VideoFrame.from_ndarray(arr, format="rgb24")):
                c.mux(pkt)
            if progress and i % 25 == 0:
                progress(i / n, f"{i}/{n}")
        for pkt in vs.encode():
            c.mux(pkt)
        c.close()
        outs["mov"] = mov
    return outs
