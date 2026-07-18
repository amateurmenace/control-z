# lane/desk — HANDOFF

The desk lane: give the production wing what the record got — a data spine
(Index), composition (the batch line), and the civic wing's polish. Owned
files: `czcore/sidecars.py` (new), `indexer/`, `suite/tools/indexer.py`,
`suite/static/js/index.js`, the eight production `*.js` pages,
`tests/test_index_desk.py`. Shared files by the single-slot law; version
bumps happen at merge, not here.

## landed (what works, how to see it)

Run `.venv/bin/python -m suite --serve` → `/#index`.

- **The sidecar law** (`czcore/sidecars.py`): one table of every suffix the
  tools leave beside a source (words, captions, cut, moments, insight, kit,
  pivot, clear), one reader. Any tool may ask what a clip carries without
  re-learning the naming.
- **The catalog knows.** Scan records each clip's carried kinds; a new
  sidecar refreshes the row via signature; pre-1.8 catalogs grow the column
  without ceremony. Rows hand the UI a clean `carries` list; `stats()` gains
  per-kind `coverage` + `wordless`; `gaps(kind)` lists the work (words gaps
  exclude silent clips — nothing to transcribe, listing them would be lying).
  `scan(only=[paths])` is the scoped rescan (never declares absence).
- **The coverage band** on the shelf: clips · hours · per-kind counts in the
  owning tool's accent · "✎ words for the N without" (confirms scale out
  loud first). Row chips say what each clip carries; filter pills know the
  kinds; a time-coded hit now lands Scribe on the moment
  (`go("scribe", {openPath, t})` — scribe.js seeks after load).
- **The batch line, first road** (`POST /api/index/transcribe-missing`,
  optional `{paths}`): Scribe's engine imported never reimplemented, one
  queue job, per-clip failures named, a missing runtime aborts with the
  install sentence instead of failing N times. The selects panel's
  "Words for ticked" sends a hand-picked list down the same road.
- **Verified live** against a real 823-clip / 13.1 h library: band counts,
  scoped batch wrote words with local whisper-base, "crosswalk vote" found
  the clip that says it, hit → Scribe with the sidecar loaded. **453 green**
  (11 new in `tests/test_index_desk.py`; the old 15-column INSERT fixture in
  `test_indexer.py` gained the 16th column).

## landed (wave 2 — the road)

- **The road** (`POST /api/index/road` `{paths, stages}`;
  `GET /api/index/road-stages` says what can run today and why not).
  Tick clips, pick stages — words/rescue/reframe-9:16 — one queue job,
  clip-major order. `_road_plan` (pure, tested) rules before engines run:
  no sound → no words, no picture → no reframe, unplugged → never joins,
  done → skipped with the reason said; a fully-done road refuses at submit
  with every skip named. Engines are the tools' own: Clear at road
  defaults (de-hum if found + de-click only — the road preps, the craft
  stays in the tool; no remux), Pivot analyze→render h264 reusing a 9:16
  sidecar when present. Scoped rescan after, so chips/band count the new
  work immediately. Verified live end-to-end; re-run refused. **457 green**
  (4 new road-plan tests).

## landed (wave 3 — the road grows up)

Run `.venv/bin/python -m suite --serve` → `/#index`, right rail.

- **Rise joins the road** as a fourth stage (`to HD`). The honest target is
  chosen per clip, not silently: a clip at or above 720p is left alone
  (`RISE_ROAD_CEILING`) with the reason said — *"already 1080p — Rise's craft,
  not the road's"* — and only standard-def footage takes a modest ×2 lift at
  the h264 preset (`_run_rise_x2`, mirrors rise.video.upscale_video). The road
  preps; 4K and model choice stay Rise's own page. `_rise_out` skips a clip
  already lifted. **Proven live:** a 480p fixture dispatched and rendered ×2
  (Real-ESRGAN when present, Lanczos otherwise); a 1080p clip refused at submit
  with the exact skip sentence (HTTP 409).
- **Road presets** — one-click roads above the stage picker: **prep the shoot**
  (words + rescue) and **make it social** (words + reframe 9:16). Named buttons
  drive the same `_road_plan`; a preset ticks its available stages, the operator
  still presses Send (no long job fires behind their back). `ROAD_PRESETS` +
  `GET /api/index/road-stages`.presets.
