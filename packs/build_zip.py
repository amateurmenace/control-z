"""Rebuild control-z-fusion-templates.zip from depth/templates/.

Reproducible (fixed mtime, sorted order, no macOS metadata) so the committed zip
only changes when a template does. Run: python packs/build_zip.py
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from depth.cli import ALL_TEMPLATES  # noqa: E402

SRC = ROOT / "depth" / "templates"
OUT = ROOT / "packs" / "control-z-fusion-templates.zip"
# Fixed timestamp keeps the archive byte-stable across rebuilds (1980-01-01,
# the ZIP epoch floor).
FIXED = (1980, 1, 1, 0, 0, 0)


def main() -> int:
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ALL_TEMPLATES:
            text = (SRC / f"{name}.setting").read_text()
            info = zipfile.ZipInfo(f"{name}.setting", date_time=FIXED)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, text)
    print(f"{len(ALL_TEMPLATES)} templates → {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
