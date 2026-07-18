# Community Memory — HANDOFF (lane B)

Wave 1 is landed on `lane/memory`: ingest → pipeline → corpus store → meeting
pages → cross-corpus search with jump-to-timestamp playback, working end to end
in the suite UI on two real meetings, with tests. Per PARALLEL, lane A merges
`lane/memory` → main.

Re-merged `origin/main` (1.6.0, Publisher live): the three slots reconciled
(server.py import/register kept; `memory.js` tag carries the new `?v={{v}}`
cache-bust; core.js flip kept beside Publisher's). Detection seam **swapped** to
`czcore.moments` now that it landed — `memory/detect.py` and `memory/ingest.py`
import it directly. Suite green at 320 tests.

## landed (what works, how to see it)

Run `.venv/bin/python -m suite --serve` → http://127.0.0.1:8300/#memory.
(Live caption fetch needs SSL working — see **asks** #4; the relay is what
actually pulls transcripts here.)

- **The tool exists on the rail.** `core.js` memory entry flipped `ready:true`;
  `server.py` registers `register_memory`; `index.html` loads `memory.js`. The
  three single-line slots PARALLEL names, nothing else in A's files.
- **The corpus** — one SQLite file at `media_dir("memory")/corpus.db`: meetings
  + diarized segments (FTS5 for words), a local lexical vector per segment
  beside them (Qdrant → "embeddings beside the store"), three-tier dedupe
  (deterministic id → canonical URL → media hash → transcript-shingle Jaccard).
- **Ingest, captions-first** (as Stephen asked, like Highlighter): a URL's
  published captions come straight in (watch page → yt-dlp → BIG's relay if the
  Settings switch is on); Scribe ASR runs only for a **local file** the user
  brings in. A URL with no captions is a calm `no_transcript`, never a runaway
  6-hour download. Every stage is one `JobManager` job → it shows in the Queue.
- **`POST /api/memory/submissions`** `{url|path, town?, body?, date?}` →
  `{meeting_id, status:"exists"|"queued"}`, dedupe as specified. This is the
  "Send to the Record" endpoint. **`POST /api/memory/context`** `{texts:[…]}` →
  `{issues:[], prior:[…], stats}` (prior = related-language search; `issues`
  stays empty, honestly, until the issue engine).
- **The long view** — cross-corpus keyword + related-language search, every hit
  time-coded; click → the meeting opens and **jumps to that second**: a YouTube
  embed seeked by postMessage for caption meetings, the audio+canvas viewer for
  local ASR files.
- **Meeting page** — follow-along transcript, the extractive reading (brief,
  entities, topics, motions/decisions, participation, moments), and a summary
  card that is generative *only* with the user's key (labeled with its model)
  and extractive otherwise — the fallback stands alone. BETA badge + "supplements
  the official record, never replaces it" on every surface.
- **Verified on two real meetings:** Brookline Select Board, May 19 (7,312
  segments) and May 12 (9,131), 12.1 hours, via captions. Searching "affordable
  housing" / "climate" lands inside the embed at the moment they're discussed.
- **Tests:** `tests/test_memory_{embed,store,ingest,analyze,api}.py` — 36 tests,
  offline (no ASR, no network; media root monkeypatched, llm mocked for the
  generative branch). Full suite: 307 green.

## next (what B starts after merge)

- **The issue engine** (specs/14 P0 №4): cluster segments per town → LLM-labeled
  canonical Issues with aliases → incremental assignment → steward merge/split →
  **threads + resurfacings** and **the long view** issue timeline. Then fill in
  `context.issues`. After that: documents (PDF), the Vote Ledger, cross-meeting
  reels, the infographic maker.

## asks (changes in A-owned files — exact, minimal)

1. **`pyproject.toml` `[tool.setuptools] packages`:** add `"memory"` to the list
   (alongside the other tool packages). Until then `suite/tools/memory.py`
   inserts the repo root on `sys.path` as a guarded fallback so `import memory`
   resolves regardless of cwd — delete that block once `memory` is declared.
2. **Detection seam:** ✅ done — swapped `memory/detect.py` + `memory/ingest.py`
   to `czcore.moments` after it landed on main.
3. **The buttons** (optional, when convenient): Highlighter's / Publisher's
   "Send to the Record" → `POST /api/memory/submissions` with `{url}` or
   `{path}`. The endpoint is stable and live now.
4. **Not a code ask — a machine note:** on this box Python `urllib` SSL fails
   (`CERTIFICATE_VERIFY_FAILED`), which kills `fetch_vtt` and the relay, and
   yt-dlp's `--skip-download` caption path has no JS runtime (deno) — so live
   caption fetch fell through until I set `SSL_CERT_FILE=<certifi>` for the
   server (in `.claude/launch.json`, which is gitignored — local only). Fix on
   the machine: install Python's certs (the "Install Certificates" step) or
   point `SSL_CERT_FILE` at certifi. With SSL working, BIG's relay pulls full
   transcripts; nothing in Memory's code needs to change.

## fragments (changelog-ready, house voice)

- The telescope opens: Community Memory keeps the record — a meeting's captions
  come straight in, the whole corpus is searchable, and every hit is a second to
  jump to.
- Captions first, like the analyzer: Memory reads a meeting's published words
  the moment you paste the link, and only asks Scribe to listen when a file has
  no transcript of its own.
- One search across every meeting, and the video lands on the moment — the long
  view learns to point back at the tape.
- Every reading shows its receipts and says it's beta: Memory supplements the
  official record, and never pretends to be it.