- **Standing orders — a folder that tends itself.** Index already watches
  folders; a standing order gives one a job: *"when new clips land here, send
  them down this road."* `GET/POST /api/index/standing`. Each order baselines
  the clips already present (the folder's past, not its work), then fires only
  on what newly lands, sending each fresh clip down its road **once** (handled
  set). A daemon clock (`_orders_clock`, Grabber's scheduler shape, sleeps
  first so tests never trip it) ticks every 10 min; *run now* forces a tick.
  Every order is visible, pausable (a real toggle), and says what it did last
  run. `_start_road` is now shared between the Index page and the clock — one
  engine, one set of rules. **Proven live end-to-end:** created an order, a new
  spoken clip dropped into the folder, *run now* scanned + dispatched, the road
  transcribed it (whisper large-v3-turbo, exact text), the sidecar landed, the
  order's note read *"1 clip sent down words."* Cleaned up after.
- **Catalog:** `living_paths(folder=None)` — the clock's "what still exists
  here" reader. **510 green** (7 new road/preset/standing tests in
  `tests/test_index_desk.py`).

## landed (wave 4 — craft depth)

- **Gemini is the desk's third BYO key** (`czcore/llm.py`). A key's own shape
  names its provider now: `sk-ant-…` Anthropic, `AIza…` Gemini, else OpenAI.
  Chat and vision both speak Gemini's `generateContent` (contents +
  systemInstruction; the key rides the `x-goog-api-key` header, never the URL
  query), the candidate text is parsed, and the spend lands in the same audit
  ledger (`usageMetadata`). Env is `GEMINI_API_KEY`/`GOOGLE_API_KEY`; defaults
  `gemini-2.0-flash`, 1M window. **Proven** with a fake-server round-trip
  (chat + vision, request shape, header auth, ledger) and live (saving an
  `AIza…` key reports `provider: gemini`). *This is the desk user's key path
  only — the Studio's server bill is a separate world (specs/17 §3).*
