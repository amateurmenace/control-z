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
    import av
    import cv2
    import numpy as np

    from czcore.media import probe

    from .engine import resolve_model, upscale_frame

    info = probe(args.input)
    v = info.video
    field = next((s.get("field_order") for s in info.raw.get("streams", [])
                  if s.get("codec_type") == "video"), None)
    if field and field not in ("progressive",):
        if not args.force:
            print(f"refusing: field_order={field} looks interlaced — deinterlace "
                  "first, or pass --force if you know better. (Honesty > silence.)")
            return 2
        print(f"  ! proceeding on possibly-interlaced source (--force)")

    model = resolve_model(args.model)
    scale = args.scale
    ow, oh = v.width * scale, v.height * scale
    ext = ".mov" if args.codec == "prores" else ".mp4"
    out_path = args.output or str(Path(args.input).with_name(
        f"{Path(args.input).stem}.rise-x{scale}{ext}"))
    print(f"Rise — {Path(args.input).name} {v.width}x{v.height} → {ow}x{oh} "
          f"({model}{', stabilized' if args.stabilize else ''})")
    if model == "lanczos":
        print("  note: lanczos backend = honest resampling, no reconstruction "
              "(convert the model with `python -m rise.convert` for synthesis).")

    CODECS = {"h264": ("libx264", "yuv420p", {"crf": "16", "preset": "medium"}),
              "hevc": ("libx265", "yuv420p", {"crf": "18", "preset": "medium"}),
              "prores": ("prores_ks", "yuv422p10le", {"profile": "3"})}
    codec, pix, opts = CODECS[args.codec]

    prev_out = None
    prev_small = None
    n = 0
    with av.open(args.input) as inp, av.open(out_path, "w") as out:
        vin = inp.streams.video[0]
        vin.thread_type = "AUTO"
        vout = out.add_stream(codec, rate=vin.average_rate or 24, options=opts)
        vout.width, vout.height = ow, oh
        vout.pix_fmt = pix
        for packet in inp.demux(vin):
            for frame in packet.decode():
                img = frame.to_ndarray(format="bgr24")
                up, _ = upscale_frame(img, scale, model=model, tile=args.tile)
                if args.stabilize and prev_out is not None:
                    # flow on quarter-res input frames, gate by warp error
                    small = cv2.resize(img, (v.width // 4, v.height // 4))
                    flow = cv2.calcOpticalFlowFarneback(
                        cv2.cvtColor(prev_small, cv2.COLOR_BGR2GRAY),
                        cv2.cvtColor(small, cv2.COLOR_BGR2GRAY),
                        None, 0.5, 3, 21, 3, 5, 1.2, 0)
                    flow_up = cv2.resize(flow, (ow, oh)) * (4 * scale)
                    grid = np.mgrid[0:oh, 0:ow].astype(np.float32)
                    map_x = grid[1] - flow_up[..., 0]
                    map_y = grid[0] - flow_up[..., 1]
                    warped = cv2.remap(prev_out, map_x, map_y, cv2.INTER_LINEAR,
                                       borderMode=cv2.BORDER_REPLICATE)
                    err = np.abs(warped.astype(np.int16) - up.astype(np.int16)
                                 ).mean(axis=2, keepdims=True)
                    gate = np.clip(1.0 - err / 24.0, 0.0, 1.0) * 0.5
                    up = (up * (1 - gate) + warped * gate).astype(np.uint8)
                if args.stabilize:
                    prev_small = cv2.resize(img, (v.width // 4, v.height // 4))
                    prev_out = up
                vf = av.VideoFrame.from_ndarray(up, format="bgr24")
                for pkt in vout.encode(vf):
                    out.mux(pkt)
                n += 1
                print(f"  …{n} frames", end="\r", flush=True)
        for pkt in vout.encode():
            out.mux(pkt)
    print(f"\n  {n} frames → {out_path}")
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
    pu.add_argument("--codec", choices=["h264", "hevc", "prores"], default="prores")
    pu.add_argument("--force", action="store_true")
    pu.add_argument("-o", "--output")
    pu.set_defaults(fn=cmd_up)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
