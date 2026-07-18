"""Cut one candidate three ways — captions burned, station on the frame.

Every render is one ffmpeg graph: trim → aspect transform → lower-third
overlay (Slate's renderer, held and faded) → caption strips (Pillow, the
suite's ink plate) → encode through the house presets. Captions render as
images, not subtitle filters, so the type matches the brand on any ffmpeg
build. The vertical and square cuts crop from center with a producer
offset — the honest fast path; Pivot remains the smart-reframe door.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, List, Optional

from czcore import ffrun
from czcore.media import probe, resolve_preset

RATIOS = {"16x9": (1920, 1080), "1x1": (1080, 1080), "9x16": (1080, 1920)}


# -- caption cues (pure logic, tested) ---------------------------------------

def cues_for_span(segments: List[dict], start: float, end: float,
                  max_chars: int = 46, max_dur: float = 4.5) -> List[dict]:
    """Transcript segments → caption cues inside [start, end), times made
    relative to the clip. Word timings drive the grouping when present;
    plain segments are clipped to the span otherwise. Returns [{s, e, text}]."""
    cues: List[dict] = []

    def push(s: float, e: float, text: str):
        text = " ".join(str(text).split())
        if not text or e - s < 0.2:
            return
        cues.append({"s": round(max(0.0, s - start), 3),
                     "e": round(min(end, e) - start, 3), "text": text})

    for seg in segments:
        s0, e0 = float(seg.get("start", 0)), float(seg.get("end", 0))
        if e0 <= start or s0 >= end:
            continue
        words = seg.get("words") or []
        timed = [w for w in words
                 if isinstance(w, dict) and w.get("s") is not None
                 and start - 0.05 <= float(w["s"]) < end]
        if timed:
            cur, cs = [], None
            for w in timed:
                tok = str(w.get("w", "")).strip()
                if not tok:
                    continue
                if cs is None:
                    cs = float(w["s"])
                cur.append((tok, float(w.get("e") or w["s"])))
                line = " ".join(t for t, _ in cur)
                if len(line) >= max_chars or cur[-1][1] - cs >= max_dur:
                    push(cs, cur[-1][1], line)
                    cur, cs = [], None
            if cur:
                push(cs, cur[-1][1], " ".join(t for t, _ in cur))
        else:
            text = str(seg.get("text", ""))
            if len(text) <= max_chars * 2:
                push(max(s0, start), min(e0, end), text)
            else:
                # long untimed segment: split evenly across its span
                parts, words_ = [], text.split()
                cur = ""
                for tok in words_:
                    if len(cur) + len(tok) + 1 > max_chars * 2 and cur:
                        parts.append(cur)
                        cur = tok
                    else:
                        cur = (cur + " " + tok).strip()
                if cur:
                    parts.append(cur)
                span = (min(e0, end) - max(s0, start)) / max(len(parts), 1)
                for i, ptext in enumerate(parts):
                    push(max(s0, start) + i * span,
                         max(s0, start) + (i + 1) * span, ptext)
    cues.sort(key=lambda c: c["s"])
    # never let two strips share the screen — the later one wins the overlap
    for i in range(1, len(cues)):
        if cues[i]["s"] < cues[i - 1]["e"]:
            cues[i - 1]["e"] = round(max(cues[i]["s"] - 0.02,
                                         cues[i - 1]["s"] + 0.2), 3)
    return [c for c in cues if c["e"] > c["s"]]


# -- image pieces -------------------------------------------------------------

def _caption_img(text: str, out_w: int, out_h: int):
    """One caption strip: ink plate, cream type, ≤2 lines wrapped by
    measure — the reel card's palette at caption scale."""
    from PIL import Image, ImageDraw, ImageFont

    from slate.fonts import find

    fs = max(18, round(out_h * 0.040))
    font = ImageFont.truetype(find(None), size=fs)
    pad = round(fs * 0.55)
    maxw = round(out_w * 0.86)
    d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    lines, cur = [], ""
    for tok in str(text).split():
        t2 = (cur + " " + tok).strip()
        if d0.textlength(t2, font=font) > maxw - 2 * pad and cur:
            lines.append(cur)
            cur = tok
        else:
            cur = t2
    if cur:
        lines.append(cur)
    lines = lines[:2] if len(lines) <= 2 else [lines[0], lines[1] + "…"]
    lw = max(round(d0.textlength(ln, font=font)) for ln in lines)
    lh = fs + round(fs * 0.28)
    W, H = lw + 2 * pad, lh * len(lines) + 2 * pad - round(fs * 0.2)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=round(fs * 0.35),
                        fill=(35, 38, 29, 216))
    y = pad - round(fs * 0.12)
    for ln in lines:
        d.text(((W - d.textlength(ln, font=font)) / 2, y), ln,
               font=font, fill=(243, 240, 231, 255))
        y += lh
    return img


