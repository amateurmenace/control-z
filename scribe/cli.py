"""scribe-cli — transcribe / export. The editor UI builds on exactly these calls."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__
from .transcript import Transcript


def _extract_wav(path: str, out_dir: Path) -> str:
    """Media -> 16k mono wav for ASR/diarization (bundled-ffmpeg in packages)."""
    from czcore.tools import ToolNotFound, ffmpeg_path

    wav = out_dir / (Path(path).stem + ".16k.wav")
    try:
        exe = ffmpeg_path()
    except ToolNotFound:
        exe = None  # PyAV fallback below keeps dev setups working
    if exe:
        subprocess.run([exe, "-y", "-v", "quiet", "-i", path, "-ac", "1",
                        "-ar", "16000", str(wav)], check=True)
        return str(wav)
    # PyAV fallback so dev setups without ffmpeg still work
    import av
    import numpy as np

    with av.open(path) as inp:
        astream = inp.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        out = av.open(str(wav), "w")
        ostream = out.add_stream("pcm_s16le", rate=16000, layout="mono")
        for frame in inp.decode(astream):
            for rf in resampler.resample(frame):
                for pkt in ostream.encode(rf):
                    out.mux(pkt)
        for pkt in ostream.encode():
            out.mux(pkt)
        out.close()
    return str(wav)


def cmd_transcribe(args) -> int:
    from czcore.media import probe

    from .exports import to_marker_edl, to_srt, to_vtt
    from .transcribe import transcribe

    say = print if not args.quiet else (lambda *a, **k: None)
    rc = 0
    for src in args.inputs:
        p = Path(src).expanduser()
        if not p.is_file():
            print(f"skip (not a file): {p}")
            rc = 2
            continue
        say(f"\nScribe — {p.name}")
        info = probe(str(p))
        fps = info.video.fps if info.video else 24.0
        with tempfile.TemporaryDirectory(prefix="scribe-") as td:
            wav = _extract_wav(str(p), Path(td))
            t = transcribe(wav, model=args.model, language=args.language,
                           progress=(lambda m: say(f"  {m}", end="\r")) if not args.quiet else None)
            say("")
            t.source = str(p.resolve())
            if args.diarize:
                from . import diarize as dz
                if dz.available():
                    dz.diarize(t, wav, num_speakers=args.speakers,
                               progress=lambda m: say(f"  {m}"))
                    say(f"  speakers: {', '.join(t.speakers)}")
                else:
                    say("  ! " + dz.install_hint().splitlines()[0])
                    say("    (continuing without speakers — see docs)")
        out_dir = Path(args.output) if args.output else p.parent
        stem = p.stem
        (out_dir / f"{stem}.scribe.json").write_text(t.to_json())
        (out_dir / f"{stem}.srt").write_text(to_srt(t, args.captions))
        (out_dir / f"{stem}.vtt").write_text(to_vtt(t, args.captions))
        (out_dir / f"{stem}.txt").write_text(t.full_text() + "\n")
        start_tc = info.timecode or "01:00:00:00"
        (out_dir / f"{stem}.markers.edl").write_text(
            to_marker_edl(t, fps, record_start_tc=start_tc))
        say(f"  {len(t.segments)} segments, language {t.language}")
        say(f"  → {stem}.scribe.json / .srt / .vtt / .txt / .markers.edl in {out_dir}")
        say("  Resolve: import .srt onto a subtitle track; Timeline → Import → "
            "Timeline Markers From EDL for the marker pass.")
    return rc


def cmd_selects(args) -> int:
    """selects JSON: [{"start": 12.5, "end": 31.0, "label": "good take"}]"""
    from czcore.media import probe

    from .exports import Select, to_selects_edl

    t = Transcript.from_json(Path(args.transcript).read_text())
    src = Path(t.source)
    info = probe(str(src)) if src.exists() else None
    fps = info.video.fps if info and info.video else args.fps
    sels = [Select(**{k: s[k] for k in ("start", "end", "label") if k in s})
            for s in json.loads(Path(args.selects).read_text())]
    edl = to_selects_edl(
        sels, fps, reel=src.stem[:8].upper() or "AX",
        source_start_tc=(info.timecode if info and info.timecode else "00:00:00:00"),
        handles=args.handles, clip_name=src.name)
    out = Path(args.output) if args.output else src.with_suffix(".selects.edl")
    out.write_text(edl)
    print(f"{len(sels)} selects → {out}")
    print("Resolve: File → Import → Timeline → EDL, then relink to the source clip.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="scribe-cli",
        description="Scribe writes it all down — local transcription and paper "
                    "edits for free Resolve. Part of control-z (https://control-z.org).")
    p.add_argument("--version", action="version", version=f"scribe {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("transcribe", help="media → transcript + captions + markers")
    pt.add_argument("inputs", nargs="+")
    pt.add_argument("--model", default="large-v3-turbo",
                    help="whisper size: tiny/base/small/medium/large-v3-turbo")
    pt.add_argument("--language", default=None)
    pt.add_argument("--diarize", action="store_true", help="label speakers")
    pt.add_argument("--speakers", type=int, default=-1,
                    help="speaker count if known (better clustering)")
    pt.add_argument("--captions", choices=["broadcast", "standard", "social"],
                    default="standard")
    pt.add_argument("-o", "--output", help="output dir (default: beside source)")
    pt.add_argument("-q", "--quiet", action="store_true")
    pt.set_defaults(fn=cmd_transcribe)

    ps = sub.add_parser("selects", help="pull-list JSON → CMX3600 EDL")
    ps.add_argument("transcript", help="*.scribe.json")
    ps.add_argument("selects", help="selects JSON")
    ps.add_argument("--handles", type=float, default=0.5, help="seconds of padding")
    ps.add_argument("--fps", type=float, default=24.0, help="fallback if source missing")
    ps.add_argument("-o", "--output")
    ps.set_defaults(fn=cmd_selects)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
