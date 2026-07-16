"""python -m pivot.app — launch the Pivot UI (add --serve for browser-only)."""

from __future__ import annotations

import argparse
from pathlib import Path

from czcore.appshell import create_app, run

from .ui import register

STATIC = Path(__file__).parent / "static"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pivot")
    p.add_argument("--port", type=int, default=8330)
    p.add_argument("--serve", action="store_true",
                   help="serve for a browser instead of opening a window")
    args = p.parse_args(argv)
    print("note: this standalone page is retired in favor of the Suite — "
          "run `python -m suite` for the full workbench (this still works).")
    app = create_app("Pivot", STATIC, register)
    run(app, port=args.port, open_window=not args.serve)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