def _lowerthird_img(brand: dict, line1: str, line2: str, w: int, h: int):
    """Slate's lower-third, held at full presence, in the brand's colors.

    Slate sizes type off frame HEIGHT (broadcast assumption); on a vertical
    frame that explodes, so scale renormalizes to the short edge. Vertical
    frames carry the third at the top — the face lives upper-middle in a
    9:16 crop and the captions own the bottom."""
    from slate.lowerthird import LowerThird, Renderer

    p = LowerThird.from_dict({
        "line1": line1 or brand.get("station") or "",
        "line2": line2 if line2 is not None else brand.get("line2", ""),
        "style": brand.get("style", "bar"), "anim": "none",
        "width": w, "height": h,
        "accent": brand.get("accent", "#3A9E8E"),
        "plate_color": brand.get("plate", "#14141A"),
        "scale": min(w, h) / h,
        # widescreen keeps the broadcast bottom-left; square and vertical
        # carry it top-left — captions own the bottom there
        "y": 0.80 if w > h else 0.15,
    })
    return Renderer(p).hold_frame()


# -- the render ---------------------------------------------------------------

def _aspect_filter(ratio: str, offset: float) -> str:
    """Trimmed stream → framed stream. offset ∈ [-1, 1] slides a crop
    between its leftmost (-1) and rightmost (+1) legal position."""
    tw, th = RATIOS[ratio]
    off = max(-1.0, min(1.0, float(offset or 0.0)))
    if ratio == "16x9":
        return (f"scale={tw}:{th}:force_original_aspect_ratio=decrease,"
                f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2")
    if ratio == "1x1":
        crop = "crop='min(iw,ih)':'min(iw,ih)'" \
               f":'(iw-out_w)/2*(1+({off}))':'(ih-out_h)/2'"
    else:  # 9x16
        crop = "crop='min(iw,ih*9/16)':ih" \
               f":'(iw-out_w)/2*(1+({off}))':0"
    return f"{crop},scale={tw}:{th}"


def render_clip(src: str, start: float, end: float, out_stem: str,
                ratio: str = "16x9", cues: Optional[List[dict]] = None,
                brand: Optional[dict] = None, lt_line1: str = "",
                lt_line2: Optional[str] = None, offset: float = 0.0,
                preset: str = "h264",
                progress: Optional[Callable[[float, str], None]] = None,
                cancelled: Optional[Callable[[], bool]] = None) -> dict:
    """One candidate → one framed, captioned, branded cut on disk."""
    if ratio not in RATIOS:
        raise ValueError(f"unknown ratio {ratio!r} — one of {list(RATIOS)}")
    a, b = float(start), float(end)
    if b - a <= 0.2:
        raise ValueError("that span is too short to cut")
    info = probe(src)
    has_audio = info.audio_streams > 0
    spec = resolve_preset(preset)
    tw, th = RATIOS[ratio]
    out = f"{out_stem}.{ratio}.{spec['container']}"
    brand = brand or {}
    lt_secs = float(brand.get("lt_seconds", 4.5) or 0)
    want_lt = lt_secs > 0.2 and bool(lt_line1 or brand.get("station"))
    cues = list(cues or [])[:80]   # a graph, not a novel

    with tempfile.TemporaryDirectory(prefix="pub-clip-") as td:
        args = ["-i", src]
        n_extra = 0
        lt_idx = cap_base = None
        if want_lt:
            p = str(Path(td) / "lt.png")
            _lowerthird_img(brand, lt_line1, lt_line2, tw, th).save(p)
            hold = min(lt_secs, b - a)
            args += ["-loop", "1", "-t", f"{hold:.3f}", "-i", p]
            n_extra += 1
            lt_idx = n_extra
        if cues:
            cap_base = n_extra + 1
            for k, c in enumerate(cues):
                p = str(Path(td) / f"cap{k}.png")
                _caption_img(c["text"], tw, th).save(p)
                args += ["-loop", "1", "-t", f"{min(c['e'], b - a):.3f}",
                         "-i", p]
                n_extra += 1

        parts = [f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,"
                 f"{_aspect_filter(ratio, offset)},setsar=1,fps=30,"
                 f"format=yuv420p[b0]"]
        cur = "b0"
        if want_lt:
            hold = min(lt_secs, b - a)
            parts.append(f"[{lt_idx}:v]format=rgba,"
                         f"fade=t=out:st={max(0.0, hold - 0.4):.3f}:d=0.4:"
                         f"alpha=1[lt]")
            parts.append(f"[{cur}][lt]overlay=0:0:eof_action=pass[b1]")
            cur = "b1"
        for k, c in enumerate(cues):
            # the widescreen third's plate bottoms out ~20% up the frame;
            # the classic caption margin passes beneath it untouched
            margin = round(th * (0.055 if ratio == "16x9" else 0.10))
            parts.append(
                f"[{cap_base + k}:v]format=rgba[t{k}]")
            parts.append(
                f"[{cur}][t{k}]overlay=x=(W-w)/2:y=H-h-{margin}:"
                f"eof_action=pass:enable='between(t,{c['s']:.3f},{c['e']:.3f})'"
                f"[b{2 + k}]")
            cur = f"b{2 + k}"
        maps = ["-map", f"[{cur}]"]
        if has_audio:
            parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},"
                         f"asetpts=PTS-STARTPTS[a]")
            maps += ["-map", "[a]"]
        args += ["-filter_complex", ";".join(parts)] + maps
        args += ffrun.encoder_args(spec, audio=has_audio) + [out]
        ffrun.run(args, duration=b - a, progress=progress, cancelled=cancelled)
    return {"out": out, "ratio": ratio, "duration": round(b - a, 2),
            "captions": len(cues), "lower_third": bool(want_lt),
            "encoder": spec["codec"]}


