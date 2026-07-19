# Running publicrecord.studio

Everything you need to run the record, find out what it is doing, and fix it
when it stops. Written to be read at 11pm by someone who did not build it.

**Provisioned 2026-07-19.** Project `publicrecord-studio`, region `us-east1`,
billed to *Firebase Payment*, budget **$100/mo** scoped to this project alone.

---

## 1. The consoles

| What | Where |
|---|---|
| **Project home** | <https://console.cloud.google.com/home/dashboard?project=publicrecord-studio> |
| **The service** (logs, revisions, traffic) | <https://console.cloud.google.com/run/detail/us-east1/record-api/metrics?project=publicrecord-studio> |
| **The jobs** (migrate, seed, press, poll) | <https://console.cloud.google.com/run/jobs?project=publicrecord-studio> |
| **The database** | <https://console.cloud.google.com/sql/instances/record-pg/overview?project=publicrecord-studio> |
| **The edition bucket** | <https://console.cloud.google.com/storage/browser/publicrecord-edition?project=publicrecord-studio> |
| **Secrets** | <https://console.cloud.google.com/security/secret-manager?project=publicrecord-studio> |
| **The bill** | <https://console.cloud.google.com/billing/01BA3F-D33117-58BB2B/reports?project=publicrecord-studio> |
| **Logs, everything** | <https://console.cloud.google.com/logs/query?project=publicrecord-studio> |
| **The image** | <https://console.cloud.google.com/artifacts/docker/publicrecord-studio/us-east1/record?project=publicrecord-studio> |

**The API:** <https://record-api-907309358085.us-east1.run.app>
**The steward console:** <https://record-api-907309358085.us-east1.run.app/steward>
**The reader:** <https://publicrecord.studio> *(DNS points at GitHub Pages;
the Pages custom domain is not switched over yet — see §8)*

---

## 2. Is it alive?

One command answers most questions:

```bash
curl -s https://record-api-907309358085.us-east1.run.app/api/health | python3 -m json.tool
```

It is deliberately honest about **halves**. A green light over a dead neural
index is how a degraded search ships for a month, so this never reports one.

- `ok: true` and a `record` block with counts — the corpus is reachable
- `neural.available: true` — the key is wired. If this ever reads `false`, the
  `reason` names the cause, and search silently falls back to words with an
  honest line rather than erroring.
- `steward_console: true` — the console is wired. A steward route without a
  valid token answers **401** ("sign in"); a verified Google account that is not
  on the allowlist gets **403** ("you may not"), because retrying the sign-in
  cannot help and the message should not send someone round a loop. If this
  key ever reads a sentence instead of `true`, that sentence names the missing
  variable and every steward route is 503 — it fails *closed*, never open.
- HTTP 503 with `"the corpus is unreachable"` — the database is down or the
  connector is broken. Go to §6.

---

## 3. The shape of the thing

Two halves, and the split is the whole design.

**The reader is static.** A pressed edition — JSON and HTML, no backend — that
carries the meetings, issues, timelines, ledgers and a prebuilt search index.
It reads with the database gone, the API dead, and the aeroplane mode on. This
was tested by stopping Postgres and walking the site; it searched all 16,443
segments and never noticed.

**The API is small on purpose.** It carries only what an envelope of files
structurally cannot: semantic search (needs a vector index at query time),
freshness, live submissions, and the steward console. If the API is down,
**the record still reads.** That is not a consolation, it is the architecture.

So: *the API being down is not an outage of the record.* It is an outage of
search-by-meaning and of intake. Fix it calmly.

---

## 4. Adding meetings

Nothing ingests on its own say-so. A video becomes a meeting in three steps,
and a human is in the middle on purpose.

**1. The intake rules decide what is even a candidate.** A municipal channel
is not a meeting feed — Brookline posts *TV on TV* beside the Select Board;
Boston City TV posts a library dedication beside the BPDA. The rules are
**default-deny**: a video enters the queue only if its title matches a rule
that *names a public body*. No rule, no entry, no spend.

**2. Preview before you poll.** In the console, or:

```bash
curl -s -X POST $API/api/steward/preview \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"source": {...}, "limit": 15}'
```

It returns three lists — would-file, excluded, unmatched — and `would_cost`,
the number of meetings a real poll would file. **Nothing is written.** On
Boston City TV this reads: polled 15, would file 4.

**3. Approve.** The queue is at `/api/steward/submissions`; approving marks a
row for the pipeline rather than transcribing inline, so you are never holding
a browser open while a meeting processes.

### When a title is missed

Unmatched titles come back as **suggested rules** with the body name inferred
from the title's stable head. One click adds it. The taxonomy gets learned
from what the town actually posts instead of guessed in advance — which is
what the live polls proved necessary: Boston's council never says "Committee
on", it titles sessions `<Name> on <Date>`, and a literal rule missed five
real committees.

