# control-z Suite 1.4.0 — the web app's three rooms, the two doors out

Sign and ship THIS one — it contains the unreleased 1.2.0 and 1.3.0 waves
too. Tag `v1.4.0`. Highlights since 1.1.0:

- **Highlighter = the web app, desktop-sized.** Three sections (Meeting
  Highlighter · Highlight Video Editor · Meeting Analyzer), reads a 7-hour
  meeting in seconds, session clock + follow-along transcript, pace/
  dynamics charts, agenda card, ✨ local + 🤖 BYO-key AI highlight reels.
- **Export Video, two doors**: a share link the deployed web player opens
  (clips encoded in the URL, nothing uploaded), or a staged
  download-and-cut into one MP4 — only the kept spans leave YouTube,
  optional title cards, Reveal in Finder.
- **Whisper taught the names** (hotwords harvested from the meeting,
  editable; large-v3 in the menus). **DaVinci Tools** page (node tree,
  middle-gray anchor, Fusion pack). Credit footer. ⌘K everywhere.

Build: no dependency changes since 1.1.0.

    git pull
    .venv/bin/python -m unittest discover -s tests -t .   # packaging gates must pass HERE
    packaging/build_suite.sh && packaging/sign_suite.sh && packaging/notarize_suite.sh
    # GitHub release v1.4.0, DMG attached, this file as the body
