# 11 — the Make wave: Highlighter, Grabber, Index, Slate

Built 2026-07-16. Four tools in one wave: the two community apps that grew up
at BIG (community-highlighter, BIG-Video-Grabber) rebuilt on czcore, plus two
from the long-list spec (`~/Hush/control-z-suite-spec.md`): **Index**
(Assist/"local footage librarian") and **Slate** (Deliver/"station graphics
kit"). Home gains a third door — **Make** — between Prep and Finish, and the
intro line becomes *"What are we creating today?"*

## The community pair — blended identity, deliberately separate

Highlighter and Grabber are `group: "community"` in the tools registry:
their own rail section ("community · via BIG"), **square** glyphs where the
workbench uses diamonds, accent-washed rows, one-line titles that keep the
old app names (Community Highlighter, BIG Video Grabber). Accents:
`--highlighter: #A8B54B` (the pen), `--grabber: #3FA9D0` (BIG's blue).
Index (`#B08968`, card-catalog oak) and Slate (`#C77BA6`, the broadcast
key/fill magenta) are natives and sit in the main tools list.

## Shared plumbing (czcore)

- `ytdlp.py` — the managed **nightly**: binary in app support/bin, GitHub
  latest-release check with a 60s cooldown, atomic replace, meta json.
  **The check runs on every fetch-tool page open** — that's a stated deal,
  surfaced as a chip ("yt-dlp nightly 2026.07.14…"). Offline is a state:
  the sentence says so and the old binary keeps working. `download()` parses
  `--newline` progress; success = the video landed (a failed caption fetch
  after it must not throw the video away); sub-langs are `en,en-orig` only
  (`en.*` pulls every translated variant → YouTube 429s).
- `ffrun.py` — ffmpeg runner with `-progress pipe:1` → 0..1 fraction,
  cooperative cancel, last stderr line as the error sentence.
  `encoder_args(spec, audio=)` maps `resolve_preset()` output to args; PCM
  into mov, AAC into mp4, never a GPL encoder.
- `paths.py` — user media lands in `~/Movies/control-z/<tool>` (mac) /
  `~/Videos/...` elsewhere; app support via `support_dir()`.
- `exports/fcpxml.py` — selects → **stringout timeline** (FCPXML 1.8, `src`
  on the asset — the oldest form importers still read). NTSC rates get exact
  rationals (1001/30000s); other rates rationalized over 1000. EDL can't do
  multi-source stringouts; this is why Index speaks FCPXML.

## Highlighter (`highlighter/`, routes `/api/highlighter/*`)

Meeting video → text → reel. Transcripts are *borrowed before computed*:
Scribe sidecar wins; else yt-dlp's caption VTT seeds one (YouTube word tags
`<00:00:01.199>` become timed words — karaoke without a model; rolling
two-line repeats deduped), written to the shared `.scribe.json` with
`model: "captions:…"` so Scribe can edit it and Index can search it. The
Scribe upgrade button calls `/api/scribe/transcribe` — same app, zero new
backend. `highlights.py` scores segments with a **transparent keyword pass**
(decision 2.5 / money 1.5 / community 1.2 / tension 1.5 / reaction 2.0 +
emphasis regexes + user keywords), length-normalized, unit-normalized;
optional `audio_energy()` blend (RMS percentile > 0.85 boosts, reason says
"room energy"). `build_reel()` pads, clamps, merges (+ a final chronological
sweep — a merge can grow a pick into a neighbor it never got compared
against). **Every pick carries reasons** — the covenant surface; the UI
shows a "why" chip and an amber score lane (scores are measurements).
The reel renders as ONE ffmpeg trim/concat filter graph (audio stays locked,
hard cuts by design — transitions belong to Resolve via the selects EDL,
exported through scribe's own `/api/scribe/selects`).
Reel output path: **append**, never `with_suffix()` — `meeting.reel` +
`.mp4`; `with_suffix` strips `.reel` and resolves to the source (guarded).

## Grabber (`grabber/`, routes `/api/grabber/*`)

`civicclerk.py` reads the OData `/v1/Events` feed **defensively**: every
URL-shaped string anywhere in the event JSON is harvested with its field
path, `videoish` flagged (zoom.us, **zoomgov.com**, youtube, vimeo, .mp4…),
bare `youtubeVideoId` synthesized into a watch URL. Tenant is any CivicClerk
town; Brookline (`brooklinema`) is home. Reality check (2026-07): Brookline
recordings live in `externalMediaUrl` as **zoomgov** share links.

`zoomshare.py` replaces the old app's Puppeteer: share URL → cookies +
`meetingId` from `window.__data__` → `/nws/recording/1.0/play/share-info/`
→ redirect → play page `fileId` → `/nws/recording/1.0/play/info/` →
`viewMp4Url`, downloaded with the same cookie jar + Referer. Multi-clip
chains via `nextClipStartTime`. yt-dlp doesn't match zoomgov at all — this
is the piece that makes Grabber real for MA towns. Zoom redecorates this
flow every year or so; every step fails with a sentence naming the step.

`convert.py` conforms for air: constant-rate always (Zoom records VFR;
playout seeks badly), optional height/fps, shared presets, hardware badge
in the UI.

## Index (`indexer/` — module name avoids the generic `index`; tool id/routes
stay `index`)

SQLite catalog in app support (`FTS5` when the build has it, LIKE fallback,
and the stats line admits which). Scan is incremental (size+mtime, and
sidecar mtime separately — a transcript appearing later re-indexes without
re-probing); vanished files are **marked missing, never forgotten**
(archives live on unplugged drives). Search returns clips + up to 3
**time-coded snippets** read from the sidecar only for actual hits; hits
jump to Scribe. Selects export: FCPXML stringout or CSV into
`~/Movies/control-z/index`. Honest limitation, stated in the UI: words, not
meaning — no embeddings; scan on demand, not a daemon.

## Slate (`slate/`)

`lowerthird.py` — one composition **group** (plates, accent, two lines,
shadow blurred from the group's own alpha) built per look at 2× supersample,
animated per frame (slide/rise/fade, cubic ease-out), Lanczos down. Styles:
bar / block / line / clean. Position is title-safe-relative; `from_dict`
clamps everything. Fonts: system discovery (`fonts.py`, cached), name or
path, no bundling. `render.py`: **ProRes 4444 with real alpha** via PyAV
(prores_ks encodes `yuva444p12le`), PNG hold frame, GIF with adaptive
palette + hard alpha at 128 and an honest note (256 colors, web). The suite
preview endpoint renders half-size **through the same Renderer** — WYSIWYG
by construction — with optional safe-area cages. `generators.py`: bars+tone
(ffmpeg smptehdbars + −20 dBFS sine), countdown leader (numeral + sweep +
beep each second, PyAV frames + soundfile wav, ffmpeg mux), program slate
card (PNG + optional held ProRes still).

## Suite integration

Rail: tools (8 diamonds) / community (2 squares) / suite (+ **About**).
Home: three doors — Grabber joins Prep; Make holds Highlighter, Index,
Slate; `.door.make` gets its own dark-umber surface. About: narrative,
covenant with meanings, build numbers from `/api/app`, the site footer's
credits verbatim. All four registered in `server.py`; scripts + packages in
pyproject; `pillow` joins requirements (Slate's type).

## Known gaps (honest)

- Grabber queue concurrency is the suite's single FIFO worker (the old app
  ran 2 downloads at once). Fine for stations; revisit if it hurts.
- Highlighter's segment-level keep/drop is the edit grain; word-level trims
  belong to the EDL in Resolve.
- zoomshare depends on Zoom's page shape (as Puppeteer did); failures name
  the step so the fix is a 10-minute regex, not an archaeology dig.
- Index thumbnails use frame 24 via the shared frame service; audio-only
  rows show a hidden thumb box.
- GIF alpha is 1-bit by format law; the UI says "web use, cut with the
  ProRes."
