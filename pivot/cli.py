"""pivot-cli — analyze / render / auto. Every UI control mirrors a flag here."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__


def _sidecar_path(src: str) -> Path:
    return Path(src).with_suffix(".pivot.json")


def _out_path(src: str, aspect: str, ext: str) -> Path:
    tag = aspect.replace(":", "x")
    p = Path(src)
    return p.with_name(f"{p.stem}.pivot-{tag}{ext}")


def _print_report(analysis) -> None:
    a0 = next(iter(analysis.aspects.values()))
    print(f"\n{analysis.source}")
    print(f"  {analysis.width}x{analysis.height} @ {analysis.fps:.3f} fps, "
          f"{analysis.n_frames} frames, {len(analysis.shots)} shots, preset={analysis.preset}")
    print(f"  aspect {a0.aspect}: crop {a0.crop_w}x{a0.crop_h} (axis {a0.axis}), "
          f"{a0.moves} camera moves")
    for row in analysis.subjects:
        subj = ("center-fallback" if row["fallback_center"]
                else f"{row.get('subject_source', 'face')} track {row['subject_track']} "
                     f"({row['detections']} det)")
        print(f"    shot {row['shot']:>3}  [{row['start']:>6}–{row['end']:>6})  "
              f"{row['mode']:<6} moves={row['moves']}  {subj}")


def cmd_analyze(args) -> int:
    from .analyze import analyze

    analysis = analyze(
        args.input, aspects=args.aspect, preset=args.preset,
        det_step=args.det_step,
        progress=(lambda n: print(f"  …{n} frames", end="\r", flush=True)),
    )
    out = Path(args.output) if args.output else _sidecar_path(args.input)
    out.write_text(analysis.to_json())
    _print_report(analysis)
    print(f"\n  sidecar → {out}")
    return 0


def cmd_render(args) -> int:
    from .analyze import Analysis
    from .render import render

    sidecar = Path(args.path) if args.path else _sidecar_path(args.input)
    analysis = Analysis.from_json(sidecar.read_text())
    if analysis.source != args.input:
        analysis.source = args.input  # allow moved files
    ext = ".mov" if args.codec == "prores" else ".mp4"
    rc = 0
    for aspect in args.aspect:
        if aspect not in analysis.aspects:
            print(f"aspect {aspect} not in sidecar (has: {list(analysis.aspects)})")
            rc = 2
            continue
        out = args.output or str(_out_path(args.input, aspect, ext))
        out_size = None
        if args.out_size:
            w, h = args.out_size.lower().split("x")
            out_size = (int(w), int(h))
        try:
            report = render(analysis, aspect, out, codec=args.codec, out_size=out_size,
                            audio=not args.no_audio, enhance=args.enhance,
                            enhance_model=args.enhance_model,
                            progress=(lambda n: print(f"  …{n} frames", end="\r", flush=True)))
        except RuntimeError as e:
            # h264/hevc have no software fallback by design (specs/09 §3); on
            # an FFmpeg without VideoToolbox that is a sentence and a nonzero
            # exit, not a traceback — and the remaining aspects still run.
            print(f"  {aspect}: {e} — prores works on every build (--codec prores).")
            rc = 2
            continue
        print(f"  {aspect}: {report['frames']} frames → {report['out']} "
              f"({report['size'][0]}x{report['size'][1]}, audio: {report['audio']})")
        if report["punch_in"] > 1.001:
            print(f"    punch-in {report['punch_in']}x past native detail — "
                  f"enhance: {report['enhance']}"
                  + ("" if report["enhance"] not in ("off", "lanczos")
                     else " (no synthesis — honest resampling; Rise model lands in task 9)"))
    return rc


def cmd_export_fusion(args) -> int:
    from czcore.exports.fusion_setting import animated_crop_setting

    from .analyze import Analysis
    from .aspect import CropGeometry, rect_for_center

    sidecar = Path(args.path) if args.path else _sidecar_path(args.input)
    analysis = Analysis.from_json(sidecar.read_text())
    rc = 0
    for aspect in args.aspect:
        if aspect not in analysis.aspects:
            print(f"aspect {aspect} not in sidecar (has: {list(analysis.aspects)})")
            rc = 2
            continue
        s = analysis.aspects[aspect]
        geom = CropGeometry(analysis.width, analysis.height, s.crop_w, s.crop_h, s.axis)
        rects = [rect_for_center(geom, c) for c in s.centers]
        text = animated_crop_setting(
            rects, analysis.width, analysis.height,
            comment=f"control-z Pivot — {Path(analysis.source).name} {aspect}",
        )
        out = Path(args.output) if args.output else \
            _out_path(args.input, aspect, ".setting")
        out.write_text(text)
        print(f"  {aspect}: {len(rects)} keyframes → {out}")
        print("    paste onto the clip in the Fusion page (free Resolve), set the "
              "timeline to the crop size or add a Transform to fit.")
    return rc


def cmd_auto(args) -> int:
    rc = cmd_analyze(args)
    if rc:
        return rc
    args.path = None
    args.output = None
    return cmd_render(args)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="pivot-cli",
        description="Pivot follows the subject — smart reframe for free Resolve workflows. "
                    "Part of control-z (https://control-z.org).",
    )
    p.add_argument("--version", action="version", version=f"pivot {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("input")
    common.add_argument("--aspect", nargs="+", default=["9:16"],
                        help="target aspect(s), e.g. 9:16 1:1 4:5")

    pa = sub.add_parser("analyze", parents=[common], help="detect, track, solve → sidecar")
    pa.add_argument("--preset", choices=["calm", "standard", "attentive"],
                    default="standard")
    pa.add_argument("--det-step", type=int, default=2)
    pa.add_argument("-o", "--output")
    pa.set_defaults(fn=cmd_analyze)

    pr = sub.add_parser("render", parents=[common], help="render from a sidecar")
    pr.add_argument("--path", help="sidecar json (default: <input>.pivot.json)")
    pr.add_argument("--codec", choices=["h264", "hevc", "prores"], default="h264")
    pr.add_argument("--out-size", help="e.g. 1080x1920 (default: native crop, no upscale)")
    pr.add_argument("--no-audio", action="store_true")
    pr.add_argument("--enhance", action="store_true",
                    help="run punch-ins through the Rise engine")
    pr.add_argument("--enhance-model", default="auto")
    pr.add_argument("-o", "--output")
    pr.set_defaults(fn=cmd_render)

    pf = sub.add_parser("export-fusion", parents=[common],
                        help="keyframed Crop .setting for free Resolve's Fusion page")
    pf.add_argument("--path", help="sidecar json (default: <input>.pivot.json)")
    pf.add_argument("-o", "--output")
    pf.set_defaults(fn=cmd_export_fusion)

    au = sub.add_parser("auto", parents=[common], help="analyze + render, defaults")
    au.add_argument("--preset", choices=["calm", "standard", "attentive"],
                    default="standard")
    au.add_argument("--det-step", type=int, default=2)
    au.add_argument("--codec", choices=["h264", "hevc", "prores"], default="h264")
    au.add_argument("--out-size", default=None)
    au.add_argument("--no-audio", action="store_true")
    au.add_argument("-o", "--output", default=None)
    au.set_defaults(fn=cmd_auto)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
