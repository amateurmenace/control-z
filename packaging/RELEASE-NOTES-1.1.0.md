# control-z Suite 1.1.0 — ten tools, on paper, with a face

The suite grew from six tools to **ten**, turned **paper-light**, and got
its icon: a caret over an amber z — *control z*, read aloud. The app and
the DMG volume both wear it.

## New since 1.0.0

- **Community Highlighter** — the community-highlighter web app's shape on
  the suite's local engine: paste a meeting URL and it's readable **before
  any video downloads** (captions seed the transcript; preview streams via
  YouTube embed). Executive brief with clickable timestamps (extractive —
  the meeting's own sentences), reel-style presets, a timeline editor,
  word cloud, search with sparkline, decisions/entities/question-flow
  analytics, ask-the-meeting (retrieval, labeled), and **smart downloads**:
  the whole recording or only the kept sections, stitched into a reel.
- **BIG Video Grabber** — CivicClerk portal search for any town (Brookline
  out of the box), fetches through yt-dlp **and its own Zoom/zoomgov share
  resolver**, then conforms recordings for air with hardware encoders.
- **Index** — the footage librarian: point it at folders, search in plain
  words, get time-coded transcript hits, export selects as an FCPXML
  stringout Resolve imports as a timeline.
- **Slate** — the station graphics kit: a lower-third maker (live preview
  through the export code path) shipping **ProRes 4444 with real alpha**,
  PNG, and honest GIF; plus SMPTE bars+tone, countdown leaders, and program
  slates.
- **Home is three doors** — Prep / **Make** / Finish — under one line:
  *Make Something.* An **About** page tells the story. Drag a clip into any
  tool's empty viewer and it opens.
- **The fetch stack**: yt-dlp **nightly**, checked every time a fetch tool
  opens (the chip says what it found). Optional **Webshare residential
  proxy** (Settings → fetch network) — the same account the web app uses —
  for YouTube's caption gating; plus a zero-setup **community caption
  service** fallback (the web app's own public transcript engine, off by
  one switch for the fully independent).

## Requirements (unchanged, stated plainly)

- **Apple silicon only** (arm64), macOS floor measured from the shipped
  binaries and written into the plist.
- No account, no telemetry, no cloud processing. Models download on first
  use behind license cards with pinned SHA-256s. The only network calls are
  the ones you ask for: fetching a video, checking the yt-dlp nightly,
  downloading a model — and, if left on, the community caption fallback
  (public video URL only).

## Honest limitations

- Stencil's GPU runtime (torch + SAM 2) still isn't in the DMG — run from
  source for click-to-matte; the page in the app says so.
- Highlighter's edit grain is the paragraph/clip; frame-accurate trims
  belong to Resolve via the selects EDL.
- The Zoom share resolver depends on Zoom's page shape (as the old
  Puppeteer app did); when Zoom redecorates, each step fails naming itself.
- GIF exports are 256 colors with 1-bit alpha by format law — the ProRes
  carries the real thing.
- Windows builds: not yet — next milestone.

## About the model asset on v1.0.0

`realesrgan-x4.onnx` stays attached to the **v1.0.0** tag because shipped
apps download it from that exact pinned URL (license card + SHA-256 in the
app). You never need to fetch it by hand, and this release does not
duplicate it.

## OpenFX siblings

**Hush** (denoise) and **Speak** (film character) install into Resolve from
this app's Install-OpenFX page; their latest plugin bundles are mirrored on
this release for one-stop download.
