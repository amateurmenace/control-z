"""python -m suite — the control-z Suite (add --serve for a plain browser)."""

from __future__ import annotations

import argparse

from .server import create_suite_app, run


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="suite",
        description="control-z Suite — the workbench around Resolve. "
                    "Local only; no accounts, no telemetry.")
    p.add_argument("--port", type=int, default=8300)
    p.add_argument("--serve", action="store_true",
                   help="serve for a browser instead of opening a window")
    args = p.parse_args(argv)
    app = create_suite_app()
    run(app, port=args.port, open_window=not args.serve)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