### The ceiling you will hit first

**YouTube's RSS feed is hard-capped at 15 items.** Not configurable. So:

- Nightly polling is **mandatory**, not a preference. Boston City TV posts
  about five items a day, so its window is roughly three days. A weekly poll
  loses meetings permanently.
- **Backfill is impossible through RSS.** Historical meetings need either a
  per-body playlist (low volume, high signal — `channel_feed_url` already
  accepts `PL…` ids) or the YouTube Data API.

---

## 5. Deploying a change

```bash
# from the repo root, after your commit
docker build --platform linux/amd64 -f record/Dockerfile \
  -t us-east1-docker.pkg.dev/publicrecord-studio/record/api:NEXT .
docker push us-east1-docker.pkg.dev/publicrecord-studio/record/api:NEXT
gcloud run deploy record-api \
  --image=us-east1-docker.pkg.dev/publicrecord-studio/record/api:NEXT \
  --region=us-east1
```

**`--platform linux/amd64` is not optional on an Apple-silicon Mac.** Without
it you build an arm64 image, Cloud Run refuses it, and the error names the
architecture rather than the flag.

**Rolling back** is instant and does not require a build:

```bash
gcloud run revisions list --service=record-api --region=us-east1
gcloud run services update-traffic record-api --region=us-east1 \
  --to-revisions=record-api-00001-f7d=100
```

Schema changes go through a numbered file in `record/migrations/` and:

```bash
gcloud run jobs execute record-migrate --region=us-east1 --wait
```

Migrations are applied once, recorded in `schema_migrations`, and each runs
inside a transaction. Running it twice is a no-op — that is asserted by a test,
because a command nobody dares re-run after a partial failure is a command
nobody runs at all.

---

## 6. When something is broken

### The API returns 503 and says the corpus is unreachable

```bash
gcloud sql instances describe record-pg --format="value(state)"
```

`RUNNABLE` means the database is fine and the problem is the connector or the
secret. Anything else — start it:

```bash
gcloud sql instances patch record-pg --activation-policy=ALWAYS
```

### Cold starts feel slow

`--min-instances=0` means an idle service costs nothing and the first request
after a quiet spell pays for the start. That trade is deliberate. If it becomes
annoying, `--min-instances=1` removes it and adds roughly $5–10/mo.

### Read the actual error

```bash
gcloud run services logs read record-api --region=us-east1 --limit=50
gcloud logging read 'resource.labels.job_name="record-press"' \
  --limit=20 --format="value(textPayload)" --freshness=1h
```

Failures in this codebase are sentences, not codes. If a log line does not read
like an English explanation, it came from a library rather than from us.

### A poll files nothing

Almost always the rules, not the connector. Run a **preview** — it shows
whether titles are landing in `excluded` (a rule is too broad) or `unmatched`
(no rule names that body). A poll that files zero and reports zero unmatched
means the feed itself returned nothing; check the channel id.

### The edition looks stale

`GET /api/freshness` returns the corpus fingerprint. If it differs from the one
in the served edition's `manifest.json`, a press is owed. Note the **edition
date is the newest meeting, not the press time** — that is deliberate, so the
bake stays byte-identical for identical input. A re-press with no new meetings
correctly shows an unchanged date.

---

## 7. The money

| Line | Est./mo | Notes |
|---|---|---|
| Cloud SQL `record-pg` | $10–30 | **the only line that bills while idle** |
| Cloud Run `record-api` | $0–5 | min-instances 0; idle costs nothing |
| Cloud Run jobs | ~$0 | seconds per run |
| GCS + egress | $1–5 | |
| Gemini embeddings | <$1 one-time, then pennies | see below |
| Artifact Registry | <$1 | |
| **Project budget alert** | **$100** | 50 / 90 / 100%, this project only |

### The Gemini key, and where it actually lives

**It is not in AI Studio, and it will not appear there.** AI Studio's key page
is a filtered view of keys created through its own flow, for projects it has
synced; this key was created with `gcloud` in a project AI Studio has not
picked up. Same underlying resource, different front door. The authoritative
view is the Cloud console:

<https://console.cloud.google.com/apis/credentials?project=publicrecord-studio>

It is listed as **`publicrecord gemini`**, and it is **restricted to
`generativelanguage.googleapis.com` only** — if it leaked it could call
nothing else. The value lives in Secret Manager as `record-gemini-key` and has
never been printed to a terminal or a chat.

To rotate it:

```bash
gcloud services api-keys create --display-name="publicrecord gemini 2" \
  --api-target=service=generativelanguage.googleapis.com \
  --project=publicrecord-studio
# then write the new string into a new secret version, redeploy, and delete the old key
```

### Two ceilings, and they are different things

**The GCP budget ($100)** alerts. It does not stop anything. It watches every
service in this project and emails at 50%, 90% and 100%.

