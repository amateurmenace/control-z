# Community Memory — HANDOFF (lane B)

**Wave 2 (the issue engine) is landed on `lane/memory`.** The telescope now sees:
the record clusters the topics that recur across meetings, names them, tracks
every appearance, and lets a resident follow a thread and catch up on an arc in
one sitting — the long view, end to end. Wave 1 (ingest → corpus → search →
meeting pages → jump-to-timestamp playback) is underneath it, unchanged. Per
PARALLEL, lane A merges `lane/memory` → main.

No shared-file edits this wave: the three single-line slots were already in from
wave 1 (server.py register pair, index.html `?v={{v}}` tag, core.js `ready:true`).
Everything new lives in lane-B-owned files (`memory/`, `suite/tools/memory.py`,
`suite/static/js/memory.js`, `tests/test_memory*.py`). New issue/thread routes
are new `/api/memory/*` endpoints; the two stable contracts kept their shapes.

## landed (what works, how to see it)

Run `.venv/bin/python -m suite --serve` → http://127.0.0.1:8300/#memory, press
**↻ rebuild** on "the long view" panel (a JobManager job — shows in the Queue).

- **The issue engine** (`memory/issues.py`). Issues are **phrase-anchored**, not
  vector-partitioned — a measured choice: the suite's embedding is lexical and
  civic meetings share too much baseline vocabulary, so a cosine threshold
  collapses everything into one "a public meeting" blob (I measured it). Instead
  the *sticky* phrases that recur across meetings (PMI-filtered: `vision zero`,
  `short term rentals`, `golf course lighting`, not `important work`) are the
  anchors; phrases that co-occur merge into one issue; each carries a **keyword
  set** that is the visible, auditable reason a segment belongs. Assignment is
  keyword-first (precise, high-recall); the cosine fallback sits high, so an
  unmatched segment waits in a **candidate queue** for a steward — the spec's
  design. Person-shaped anchors never open an issue (the no-person-aggregation
  non-goal, kept in code).
- **The long view page.** The landing grew a "long view" issue rail (every issue,
  sorted by reach, follow ☆) and "still watching" (your threads + a copyable
  digest). Open an issue → a **horizontal timeline**: a time axis, one node per
  meeting, moments as beads, votes as ◆ milestones — and **every bead deep-links
  into playback** (reuses the search→seek path: YouTube embed by postMessage,
  the audio+canvas viewer for local files). Verified in a browser: a bead on the
  Legislative Agenda timeline lands the May-12 tape at 2:03:34.
- **Threads + resurfacings.** Follow from a star or straight from a search
  ("follow this" → `mint_from_query`, which attaches to a near issue or mints a
  new one seeded from the search). On a new meeting the pipeline assigns it to
  the existing issues (a new stage in `ingest.run`) and, for any *followed* issue
  it reopens with a newer meeting, writes a **resurfacing event** with a
  one-paragraph "what changed since last time" delta (generative with a key,
  extractive otherwise). Notifications are in-app: a bell counts unseen
  resurfacings; the **"still watching" digest** is the local covenant for the
  spec's email — a plain markdown roundup you copy, nothing sent anywhere.
- **Steward tools.** merge (folds aliases + segments, tombstones the source →
  `merged_into`), split (lifts one meeting into its own issue), rename (+ aliases
  → re-assigns), promote a candidate, forget. All as `/api/memory/issue/*`.
- **`/api/memory/context` now fills `issues`.** Same shape, `prior` unchanged;
  `issues` carries the tracked topics a meeting's agenda/transcript language lands
  on, scored keyword-first (Highlighter's panel currently reads `r.prior` — see
  **asks** #2 to light up `r.issues`).
- **Acceptance MET.** On the two real Brookline meetings, recall of literal true
  appearances: **Vision Zero 100%, Golf Course 100%, short-term rentals 83%** —
  all ≥ the spec's 80% (hand-audited). Rebuild draws 41 real issues (vision zero,
  overlay zoning, sewer rates, permit fees, immigration enforcement, blue bikes,
  dark skies…) from 12.1 hours.
- **Tests:** `tests/test_memory_issues.py` (18: anchors/PMI/name-filter,
  discover, incremental assign, resurfacing+delta, merge/split/rename, mint,
  digest) + issue/thread/steward/context routes in `test_memory_api.py`. Full
  suite **359 green** (was 334; +25). Offline: no key (extractive paths), no
  network, throwaway SQLite.

## next (what B starts after merge)

- **Live cross-time proof.** Resurfacings are unit-tested but haven't fired on
  real data: both meetings are May 2026 a week apart, so rebuild's baseline is
  already the latest. Ingesting a Brookline meeting dated *after* May 19 (captions
  permitting — see **asks** #3) would fire a real resurfacing + delta on a
  followed thread. The engine already auto-assigns every new ingest, so this is
  "add meetings," not "add code."
- **P1 №11 Documents** (PDF warrants/plans/budgets → chunk, embed, link to
  issues, interleave on the timeline with page cites). **№12 Vote Ledger** — the
  timeline already surfaces votes-as-milestones (decisions within ~90s of an
  issue's beads); the ledger is the per-issue / per-member roll-call grid on top.
  **№13 cross-meeting reels**, **№14 the infographic maker**.

## asks (changes in A-owned files — exact, minimal)

1. **`pyproject.toml` `[tool.setuptools] packages`:** add `"memory"` (still
   missing; `"publisher"` is there). Until then `suite/tools/memory.py` inserts
   the repo root on `sys.path` as a guarded fallback so `import memory` resolves —
   delete that block once `memory` is declared. The one thing that would break a
   packaged (PyInstaller) build; dev-serve and tests already work via the fallback.
2. **(Optional) Light up prior-appearance *issues* in Highlighter.** `POST
   /api/memory/context` now returns real `issues: [{id, name, n_meetings,
   n_segments, first_seen, last_seen, score, following}]` alongside `prior`.
   Highlighter's panel reads `r.prior` today; rendering `r.issues` too would give
   the spec's "this topic: N appearances across M bodies since YYYY" line and a
   door into the issue timeline (open Memory with `{openIssue: id}` — the page's
   onshow already routes it). Zero lane-B edits needed; the shape is stable.
3. **Machine note (unchanged from wave 1):** live caption fetch needs working SSL
   — `urllib` fails `CERTIFICATE_VERIFY_FAILED` on this box, yt-dlp's caption path
   has no JS runtime (deno), and the community relay is opt-in (off by default).
   `.claude/launch.json` sets `SSL_CERT_FILE`=certifi for `-m suite` (gitignored,
   local). With SSL working + the relay switch on, more meetings come straight in
   and nothing in Memory's code changes.

## fragments (changelog-ready, house voice)

- The telescope learns to see: Memory finds the issues that recur across
  meetings — vision zero, the golf course lighting, short-term rentals — names
  each from the record's own words, and tracks every appearance. Anchored in the
  words a meeting actually says, never a guess about anyone's position.
- Follow a thread and the record keeps watch: star an issue (or a search), and
  when it resurfaces on a new agenda Memory tells you what changed since last
  time — a paragraph, generative with your key, extractive without one.
- The long view is a line you can walk: an issue's timeline lays every meeting
  along a time axis, its moments as beads and its votes as milestones, and every
  one is a second to jump to — the tape lands on the moment.
- Steward-tended, not machine-final: merge two issues, split one that was fused,
  rename or promote a candidate — and the record remembers its own edits.
- Still watching, on your terms: a plain digest of your threads you can copy and
  paste anywhere. No email, no account, nothing sent — the covenant, kept.
