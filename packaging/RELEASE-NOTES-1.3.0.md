# control-z Suite 1.3.0 — the meeting shows its shape

Sign and ship THIS one — it contains 1.2.0 (never released) plus the
same-day wave on top. Tag `v1.3.0`.

## New since 1.1.0 (1.2.0 + 1.3.0 together)

- **The read is seconds.** YouTube ingest skips the probe, races both
  caption routes on threads, scrapes the title from the same watch page,
  and jumps straight to the community relay on YouTube's gate tell.
  A 7-hour meeting: 7.4 s to 8,363 readable segments from a gated IP;
  re-opening a read meeting: 0.1 s.
- **Whisper, taught the names.** People, places and boards harvested from
  the meeting's own captions/title into an editable "names to teach"
  field, biased into the decoder (fix YouTube's own misspellings once —
  Scribe follows). large-v3 joins the menus. Hotwords on Scribe's page too.
- **Downloads, clips first.** The green button fetches only the kept spans
  (one file per span, named with its seconds); the full recording is its
  own explicit button wearing its duration. Quality best→4K→…→audio on
  Highlighter and Grabber; per-highlight ↓ clip; landed files Reveal in
  the Finder. Grabber can fetch a whole month's search in one click.
- **Reels wear title cards** (optional): ink card before each moment —
  meeting small, moment big, timestamp in green — in the same concat
  graph, audio locked, both render paths.
- **Sessions have a clock.** The streaming preview reports time; the
  transcript follows along (green edge on the row being spoken, `follow`
  chip scrolls it), the sparkline gets a playhead.
- **Analyze shows the shape**: meeting-pace bars (words/minute), dynamics
  lanes (questions · decisions · tension), an agenda card when the upload
  carries chapters or timestamp lines. All counted, all clickable.
- **AI, your key, optional.** Settings → AI takes an Anthropic key
  (0600, masked, env wins); Highlighter gains labeled generative brief +
  grounded answers with clickable [MM:SS]. Nothing changes without a key;
  no key ships.
- **⌘K** command palette; Index → Highlighter handoff; transport keys;
  8k-row transcripts render chunked with one delegated listener.

## Build & sign (on this machine)

No dependency changes since 1.1.0; `czcore/llm.py` is stdlib. Pillow (the
title cards) has been required since the Make wave.

    git pull
    .venv/bin/python -m unittest discover -s tests -t .   # the 2 cv2 gates must pass HERE
    packaging/build_suite.sh && packaging/sign_suite.sh && packaging/notarize_suite.sh
    # GitHub release v1.3.0, DMG attached, this file as the body
