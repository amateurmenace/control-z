#!/usr/bin/env python3
"""Bake control-z.org: tools.yaml + templates -> docs/ (static, self-contained).

    python3 site/build.py

Philosophy (specs/07): no JS build chain, view-source friendly, data-driven —
adding a tool touches tools.yaml and nothing else.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"


def main() -> int:
    try:
        import yaml
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        print("pip install jinja2 pyyaml")
        return 2

    import base64
    import mimetypes

    tools = yaml.safe_load((ROOT / "content" / "tools.yaml").read_text())
    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=False, trim_blocks=True, lstrip_blocks=True)
    assets = ROOT / "content" / "assets"

    def b64(name: str) -> str:
        """Bake an asset as a data URI — self-contained pages, hush-site style."""
        p = assets / name
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"

    def asset_text(name: str) -> str:
        return (assets / name).read_text()

    env.globals.update(b64=b64, asset_text=asset_text)
    DOCS.mkdir(exist_ok=True)

    # single-page site: tools live at index.html#t-<id>; only roadmap stays a page
    pages = {
        "index.html": ("home.html", "home"),
        "roadmap.html": ("roadmap.html", "roadmap"),
        "templates.html": ("templates.html", "templates"),
        "node-tree.html": ("node-tree.html", "node-tree"),
    }
    for stale in DOCS.glob("*.html"):
        if stale.name not in pages and stale.name != "whitepaper.html":
            stale.unlink()
            print(f"  removed stale {stale.name}")
    for out_name, (tpl, page) in pages.items():
        html = env.get_template(tpl).render(tools=tools, page=page)
        (DOCS / out_name).write_text(html)
        print(f"  {out_name}  ({len(html)//1024} KB)")
    # the custom domain lives here, not in GitHub's UI: every deploy rebuilds the
    # gh-pages branch from this folder, so a UI-only setting would be wiped.
    (DOCS / "CNAME").write_text("control-z.org\n")
    print("  CNAME  (control-z.org)")

    # carry the Hush design study (+ its PDF) so those URLs survive the CNAME move
    hush_docs = Path.home() / "Hush" / "Hush-OpenNR" / "docs"
    for name in ("whitepaper.html", "hush-whitepaper.pdf"):
        src = hush_docs / name
        if src.exists():
            (DOCS / name).write_bytes(src.read_bytes())
            print(f"  {name}  (carried from Hush-OpenNR/docs)")
    print(f"baked → {DOCS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
