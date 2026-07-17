"""Cut the reel — one ffmpeg graph, hard cuts, honest about it.

Trims and concats happen in a single filter graph so audio stays locked to
picture. Cuts are hard cuts by design: a highlight reel that dissolves
between a vote and an argument is editorializing. Finish in Resolve via the
selects EDL if you want transitions — the EDL is the same cut list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from czcore import ffrun
from czcore.media import probe, resolve_preset


def render_reel(src: str, ranges: List[dict], out_path: str,
                preset: str = "h264",
                progress: Optional[Callable[[float, str], None]] = None,
                cancelled: Optional[Callable[[], bool]] = None) -> dict:
    """ranges: [{start, end}] seconds, already in story order."""
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

    parts, maps = [], []
    for k, r in enumerate(ranges):
        a, b = float(r["start"]), float(r["end"])
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},"
                     f"setpts=PTS-STARTPTS[v{k}]")
        if has_audio:
            parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},"
                         f"asetpts=PTS-STARTPTS[a{k}]")
        maps.append(f"[v{k}]" + (f"[a{k}]" if has_audio else ""))
    n = len(ranges)
    parts.append("".join(maps) + f"concat=n={n}:v=1:a={1 if has_audio else 0}"
                 + ("[v][a]" if has_audio else "[v]"))
    graph = ";".join(parts)

    args = ["-i", src, "-filter_complex", graph, "-map", "[v]"]
    if has_audio:
        args += ["-map", "[a]"]
    args += ffrun.encoder_args(spec, audio=has_audio)
    args += [out]
    total = sum(float(r["end"]) - float(r["start"]) for r in ranges)
    ffrun.run(args, duration=total, progress=progress, cancelled=cancelled)
    return {"out": out, "duration": round(total, 2), "clips": n,
            "encoder": spec["codec"], "hardware": spec["hardware"]}


def stitch_files(files: List[str], out_path: str, preset: str = "h264",
                 progress: Optional[Callable[[float, str], None]] = None,
                 cancelled: Optional[Callable[[], bool]] = None) -> dict:
    """Concat whole files into one reel — the section-download path, where
    each kept moment already arrived as its own clip."""
    if not files:
        raise ValueError("no clips to stitch")
    infos = [probe(f) for f in files]
    has_audio = all(i.audio_streams > 0 for i in infos)
    spec = resolve_preset(preset)
    out = str(out_path)
    if not out.endswith("." + spec["container"]):
        out += "." + spec["container"]
    args = []
    for f in files:
        args += ["-i", f]
    n = len(files)
    parts = []
    for k in range(n):
        parts.append(f"[{k}:v]setpts=PTS-STARTPTS,fps=30[v{k}]")
        if has_audio:
            parts.append(f"[{k}:a]asetpts=PTS-STARTPTS[a{k}]")
    join = "".join(f"[v{k}]" + (f"[a{k}]" if has_audio else "") for k in range(n))
    parts.append(join + f"concat=n={n}:v=1:a={1 if has_audio else 0}"
                 + ("[v][a]" if has_audio else "[v]"))
    args += ["-filter_complex", ";".join(parts), "-map", "[v]"]
    if has_audio:
        args += ["-map", "[a]"]
    args += ffrun.encoder_args(spec, audio=has_audio)
    args += [out]
    total = sum(i.duration or 0 for i in infos)
    ffrun.run(args, duration=total or None, progress=progress, cancelled=cancelled)
    return {"out": out, "duration": round(total, 2), "clips": n,
            "encoder": spec["codec"], "hardware": spec["hardware"]}
