"""Cut the reel — one ffmpeg graph, hard cuts, honest about it.

Trims and concats happen in a single filter graph so audio stays locked to
picture. Cuts are hard cuts by design: a highlight reel that dissolves
between a vote and an argument is editorializing. Finish in Resolve via the
selects EDL if you want transitions — the EDL is the same cut list.

Title cards are the one adornment: an optional ink card before each moment
naming it and its place in the meeting — context, not decoration. They
render through Pillow (Slate's font discovery) and ride the same concat
graph, so audio stays locked and the cut list stays one list.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, List, Optional

from czcore import ffrun
from czcore.media import probe, resolve_preset

CARD_SECONDS = 1.6


def _fmt_t(t: float) -> str:
    t = int(t)
    return (f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600
            else f"{t // 60}:{t % 60:02d}")


def _card_png(path: str, w: int, h: int, title: str, label: str,
              tstr: str) -> None:
    """One ink title card: the meeting small, the moment big, its time in
    the brief's green. Flat design, rendered at output size."""
    from PIL import Image, ImageDraw, ImageFont

    from slate.fonts import find

    img = Image.new("RGB", (w, h), (35, 38, 29))          # the suite's ink
    d = ImageDraw.Draw(img)
    fp = find(None)
    f_small = ImageFont.truetype(fp, size=max(16, round(h * 0.032)))
    f_big = ImageFont.truetype(fp, size=max(24, round(h * 0.062)))
    f_pill = ImageFont.truetype(fp, size=max(15, round(h * 0.030)))
    mx, my = round(w * 0.08), round(h * 0.20)
    d.text((mx, my), (title or "")[:80].upper(),
           font=f_small, fill=(185, 189, 178))
    d.rectangle((mx, my + round(h * 0.075), mx + round(w * 0.10),
                 my + round(h * 0.082)), fill=(34, 197, 94))
    # the moment's words, wrapped by measure
    words, lines, cur = (label or "").split(), [], ""
    for word in words:
        t2 = (cur + " " + word).strip()
        if d.textlength(t2, font=f_big) > w * 0.84 and cur:
            lines.append(cur)
            cur = word
        else:
            cur = t2
        if len(lines) == 3:
            break
    if cur and len(lines) < 4:
        lines.append(cur)
    y = my + round(h * 0.14)
    for ln in lines[:3]:
        d.text((mx, y), ln, font=f_big, fill=(243, 240, 231))
        y += round(h * 0.085)
    pill = f"  {tstr}  "
    pw = d.textlength(pill, font=f_pill)
    py = y + round(h * 0.05)
    d.rounded_rectangle((mx, py, mx + pw, py + round(h * 0.052)),
                        radius=round(h * 0.012), fill=(30, 127, 99))
    d.text((mx, py + round(h * 0.009)), pill, font=f_pill,
           fill=(243, 240, 231))
    img.save(path)


def _render_cards(cards: List[dict], w: int, h: int, title: str,
                  tmpdir: str) -> List[str]:
    """One PNG per moment; even dimensions (encoders insist)."""
    w, h = (w // 2) * 2 or 1920, (h // 2) * 2 or 1080
    paths = []
    for k, c in enumerate(cards):
        p = str(Path(tmpdir) / f"card{k}.png")
        _card_png(p, w, h, title, str(c.get("label", "")),
                  _fmt_t(float(c.get("t", 0))))
        paths.append(p)
    return paths


_ANORM = ("aresample=48000,"
          "aformat=sample_fmts=fltp:channel_layouts=stereo")


def render_reel(src: str, ranges: List[dict], out_path: str,
                preset: str = "h264",
                progress: Optional[Callable[[float, str], None]] = None,
                cancelled: Optional[Callable[[], bool]] = None,
                cards: Optional[List[dict]] = None,
                title: str = "") -> dict:
    """ranges: [{start, end}] seconds, already in story order.
    cards: optional [{label, t}] aligned with ranges — an ink title card
    lands before each moment, in the same graph, audio still locked."""
    if not ranges:
        raise ValueError("the reel is empty — mark at least one moment")
    info = probe(src)
    has_audio = info.audio_streams > 0
    spec = resolve_preset(preset)
    # out_path is a stem — append, never with_suffix(): "meeting.reel" would
    # lose its .reel and the output would be the source's own name
    out = str(out_path)
    if not out.endswith("." + spec["container"]):
        out += "." + spec["container"]
    if Path(out).resolve() == Path(src).resolve():
        raise ValueError("output would overwrite the source clip")
    use_cards = bool(cards) and info.video is not None
    n = len(ranges)

    with tempfile.TemporaryDirectory(prefix="hl-cards-") as td:
        args = ["-i", src]
        pngs = []
        if use_cards:
            fps = round(info.video.fps or 30, 3)
            pngs = _render_cards(cards[:n], info.video.width,
                                 info.video.height, title, td)
            for p in pngs:
                args += ["-loop", "1", "-t", f"{CARD_SECONDS}", "-i", p]
            if has_audio:
                for _ in pngs:
                    args += ["-f", "lavfi", "-t", f"{CARD_SECONDS}", "-i",
                             "anullsrc=channel_layout=stereo:sample_rate=48000"]
        parts, maps = [], []
        for k, r in enumerate(ranges):
            a, b = float(r["start"]), float(r["end"])
            vnorm = ",setsar=1,format=yuv420p" if use_cards else ""
            anorm = "," + _ANORM if use_cards else ""
            parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},"
                         f"setpts=PTS-STARTPTS{vnorm}[v{k}]")
            if has_audio:
                parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},"
                             f"asetpts=PTS-STARTPTS{anorm}[a{k}]")
            if use_cards:
                parts.append(f"[{1 + k}:v]fps={fps},setpts=PTS-STARTPTS,"
                             f"setsar=1,format=yuv420p[c{k}]")
                if has_audio:
                    parts.append(f"[{1 + n + k}:a]asetpts=PTS-STARTPTS,"
                                 f"{_ANORM}[s{k}]")
                maps.append(f"[c{k}]" + (f"[s{k}]" if has_audio else ""))
            maps.append(f"[v{k}]" + (f"[a{k}]" if has_audio else ""))
        segs = n * 2 if use_cards else n
        parts.append("".join(maps)
                     + f"concat=n={segs}:v=1:a={1 if has_audio else 0}"
                     + ("[v][a]" if has_audio else "[v]"))
        args += ["-filter_complex", ";".join(parts), "-map", "[v]"]
        if has_audio:
            args += ["-map", "[a]"]
        args += ffrun.encoder_args(spec, audio=has_audio)
        args += [out]
        total = sum(float(r["end"]) - float(r["start"]) for r in ranges) \
            + (len(pngs) * CARD_SECONDS if use_cards else 0)
        ffrun.run(args, duration=total, progress=progress, cancelled=cancelled)
    return {"out": out, "duration": round(total, 2), "clips": n,
            "cards": len(pngs) if use_cards else 0,
            "encoder": spec["codec"], "hardware": spec["hardware"]}


