"""clear-cli — process / roomtone. WAV/AIFF in, WAV out (video remux is v0.2)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _read(path):
    import soundfile as sf

    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    return audio, sr


def _write(path, audio, sr):
    import soundfile as sf

    sf.write(path, audio, sr)


def cmd_process(args) -> int:
    import numpy as np

    from .dsp import declick, deess, dehum, detect_hum
    from .loudness import TARGETS, normalize

    say = print if not args.quiet else (lambda *a, **k: None)
    audio, sr = _read(args.input)
    original = audio.copy()
    say(f"Clear — {Path(args.input).name} ({sr} Hz, {audio.shape[1]} ch, "
        f"{len(audio)/sr:.1f}s)")

    if args.dehum != "off":
        base = float(args.dehum) if args.dehum not in ("auto",) else \
            detect_hum(audio, sr)
        if base:
            audio = dehum(audio, sr, base)
            say(f"  de-hum: notched {base:.0f} Hz + harmonics")
        else:
            say("  de-hum: no mains hum detected (skipped)")

    if args.declick:
        audio, n = declick(audio, sr)
        say(f"  de-click: repaired {n} samples" if n else "  de-click: clean")

    if args.isolate > 0:
        from . import isolate as iso
        if iso.available():
            say(f"  voice isolation: DeepFilterNet3, mix-back "
                f"{1 - args.isolate:.0%} room kept")
            audio = iso.isolate(audio, sr, mix_back=1.0 - args.isolate)
        else:
            say("  ! " + iso.install_hint().splitlines()[0])

    if args.deess > 0:
        audio = deess(audio, sr, amount=args.deess)
        say(f"  de-ess: {args.deess:.0%}")

    report = None
    if args.loudness:
        target = TARGETS.get(args.loudness)
        target = float(args.loudness) if target is None else target
        audio, report = normalize(audio, sr, target)
        say(f"  loudness: {report['measured_lufs']} LUFS → {target} "
            f"(gain {report['applied_db']:+.1f} dB"
            + (", PEAK-LIMITED — needs dynamics work" if report["limited_by_peak"] else "")
            + ")")

    out = args.output or str(Path(args.input).with_suffix(".clear.wav"))
    _write(out, audio, sr)
    say(f"  → {out}")

    if args.residual:
        n = min(len(original), len(audio))
        _write(args.residual, original[:n] - audio[:n], sr)
        say(f"  → residual (what was removed): {args.residual} — LISTEN to it: "
            "words in the residual = over-processing.")
    return 0


def cmd_roomtone(args) -> int:
    from .roomtone import find_quietest, generate, profile

    audio, sr = _read(args.input)
    if args.from_time is not None:
        s = int(args.from_time * sr)
        e = s + int(args.profile_len * sr)
    else:
        s, e = find_quietest(audio, sr, args.profile_len)
    print(f"Clear roomtone — profiling {s/sr:.2f}s–{e/sr:.2f}s of "
          f"{Path(args.input).name}")
    prof = profile(audio[s:e], sr)
    tone = generate(prof, args.len)
    out = args.output or str(Path(args.input).with_suffix(".roomtone.wav"))
    _write(out, tone, sr)
    print(f"  {args.len:.0f}s of matching tone → {out} (loop-safe tail)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="clear-cli",
        description="Clear rescues the voice — dialogue repair for free Resolve "
                    "workflows. Part of control-z (https://control-z.org).")
    p.add_argument("--version", action="version", version=f"clear {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("process", help="de-hum / de-click / isolate / de-ess / loudness")
    pp.add_argument("input")
    pp.add_argument("--dehum", default="auto", help="auto | off | 50 | 60")
    pp.add_argument("--no-declick", dest="declick", action="store_false")
    pp.add_argument("--isolate", type=float, default=0.0,
                    help="voice isolation amount 0..1 (0 = off, 0.65 typical)")
    pp.add_argument("--deess", type=float, default=0.0, help="0..1")
    pp.add_argument("--loudness", default=None,
                    help="broadcast(-24) | podcast(-16) | streaming(-14) | <LUFS>")
    pp.add_argument("--residual", help="write removed audio here (hear your damage)")
    pp.add_argument("-o", "--output")
    pp.add_argument("-q", "--quiet", action="store_true")
    pp.set_defaults(fn=cmd_process)

    pr = sub.add_parser("roomtone", help="profile a region, synthesize matching tone")
    pr.add_argument("input")
    pr.add_argument("--from", dest="from_time", type=float, default=None,
                    help="profile start seconds (default: auto-find quietest)")
    pr.add_argument("--profile-len", type=float, default=2.0)
    pr.add_argument("--len", type=float, default=30.0, help="output seconds")
    pr.add_argument("-o", "--output")
    pr.set_defaults(fn=cmd_roomtone)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
