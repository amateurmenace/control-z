"""grabber-cli — search the portal, fetch, conform. Station-scriptable.

    grabber-cli search --from 2026-07-01 --to 2026-07-16 [--tenant brooklinema]
    grabber-cli fetch "https://…zoom.us/rec/…" [--out DIR]
    grabber-cli convert meeting.mp4 [--preset prores-422] [--height 1080] [--fps 29.97]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="grabber-cli", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="list a portal's meetings in a date range")
    s.add_argument("--tenant", default="brooklinema")
    s.add_argument("--from", dest="date_from", required=True)
    s.add_argument("--to", dest="date_to", required=True)

    f = sub.add_parser("fetch", help="download a recording URL")
    f.add_argument("url")
    f.add_argument("--out", default=None)
    f.add_argument("--quality", default="best")

    c = sub.add_parser("convert", help="conform a file for broadcast")
    c.add_argument("path")
    c.add_argument("--preset", default="prores-422")
    c.add_argument("--height", type=int, default=None)
    c.add_argument("--fps", type=float, default=None)
    c.add_argument("--out", default=None, help="output folder (default: beside source)")

    a = ap.parse_args(argv)
    if a.cmd == "search":
        from .civicclerk import search_events
        for ev in search_events(a.tenant, a.date_from, a.date_to):
            vids = [l["url"] for l in ev["links"] if l["videoish"]]
            print(f"{(ev['when'] or '')[:16]:17} {ev['name'][:56]:57} "
                  f"{ev['category'][:18]}")
            for u in vids:
                print(f"                  ▸ {u}")
        return
    if a.cmd == "fetch":
        from czcore.paths import media_dir
        out = Path(a.out) if a.out else media_dir("grabber")
        prog = lambda p, m: print(f"\r{m or f'{p*100:5.1f}%'}", end="", flush=True)  # noqa: E731
        from . import zoomshare
        if zoomshare.is_zoom_share(a.url):
            got = zoomshare.download(a.url, out, progress=prog)
        else:
            from czcore import ytdlp
            ytdlp.check_async(force=True)
            while ytdlp.status()["phase"] in ("checking", "updating"):
                time.sleep(0.5)
            got = ytdlp.download(a.url, out, quality=a.quality, progress=prog)
        print(f"\n→ {got['path']}")
        return
    from .convert import convert
    rep = convert(a.path, a.out or str(Path(a.path).parent), preset=a.preset,
                  fps=a.fps, height=a.height,
                  progress=lambda p, m: print(f"\r{p*100:5.1f}%", end="", flush=True))
    print(f"\n→ {rep['out']}  ({rep['label']}, "
          f"{'hardware' if rep['hardware'] else 'software'} encode)")


if __name__ == "__main__":
    sys.exit(main())
