"""The web app — the Community AI Project, pressed into a static edition.

`python -m web.bake --corpus <corpus.db> --out site/docs/app` reads everything
Memory knows and writes a browsable, backend-free edition: JSON data planes,
a prebuilt lexical search index, RSS feeds, caption/AD tracks, and per-page
HTML stubs that carry the transcript as real text (readable with JavaScript
off) and unfurl with the meeting's name and thumbnail in a group chat.

Pure stdlib for the bake; the reader (web/static/app.js) is no-build vanilla
JS on the suite's own tokens. No accounts, no cookies, no telemetry, no video
rehosting — the covenant, carried outdoors. specs/16 is the law.
"""

SCHEMA_VERSION = 1
