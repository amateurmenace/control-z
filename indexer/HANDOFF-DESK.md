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

## next

- The coherence pass (thrust 1): walk the eight production pages in the
  browser against the civic wing's bar; fix what the walk finds.
- The local model cards (thrust 3), the drain client (thrust 5, gated), and
  the craft-depth picks (thrust 4).

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
