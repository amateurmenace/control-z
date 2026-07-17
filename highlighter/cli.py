"""highlighter-cli — the whole pipeline, scriptable per station habit.

    highlighter-cli fetch "https://youtube.com/watch?v=…" [--quality 1080]
    highlighter-cli detect meeting.mp4 [--target 90] [--keywords "override,zoning"]
    highlighter-cli reel meeting.mp4 --out reel.mp4 [--target 90] [--preset h264]

detect prints the cut list with reasons; reel renders it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _transcript_segments(path: Path) -> list:
    sc = path.with_suffix(".scribe.json")
    if sc.exists():
        return json.loads(sc.read_text()).get("segments", [])
    from .highlights import parse_vtt
    vtts = sorted(s for s in path.parent.iterdir()
                  if s.name.startswith(path.stem) and s.suffix == ".vtt")
    for vtt in vtts:
        segs = parse_vtt(vtt.read_text(errors="replace"))
        if segs:
            return segs
    raise SystemExit(f"no transcript next to {path.name} — run Scribe on it "
                     "or fetch with captions first")


def _detect(path: Path, target: float, keywords: list) -> list:
    from .highlights import (audio_energy, blend_energy, build_reel,
                             score_segments)
    segs = _transcript_segments(path)
    scored = blend_energy(score_segments(segs, keywords),
                          audio_energy(str(path)))
    return build_reel(scored, target=target)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="highlighter-cli", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download a video with the managed yt-dlp")
    f.add_argument("url")
    f.add_argument("--quality", default="best", help="best | 1080 | 720 | audio")
    f.add_argument("--out", default=None, help="folder (default ~/Movies/control-z/highlighter)")

    d = sub.add_parser("detect", help="print the highlight cut list, with reasons")
    d.add_argument("path", type=Path)
    d.add_argument("--target", type=float, default=90.0)
    d.add_argument("--keywords", default="", help="comma-separated extra terms")

    r = sub.add_parser("reel", help="render the highlight reel")
    r.add_argument("path", type=Path)
    r.add_argument("--out", default=None)
    r.add_argument("--target", type=float, default=90.0)
    r.add_argument("--keywords", default="")
    r.add_argument("--preset", default="h264")

    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        from czcore import ytdlp
        from czcore.paths import media_dir
        st = ytdlp.check_async(force=True)
        print(f"yt-dlp: {st.get('detail') or st.get('phase')}")
        import time
        while ytdlp.status()["phase"] in ("checking", "updating"):
            time.sleep(0.5)
        got = ytdlp.download(a.url, Path(a.out) if a.out else media_dir("highlighter"),
                             quality=a.quality,
                             progress=lambda p, m: print(f"\r{m or f'{p*100:5.1f}%'}",
                                                         end="", flush=True))
        print(f"\n→ {got['path']}")
        return
    kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
    picks = _detect(a.path, a.target, kws)
    if a.cmd == "detect":
        for p in picks:
            print(f"{p['start']:8.1f}–{p['end']:8.1f}  {'·'.join(p['reasons'])[:80]}")
            print(f"          “{p['text'][:100]}”")
        total = sum(p["end"] - p["start"] for p in picks)
        print(f"-- {len(picks)} moments, {total:.0f}s")
        return
    from .reel import render_reel
    out = a.out or str(a.path.with_suffix("")) + ".reel.mp4"
    rep = render_reel(str(a.path), picks, out, preset=a.preset,
                      progress=lambda p, m: print(f"\r{p*100:5.1f}%", end="", flush=True))
    print(f"\n→ {rep['out']}  ({rep['clips']} clips, {rep['duration']}s, "
          f"{rep['encoder']})")


if __name__ == "__main__":
    sys.exit(main())
