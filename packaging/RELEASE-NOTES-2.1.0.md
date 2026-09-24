# Civic Media Studio 2.1.0 — the desk, fixed where it hurt

**The first published release since 1.9.0.** It carries everything from the
never-published 2.0.0 (the Civic Media Studio identity — see below) plus a
field report's worth of desk fixes, each traced to its root before it was
touched. Tag `v2.1.0`.

**Read this before you install: the app has a new identity.** Since 2.0.0 the
bundle id is `org.civicmedia.studio` (it was `org.control-z.suite`). macOS
treats that as a different application, so 2.1.0 installs *beside* 1.9.0
instead of replacing it. Drag **Civic Media Studio** into Applications, open
it once, then delete the old **control-z Suite** app yourself — nothing will do
it for you. Your meetings, downloads and settings live outside the app and
carry straight over.

## What's new in 2.1.0

- **Transcripts come back.** Highlighter's captions had quietly stopped
  arriving: YouTube's watch-page caption links now carry a proof-of-origin
  token wall and answer with an empty file from *any* address, so no proxy
  could have fixed it. Captions now come through YouTube's player API — a
  four-hour meeting reads in about two seconds, no proxy needed.
- **Captions read once, not twice.** YouTube's rolling auto-captions were
  parsed so that every line of a meeting appeared twice, each block's first
  words a few seconds late — and search, highlights and summaries read the
  doubles. Fixed at the parser; meetings you already read re-read their
  caption file once, by themselves. Scribe transcripts are untouched.
- **Fetch asks first.** Pick a quality before a byte moves: the Grabber reads
  what the video really offers and lists each option with its size — 1080p
  about 83 MB, 720p about 47 MB, audio only about 4 MB — the way the download
  will actually take it. (The app keeps to H.264 so every file opens in
  QuickTime and every editor; YouTube serves H.264 up to 1080p, so "4K" no
  longer quietly means 1080p — the chooser says so.)
- **A caption hiccup never costs you the video.** yt-dlp fetched subtitles
  *before* the video, so a caption "429 Too Many Requests" aborted the whole
  download. Captions now come separately, after the video is safe on disk.
- **Downloads land in `~/Downloads/Civic Media Studio`** — the first fetch
  asks once (here, or a folder you choose), and the location is shown with
  Show in Finder / Change on the Grabber and in Settings.
- **The proxy is a switch, off by default.** When YouTube refuses a computer
  (429s, "confirm you're not a bot"), turn it on right in the Grabber or
  Highlighter: the app carries a built-in account for exactly that, or add
  your own Webshare account in Settings → Fetch network. "Test the connection"
  answers with the exit address or the fix.
- **The Highlighter, reshaped around its three steps.** ① Find the moments →
  ② Build the reel → ③ Analyze, always in reach in a bar at the top, with
  **✨ Make a highlight reel** beside them (what the moments are about, how
  long, and who picks — this computer, or AI with your key) and again in the
  timeline. The reel is the whole cut list, sized to the length you chose,
  each moment long enough to finish its sentence. **The player follows you:**
  press play anywhere down the page and it lifts into the corner — clip 3 of
  8, ⏮ ⏭ ↑ ✕ — and settles back when you scroll up. The reel plays on the
  meeting's own clock, so clips no longer end early while YouTube buffers, and
  it stops at its last clip instead of running on into the meeting.
- **The AI summary is an executive summary** — one paragraph, about five
  sentences, its key moments one click away. Without a key you see the
  meeting's key lines, labeled as exactly that, and one button to write it.
- **Keys, asked for kindly.** Anything that needs an AI key says so and opens
  a popup with step-by-step instructions for getting one — then carries on.
- **Optional runtimes install from the signed app.** Stencil's rotoscoping
  engine (SAM2), Clear's voice isolation and the Deno helper install from
  Settings → Optional runtimes in the signed build — with manual install
  instructions, the exact folder, and a Check button for anyone who'd rather
  do it by hand.
- **Every page resets; every job cancels; nothing is forgotten.** ↺ Reset on
  every page; Cancel on every job, with partial files removed; the Queue keeps
  a permanent history you can search and export as CSV.
- **Pages that say what they're for.** Publisher, Interpreter and Narrator
  open with what they make and how, in numbered steps; **Send to next app**
  hands a meeting down the line with its data; Publisher kits land in one
  folder per meeting that you choose. The Grabber got the same pass — one way
  in, one strip for where files go and the proxy, and a calmer bin.
- **Highlighter follows the Grabber in the rail,** and anything the Grabber
  fetched opens in the Highlighter.

## Also new since 1.9.0 (the 2.0.0 work)

- **The suite is Civic Media Studio.** The app, its icon, its window title and
  its home page carry civicmedia.studio. Control-Z stays its own brand inside
  the suite — free finishing tools for DaVinci Resolve, still at control-z.org.
- **The public record is publicrecord.studio** — the web edition, published
  separately; nothing of it ships in this DMG.
- **The desk's fifth wave.** Rise joins the road, presets name their work, a
  consistency pass across all eight desk pages, and local cards for machine
  translation and vision on the Models page.

## Install

- **Apple silicon, macOS 15.5 or later.** Signed with Developer ID
  (team 6M536MV7GT), notarized and stapled.
- `civicmedia-studio-2.1.0-macos-arm64.dmg` — 126.7 MB, sha256
  `e453709556fcdd63a6231931d1641708b5ea970ec894c7d486b14f596d786b18`
- `NOTICE.txt` and the FFmpeg LGPL-2.1 licence ride in the DMG beside the app.
- AI features are optional and use **your own** key; the app asks when one is
  needed. The built-in proxy account has a monthly cap — if it's ever spent,
  add your own in Settings → Fetch network.

## Build notes for the signing operator

- **Two version truths agree**: `pyproject.toml` and `suite/__init__.py` are
  both `2.1.0` (the statics cache-bust off the latter).
- **The built-in proxy account** is `czcore/house_proxy.json` — gitignored,
  never committed, baked in when present. The build log says which:
  `[suite.spec] built-in proxy account: baked in`. It is obfuscated, not
  secret: scope it (a Webshare sub-user with a bandwidth cap).
- **New data files in the freeze:** `stencil/sam2_engine.py` (the SAM2 helper
  the managed runtime runs) and the house proxy file; new hidden imports
  `czcore.pyruntime`, `czcore.proxy`, `czcore.captions`, `stencil.sam2_engine`,
  `suite.tools.keyneed`.
- **`tests/test_packaging.py` must report eight tests and no skips** — a skip
  there is a gate that lost its inputs (a missing `otool` silently skips every
  GPL-linkage gate).
- The FFmpeg posture is unchanged: LGPL-2.1, no `--enable-gpl`, no x264/x265.
  `record/` stays out of `suite.spec`.

## The ritual (run on the signing Mac)

    .venv/bin/pip install -e '.[packaging]'
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python -m unittest discover -s tests -t .
    #   957 tests; the record's Postgres half skips without RECORD_TEST_PG_DSN
    #   (none of it ships in the DMG)
    packaging/build_suite.sh    # freezes onedir; fails loudly on a missing asset
    packaging/sign_suite.sh     # Developer ID, hardened runtime, zero entitlements
    packaging/notarize_suite.sh # staples the app, builds + notarizes the DMG

The gate that cannot run on a dev machine (specs/09 §7) — `spctl -a -vvv` on a
Mac that has never seen a developer certificate — still matters most for an app
whose identity is new.
