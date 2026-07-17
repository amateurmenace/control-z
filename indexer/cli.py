"""index-cli — the librarian from the terminal.

    index-cli add ~/Footage            # watch a folder
    index-cli scan                     # (re)log everything
    index-cli search "crosswalk vote"  # plain words, time-coded hits
    index-cli export out.fcpxml --q "crosswalk"   # stringout of the hits
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import Catalog


def main(argv=None):
    ap = argparse.ArgumentParser(prog="index-cli", description=__doc__)
    ap.add_argument("--db", default=None, help="catalog path (default: app support)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("folder")
    r = sub.add_parser("remove"); r.add_argument("folder")
    sub.add_parser("scan")
    s = sub.add_parser("search"); s.add_argument("query", nargs="+")
    e = sub.add_parser("export")
    e.add_argument("out", type=Path)
    e.add_argument("--q", default="", help="export the hits for this query")

    args = ap.parse_args(argv)
    cat = Catalog(args.db)
    if args.cmd == "add":
        cat.add_folder(args.folder)
        print(f"watching {args.folder} — run: index-cli scan")
    elif args.cmd == "remove":
        cat.remove_folder(args.folder)
        print("removed (its clips left the catalog)")
    elif args.cmd == "scan":
        st = cat.scan(progress=lambda m: print(f"\r{m[:76]:76}", end="", flush=True))
        print(f"\r{st['seen']} seen · {st['added']} added · "
              f"{st['updated']} updated · {st['missing']} missing"
              f"{' · ' + str(st['unreadable']) + ' unreadable' if st['unreadable'] else ''}")
    elif args.cmd == "search":
        rows = cat.search(" ".join(args.query))
        for row in rows:
            mins = (row["duration"] or 0) / 60
            print(f"{row['name'][:52]:53} {mins:6.1f}m  "
                  f"{'missing!' if row['missing'] else row['folder'][-24:]}")
            for m in row["matches"]:
                print(f"    {m['t']:8.1f}s  “{m['text'][:90]}”")
        if not rows:
            print("nothing matched — words come from filenames, folders and "
                  "Scribe transcripts")
    elif args.cmd == "export":
        from czcore.exports.fcpxml import selects_csv, stringout
        rows = cat.search(args.q, limit=500)
        if not rows:
            raise SystemExit("nothing to export")
        if args.out.suffix.lower() == ".csv":
            args.out.write_text(selects_csv(rows))
        else:
            args.out.write_text(stringout(rows))
        print(f"→ {args.out}  ({len(rows)} clips) — Resolve: File → Import → "
              "Timeline")


if __name__ == "__main__":
    sys.exit(main())