**The embedding cap (`RECORD_SPEND_CAP_USD`, default $100)** stops. It is
checked at the top of every backfill batch — before a row is read, let alone
bought — and measured against the `spend` ledger rather than a counter held in
memory, so it survives a restart, a second job, and a job somebody ran last
week.

The arithmetic it uses is pinned and checkable:

| | |
|---|---|
| rate | **$0.15 per 1M input tokens**, `gemini-embedding-001` paid tier, verified against ai.google.dev on 2026-07-19 |
| assumption | 60 tokens per civic segment (deliberately generous — an estimate that undercounts is a cap that does not hold) |
| **the whole imported record** | 72,816 segments ≈ **$0.66** |
| the cap is reached at | ~11.1 million segments |

So the cap is a runaway brake, not a budget: the real backfill costs less than
a coffee, and $100 is roughly a hundred and fifty times it. If the estimate and
the invoice ever disagree, the ledger is the arbiter —
`/api/steward/spend` shows units actually bought, and the conversion above is
only an estimate over them. A drifting price shows up as that divergence.

Lower it for a run:

```bash
gcloud run jobs update record-embed --region=us-east1 \
  --update-env-vars=RECORD_SPEND_CAP_USD=5
```

**Turning it all off** — and it is worth knowing this is safe:

```bash
gcloud sql instances patch record-pg --activation-policy=NEVER
```

The reader keeps working. The record is static; stopping the database stops
meaning-search and intake, not reading. To stop everything:
`gcloud projects delete publicrecord-studio`. The record itself is not in
there — it is in `corpus.db` on the desk and in every pressed edition anyone
has downloaded, which is what the anti-lock-in promise was for.

## 8. What is not done yet

Honest list. None of it is broken; all of it is unfinished.

1. **The corpus is empty.** 0 meetings. The full record (10 meetings, 217
   issues, 27 roll calls) lives on the other Mac and imports through the Cloud
   SQL proxy — see §9.
2. **`publicrecord.studio` DNS points at GitHub Pages, but the Pages custom
   domain is still `control-z.org`.** Until that swaps, the domain resolves to
   GitHub and GitHub does not yet know which site to serve. The swap waits on
   moving the tools site to its own repo so control-z.org never goes dark.
3. ~~No Gemini key~~ — **done.** `neural.available: true`. Nothing has been
   embedded yet because the corpus is empty; the backfill job is created after
   the import lands, and it runs under the cap in §7.
4. ~~The steward console is configured-off~~ — **done.** Signed in with Google
   against a server-side allowlist of one. `/api/steward/me` now answers 401
   without a token rather than 503; the difference is "sign in" versus "there is
   no console here", and both are honest.
5. **The nightly scheduler is not created.** Polling is manual until it is.
6. **The intake connector has never ingested a meeting end to end.** It polls,
   classifies and files correctly against all three real channels — but
   transcription, embedding and issue-assignment on a freshly-filed meeting has
   only ever run at the desk. **Do one meeting and read it end to end before
   turning a nightly poll loose on a backlog.**

---

## 9. Importing the full corpus

From the Mac that holds it — not this one, which has a thinner copy:

```bash
gcloud components install cloud-sql-proxy   # once
cloud-sql-proxy publicrecord-studio:us-east1:record-pg --port 55432 &

# the password is in Secret Manager, not in this file
RECORD_DSN="postgresql://record:$(gcloud secrets versions access latest \
  --secret=record-dsn --project=publicrecord-studio | sed 's/.*record://;s/@.*//')\
@localhost:55432/record" \
  .venv/bin/python -m record.import_desk \
  --corpus ~/Movies/control-z/memory/corpus.db --sample 500
```

It verifies itself: every table counted, a sample of vectors re-read
bit-for-bit against the source blobs, and the issue rollups diffed between
SQLite and Postgres. **It must end with "the record arrived whole."** If it
does not, that output is the finding — send it rather than working around it.

It opens the source corpus **read-only** and cannot write to it.

---

## 10. The rules that are not negotiable

These are covenant, not configuration. If a change would break one, the change
is wrong.

- **Readers never log in, are never counted, never tracked.** No cookie, no
  session, no analytics. The public endpoints take no identity and there is a
  test asserting they set no `Set-Cookie`.
- **Accounts exist for stewards only.**
- **The record stays readable with the backend dead.** Every feature that
  cannot degrade to the static edition is a feature that needs rethinking.
- **Nothing ingests without a human.** Submissions queue; stewards approve.
- **Everything degrades out loud.** A missing capability is stated in the
  response and shown to the reader. Silence is the failure mode we design
  against.
- **Officials-only aggregation.** Enforced at press time. Private citizens are
  findable within a meeting, never aggregated into a person page.
- **Corrections annotate; they never rewrite.** The record remembers its own
  edits, and now remembers who made them.