def thumbnail(src: str, t: float, title: str, brand: Optional[dict],
              out_png: str, ratio: str = "16x9") -> dict:
    """One thumbnail candidate: the frame at t, framed to ratio, title in
    the station's type on the ink plate."""
    import subprocess

    from PIL import Image

    from czcore.tools import ffmpeg_path

    tw, th = (1280, 720) if ratio == "16x9" else (
        (1080, 1080) if ratio == "1x1" else (720, 1280))
    with tempfile.TemporaryDirectory(prefix="pub-thumb-") as td:
        raw = str(Path(td) / "frame.png")
        subprocess.run([ffmpeg_path(), "-y", "-v", "error",
                        "-ss", f"{max(0.0, float(t)):.3f}", "-i", src,
                        "-frames:v", "1", raw], check=True, timeout=60)
        try:
            pil = Image.open(raw).convert("RGBA")
        except OSError as e:
            raise RuntimeError("couldn't read a frame there — past the end, "
                               "or the file has no video") from e
        scale = max(tw / pil.width, th / pil.height)
        pil = pil.resize((round(pil.width * scale), round(pil.height * scale)),
                         Image.LANCZOS)
        x0, y0 = (pil.width - tw) // 2, (pil.height - th) // 2
        pil = pil.crop((x0, y0, x0 + tw, y0 + th))
        if title:
            strip = _caption_img(title, tw, th)
            big = strip.resize((round(strip.width * 1.25),
                                round(strip.height * 1.25)), Image.LANCZOS)
            pil.alpha_composite(big, ((tw - big.width) // 2,
                                      th - big.height - round(th * 0.07)))
        pil.convert("RGB").save(out_png, "PNG")
    return {"out": out_png, "ratio": ratio, "t": round(float(t), 2)}