- **Slate reads the station brand** (`publisher/brand.py`, read-only — one
  brand, every lower third). `/api/slate/status` now carries `brand`: accent,
  plate, style, hold, line2, station, and a `configured` flag so a fresh
  install keeps Slate's own look until a brand is actually set. The page adopts
  the visual defaults on load and offers "match station brand." **Proven
  live:** the lower third came up mint (#3A9E8E), 4.5s hold, "community media"
  on line 2 — the station's brand, not Slate's amber default.
- **Scribe tighten — strip fillers, close silences** (`scribe/tighten.py`,
  `POST /api/scribe/tighten`). Extractive and visible before commit: every
  "um/uh/er…" and every silence longer than a threshold is listed with its
  timecode first; only on Write does it leave a `<stem>.tighten.edl` — a
  CMX3600 cut list of what survives, a proposal you import and relink. **The
  source is never touched** (tested + proven live: a 4-filler, 1-silence
  fixture → 5-keep EDL, the wav byte-identical after).
- **530 green** (+20: Gemini round-trip + config, brand defaults, the whole
  tighten module + route).

## asks (A-owned / shell files — minimal, marked, low-conflict)

- **`suite/static/js/services.js`** (the Settings/Services shell page, not one
  of my eight): I made a small honest edit so the new Gemini key path is
  visible and truthful — the AI-key blurb now names Anthropic/OpenAI/**Google
  Gemini**, the placeholder accepts all three shapes (`sk-ant-… · sk-… ·
  AIza…`), the status line shows the **provider** (`active — gemini (…key ·
  model)`), and the audit's `LLM_PRICES` gained Gemini rows. Without this the
  shipped feature was invisible/dishonest (covenant: provenance as UI). Flagged
  here for transparency — reshape freely; `llm.status()` already returns
  `provider`. No other shell file touched.

## landed (wave 5 — the coherence walk, thrust 1)

Walked all eight production pages against the civic wing's bar. The finding
list came from a fan-out audit (one reader per page) + an adversarial verify
pass (each candidate re-checked against the code, false-positives dropped):
**21 confirmed findings, every one fixed.** No page ships a control that
pretends. Grouped:

- **Honest progress.** Stencil's SAM pass and Clear's rescue emitted per-frame
  text but no fraction, yet pinned their bars at a fake 50%/55% — now they show
  an honest indeterminate bar (reuses czProgress's slide keyframe, reduced-
  motion gated). Slate's render bar resets each run and caps below full until
  the job is actually done, so a per-format reset (ProRes→GIF) never reads as
  "done, then restarted." Added the missing reduced-motion gate on
  `.czprog-bar i.indet` (a higher-specificity override the guard had missed).
- **Errors that name a remedy, not silence.** Stencil's runtime probe and
  Depth's preview catch swallowed real failures (a dead Propagate button; a
  blank overlay when the model isn't downloaded) — both now say what broke and
  what to do. Rise's batch failures surfaced only a bare "error" chip — now the
  reason and clip name land in a toast and the report. Pivot surfaces a
  corrupt-sidecar warning instead of blanking it, and clears the stale `.err`
  red on the next clip. Clear validates a custom LUFS target *before* running
  the whole pass, not after a late float() throws the work away.
- **`toast(…, true)` was crying wolf.** Stencil's low-confidence heads-up on a
  *successful* run rendered as a red error toast — now neutral.
- **Keyboard grammar.** Scribe and Clear gained the house transport keys —
  Space plays/pauses, ←/→ seek ±5s — guarded against typing/editing, matching
  Highlighter. (Proven live: ←/→ seek the transcript clock; Space is blocked
  only by the headless browser's autoplay policy.)
- **Fresh clip, clean slate.** Scribe's `open()` now resets the export/pull/
  tighten sections, the pull rows, the report and the progress bar, so clip B
  never inherits clip A's UI.
- **Affordance + contrast.** Clear's pre-pass monitor chips read as
  not-yet-available (a real `[data-off]` style). Slate's preview HUD got a
  solid dark panel + light text so its readout — and its "couldn't draw that…"
  error — clear AA contrast over the light checker. Slate's dead font-preselect
  ternary now actually preselects the first installed house font. My own Index
  additions were in the audit too: "Words for ticked" now guards against
  re-entry, and a failed standing-order "run now" resets its button label.

**530 green**, no regressions (JS/CSS + the new `scribe/tighten.py` route from
wave 4 are the only moving parts). Verified live: no console errors on the
reloaded pages; the reset + keyboard proven in the browser.

## landed (wave 6 — the drain client, gated, thrust 5)

The desk side of specs/17 §6.4 — a desk that volunteers to transcribe the
Studio's caption-less meetings on its own hardware. Built and tested; **dormant
until the Studio exists.**

- **`czcore/drain.py`** — config (0600 key, env override), a `DrainClient`
  (stdlib urllib, key in the `X-Studio-Key` header) with `poll`/`claim`/
  `post_transcript`, `run_once(client, transcribe)` (poll → claim → transcribe
  → post, honest about the empty-queue and lost-claim cases), and
  `desk_transcribe` (the real path: `czcore.ytdlp.download` + the vendored
  ffmpeg + Scribe's engine — ASR stays Scribe's, never reimplemented).
- **`suite/tools/drain.py`** — `/api/drain/{status, config, run-once}` and a
  poller that **sleeps first and does nothing until configured + enabled** (so
  tests and a fresh launch never trip it).
- **Settings section "Studio · lend this desk"** — reads *"waiting for the
  Studio to exist"* until a steward sets a URL + key and switches it on; the
  enable toggle is disabled until then. Proven live.
- **7 tests** (`tests/test_drain.py`) drive the whole flow against a **fake
  Studio** (poll/claim/post, steward-key check) — no real Studio, no network,
  no whisper. Config masking + the "waiting" surface pinned. **537 green.**

## asks (A-owned / shell + the Studio session)

- **Shared single-slot (server.py):** one import + one `register_drain(...)`
  line, alphabetical between depth and grabber. Standard slot; flagged for
  transparency.
- **`suite/static/js/services.js`** (shell Settings page): the Gemini status
  edit (wave 4) **and** the new "Studio · lend this desk" section live here —
  the drain's UI belongs in Settings by the brief. Marked, low-conflict;
  reshape freely.
- **THE STUDIO CONTRACT (for the specs/17 session) — this is a PROPOSAL, not a
  spec.** specs/17 §5's `AsrTask` names the object without fields, so the desk
  built to the smallest shape the flow needs. **Confirm or revise, then tell me
  in "state of main":**
  - `GET  {base}/api/asr/next?desk={desk}` → 200 `AsrTask` | 204 empty
  - `POST {base}/api/asr/{id}/claim {desk}` → 200 `{ok:true}` | 409 `{ok:false}`
  - `POST {base}/api/asr/{id}/transcript {desk, model, transcript}` → 200 `{ok:true}`
  - auth header `X-Studio-Key: {key}` on every call
  - `AsrTask := {id, meeting_id, town, source_url, title?, duration_hint?}` —
    `source_url` is the media the desk fetches itself (no video hosting, §3);
    `transcript` is Scribe's `Transcript.to_json()`.
  - **Objection/ask:** the spec is silent on the desk's *identity + trust* — is
    `desk_id` (hostname) enough, or does a drain need a registered token per
    desk? And is a *lease TTL* on claim wanted (a desk that dies mid-transcribe
    shouldn't strand a task)? Both feel like real gaps; deferred to you.

## next

- The local model cards (thrust 3 — scaffold + conversion recipe; hosting is
  an external human step).

## asks (A-owned files; single lines, in your hands)

- None yet. czcore gained only the NEW file `czcore/sidecars.py` (the lane-C
  new-file precedent). No core.js/index.html slots were needed.

## fragments (changelog-ready, house voice)

- **Index knows what every clip carries.** The catalog reads the whole
  sidecar law, the coverage band counts the library like Memory counts the
  record, and every gap is one click of work: "words for the N without"
  runs Scribe's engine over the wordless as one queue job — silent clips
  honestly excluded, failures named. Ticked clips take the same road.
- A time-coded search hit now lands Scribe on the moment instead of
  dropping the timestamp on the floor.
- **The road.** Tick clips, pick stages — words, rescue, reframe 9:16 —
  and one queue job walks each clip through the tools in order, skipping
  what's already made with the reason said; run it twice and the second
  run is a sentence, not a queue entry.
- **The road grows up.** Rise joins as a fourth stage — but it never 4×'s
  an archive: it lifts standard-def footage a modest ×2 toward HD and leaves
  anything already 720p-or-better to Rise's own page, saying so. Two
  one-click roads sit above the picker — *prep the shoot* (words + rescue)
  and *make it social* (words + reframe). And a folder can now tend itself:
  set a **standing order** and clips that land afterward wake up worked —
  overnight a dumped shoot is transcribed and rescued by morning, each
  standing order visible, pausable, and honest about its last run.
- **The desk's own key learns a third shape.** Paste an Anthropic, OpenAI,
  or now **Google Gemini** key and the suite reads the provider from the key
  itself — Gemini's chat and vision both counted in the same AI audit, the
  spend always in view. Still bring-your-own, still labeled, still an
  extractive fallback underneath.
- **One brand, every lower third.** Slate reads the station's brand kit as
  its defaults — the accent, plate, style and hold you set once in Publisher
  now dress every lower third, without re-typing.
- **Scribe learns to tighten.** One read of the words finds every "um" and
  every long silence, lists them with their timecodes first, and — only when
  you say so — leaves a cut list of what's left. A proposal you import, never
  a cut to your footage.
- **The desk walks its own eight pages.** A page-by-page coherence pass in the
  house voice: progress bars that no longer pretend to measure, errors that
  name a remedy instead of going quiet, transport keys (space, arrows) on the
  players that lacked them, a fresh clip that never wears the last clip's UI,
  and a handful of contrast and affordance fixes. No control that pretends.
- **A desk can lend itself to the record.** When the Community AI Studio
  exists, a meeting that arrives without captions can be transcribed by any
  desk running the suite — on its own hardware, with Scribe's engine, no cloud
  GPU and no bill — and posted back. The wiring is here and tested against a
  stand-in Studio; until the real one exists, Settings says so plainly.