def stitch_files(files: List[str], out_path: str, preset: str = "h264",
                 progress: Optional[Callable[[float, str], None]] = None,
                 cancelled: Optional[Callable[[], bool]] = None,
                 cards: Optional[List[dict]] = None,
                 title: str = "") -> dict:
    """Concat whole files into one reel — the section-download path, where
    each kept moment already arrived as its own clip. cards as in
    render_reel, aligned with files."""
    if not files:
        raise ValueError("no clips to stitch")
    infos = [probe(f) for f in files]
    has_audio = all(i.audio_streams > 0 for i in infos)
    spec = resolve_preset(preset)
    out = str(out_path)
    if not out.endswith("." + spec["container"]):
        out += "." + spec["container"]
    n = len(files)
    v0 = next((i.video for i in infos if i.video), None)
    use_cards = bool(cards) and v0 is not None

    with tempfile.TemporaryDirectory(prefix="hl-cards-") as td:
        args = []
        for f in files:
            args += ["-i", f]
        pngs = []
        if use_cards:
            pngs = _render_cards(cards[:n], v0.width, v0.height, title, td)
            for p in pngs:
                args += ["-loop", "1", "-t", f"{CARD_SECONDS}", "-i", p]
            if has_audio:
                for _ in pngs:
                    args += ["-f", "lavfi", "-t", f"{CARD_SECONDS}", "-i",
                             "anullsrc=channel_layout=stereo:sample_rate=48000"]
        parts, maps = [], []
        vnorm = ",setsar=1,format=yuv420p" if use_cards else ""
        for k in range(n):
            parts.append(f"[{k}:v]setpts=PTS-STARTPTS,fps=30{vnorm}[v{k}]")
            if has_audio:
                parts.append(f"[{k}:a]asetpts=PTS-STARTPTS"
                             + ("," + _ANORM if use_cards else "") + f"[a{k}]")
            if use_cards:
                # card k sits at input n+k; its silence at input 2n+k —
                # the clips' own dimensions drive the card size
                parts.append(f"[{n + k}:v]fps=30,setpts=PTS-STARTPTS,"
                             f"setsar=1,format=yuv420p[c{k}]")
                if has_audio:
                    parts.append(f"[{2 * n + k}:a]asetpts=PTS-STARTPTS,"
                                 f"{_ANORM}[s{k}]")
                maps.append(f"[c{k}]" + (f"[s{k}]" if has_audio else ""))
            maps.append(f"[v{k}]" + (f"[a{k}]" if has_audio else ""))
        segs = n * 2 if use_cards else n
        parts.append("".join(maps)
                     + f"concat=n={segs}:v=1:a={1 if has_audio else 0}"
                     + ("[v][a]" if has_audio else "[v]"))
        args += ["-filter_complex", ";".join(parts), "-map", "[v]"]
        if has_audio:
            args += ["-map", "[a]"]
        args += ffrun.encoder_args(spec, audio=has_audio)
        args += [out]
        total = sum(i.duration or 0 for i in infos) \
            + (len(pngs) * CARD_SECONDS if use_cards else 0)
        ffrun.run(args, duration=total or None, progress=progress,
                  cancelled=cancelled)
    return {"out": out, "duration": round(total, 2), "clips": n,
            "cards": len(pngs) if use_cards else 0,
            "encoder": spec["codec"], "hardware": spec["hardware"]}
