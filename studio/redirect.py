"""Redirect stubs, for the day the record changes address — and not before.

specs/17 §11.4: `control-z.org/app/*` becomes redirect stubs into the Studio,
so every civic citation minted so far survives. Those citations are the point.
A resident who pasted a deep link into a comment letter in June, a reporter who
footnoted a timestamp, the town's own agenda packet linking a moment — none of
them will be re-issued, and a 404 is the record forgetting something it
promised to keep.

Which is exactly why this is a command and not a step that already ran.
**Redirecting a working edition at a Studio that does not exist yet would break
every one of those links to fix a problem nobody has.** Nothing here runs until
`communityai.studio` actually serves the record; the runbook
(`studio/INFRA.md`) puts it after DNS.

The stubs are deliberately dumb: a `<meta http-equiv="refresh">` and a real
`<a>`, because GitHub Pages serves no redirect headers and a reader with
JavaScript off must still be able to follow the link by hand. Each one carries
the path it came from, so `control-z.org/app/i/vision-zero` lands on the same
issue in the Studio rather than dumping everyone at a home page — a redirect
that loses the deep link is only half a promise kept.

    python -m studio.redirect --edition site/docs/app --to https://communityai.studio
    python -m studio.redirect --edition site/docs/app --to ... --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The routes the reader mints links into. Anything with an index.html under the
# edition is a page somebody may have cited.
_STUB = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title} — moved to the Studio</title>
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<meta name="robots" content="noindex">
<style>body{{font:16px/1.6 system-ui,sans-serif;margin:12vh auto;max-width:34rem;
padding:0 1.2rem;color:#1a1a1a;background:#f7f5f0}}a{{color:#7b2d3b}}
p{{margin:.6rem 0}}</style></head>
<body>
<h1>The record moved.</h1>
<p>This page now lives at the Community AI Studio, and the link you followed
points at the same place there.</p>
<p><a href="{target}">{target}</a></p>
<p style="opacity:.7">If your browser does not follow it automatically, the
link above is the one you want. Nothing was lost — the record kept its
addresses.</p>
</body></html>
"""


def plan(edition: Path, base: str) -> list:
    """Every page in a pressed edition, paired with where it goes. Returns
    `[(local_path, target_url)]` — computed, never guessed, so a route the bake
    stops emitting stops being redirected too."""
    base = base.rstrip("/")
    out = []
    for page in sorted(edition.rglob("index.html")):
        rel = page.parent.relative_to(edition).as_posix()
        rel = "" if rel == "." else rel
        target = f"{base}/app/{rel}".rstrip("/")
        out.append((page, target))
    return out


def write_stubs(edition: Path, base: str, dry_run: bool = True) -> dict:
    pairs = plan(edition, base)
    written = 0
    for page, target in pairs:
        title = page.parent.name or "The record"
        if not dry_run:
            page.write_text(_STUB.format(title=title, target=target),
                            encoding="utf-8")
        written += 1
    return {"pages": len(pairs), "written": 0 if dry_run else written,
            "dry_run": dry_run}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m studio.redirect",
        description="Point a pressed edition's pages at the Studio. "
                    "Run this at DNS cutover, never before.")
    ap.add_argument("--edition", required=True,
                    help="the pressed edition to overwrite (e.g. site/docs/app)")
    ap.add_argument("--to", required=True,
                    help="the Studio's base URL, e.g. https://communityai.studio")
    ap.add_argument("--write", action="store_true",
                    help="actually overwrite. Without this it only reports.")
    args = ap.parse_args(argv)

    edition = Path(args.edition)
    if not (edition / "manifest.json").exists():
        print(f"{edition} does not look like a pressed edition "
              f"(no manifest.json). Refusing to overwrite it.")
        return 1

    result = write_stubs(edition, args.to, dry_run=not args.write)
    if result["dry_run"]:
        print(f"would replace {result['pages']} page(s) in {edition} with "
              f"redirects to {args.to}/app/…")
        print("nothing written — pass --write when the Studio actually serves "
              "the record. Until then these links work and the redirects "
              "would not.")
    else:
        print(f"replaced {result['written']} page(s) with redirects to "
              f"{args.to}/app/…")
        print("the deep links are preserved path for path; push the edition.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
