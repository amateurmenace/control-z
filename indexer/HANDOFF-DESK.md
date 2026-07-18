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

## next

- The batch line, further roads: Clear→Pivot/Rise chains from a selection
  (per-tool params need a design pass; engines exist).
- The coherence pass (thrust 3): czProgress/empty-state/keyboard grammar on
  the eight production pages.

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
