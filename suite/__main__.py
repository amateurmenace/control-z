"""python -m suite — the Community AI Project (add --serve for a browser)."""

from __future__ import annotations

import argparse

from .server import create_suite_app, run


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="suite",
        description="Community AI Project — the civic media suite, with the "
                    "control-z workbench inside. Local only; no accounts, "
                    "no telemetry.")
    p.add_argument("--port", type=int, default=8300)
    p.add_argument("--serve", action="store_true",
                   help="serve for a browser instead of opening a window")
    args = p.parse_args(argv)
    app = create_suite_app()
    run(app, port=args.port, open_window=not args.serve)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
