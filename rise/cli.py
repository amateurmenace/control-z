"""rise-cli — up / probe. Batch upscaling for archives and punch-in rescue."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def cmd_probe(args) -> int:
    from czcore.media import probe

    info = probe(args.input)
    v = info.video
    if not v:
        print("no video stream")
        return 2
    field = "unknown"
    for s in info.raw.get("streams", []):
        if s.get("codec_type") == "video":
            field = s.get("field_order", "progressive or untagged")
    print(f"{Path(args.input).name}: {v.width}x{v.height} @ {v.fps:.3f} "
          f"({v.codec}), field_order={field}")
    if field not in ("progressive", "progressive or untagged"):
        print("  ! interlaced/telecined source — deinterlace BEFORE upscaling "
              "(QTGMC or Resolve's deinterlacer), or Rise will sharpen the combs.")
    for target in (1080, 2160):
        if v.height < target:
            print(f"  to {target}p: {target / v.height:.2f}x "
                  f"({'x2 model' if target / v.height <= 2 else 'x4 model'} + fit)")
    return 0


def cmd_up(args) -> int:
    from czcore.media import probe, resolve_preset

    from .engine import resolve_model
    from .video import InterlacedSourceError, upscale_video

    info = probe(args.input)
    v = info.video
    model = resolve_model(args.model)
    scale = args.scale
    # One codec-choosing path for the whole program: czcore's export presets.
    # The libx264/libx265 table that used to live here silently overrode
    # upscale_video's correct default AND offered GPL encoders (specs/09 §3).
    # No-encoder is a sentence + exit 2, never a traceback: h264/hevc have no
    # software fallback by design, and a source build without VideoToolbox
    # (Linux, conda PyAV) hits this on the first explicit --codec h264.
    try:
        spec = resolve_preset(
            {"h264": "h264", "hevc": "hevc", "prores": "prores-hq"}[args.codec])
    except RuntimeError as e:
        print(f"{e} — prores works on every build (--codec prores).")
        return 2
    ext = "." + spec["container"]
    out_path = args.output or str(Path(args.input).with_name(
        f"{Path(args.input).stem}.rise-x{scale}{ext}"))
    print(f"Rise — {Path(args.input).name} {v.width}x{v.height} → "
          f"{v.width * scale}x{v.height * scale} "
          f"({model}{', stabilized' if args.stabilize else ''})")
    if model == "lanczos":
        print("  note: lanczos backend = honest resampling, no reconstruction "
              "(convert the model with `python -m rise.convert` for synthesis).")
    if args.force:
        print("  ! interlace guard bypassed (--force)")

    try:
        report = upscale_video(
            args.input, out_path, scale=scale, model=model, tile=args.tile,
            stabilize=args.stabilize, codec_spec=spec,
            force=args.force,
            denoise="hush" if args.denoise else "off",
            progress=lambda n, total: print(f"  …{n} frames", end="\r", flush=True))
    except InterlacedSourceError as e:
        print(str(e).replace("force if", "pass --force if"))
        return 2
    print(f"\n  {report['frames']} frames → {report['out']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="rise-cli",
        description="Rise restores the detail — super-resolution for archives. "
                    "Part of control-z (https://control-z.org).")
    p.add_argument("--version", action="version", version=f"rise {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("probe", help="interlace + punch-in report")
    pp.add_argument("input")
    pp.set_defaults(fn=cmd_probe)

    pu = sub.add_parser("up", help="upscale a clip")
    pu.add_argument("input")
    pu.add_argument("--scale", type=int, choices=[2, 4], default=2)
    pu.add_argument("--model", default="auto")
    pu.add_argument("--tile", type=int, default=512)
    pu.add_argument("--stabilize", action="store_true",
                    help="flow-gated temporal blend (kills per-frame shimmer)")
    pu.add_argument("--denoise", action="store_true",
                    help="clean noise BEFORE scaling (Hush core: 3-frame "
                         "temporal + fine NLM) — upscaling amplifies noise")
    pu.add_argument("--codec", choices=["h264", "hevc", "prores"], default="prores")
    pu.add_argument("--force", action="store_true")
    pu.add_argument("-o", "--output")
    pu.set_defaults(fn=cmd_up)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
