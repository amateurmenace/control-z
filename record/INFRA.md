# Publicrecord's infrastructure — a runbook, not a report

**Nothing in this document has been provisioned.** No GCP project exists, no
Cloud SQL instance is running, no bucket has been created, and the meter has
not started. That was a deliberate choice at the top of wave 1: the whole thing
was built and proven against `docker compose up` (Postgres 16 + pgvector 0.8.5
locally), so that the day the bill begins is a day somebody chose, with the
code already known to work.

What follows is therefore the exact sequence to run, each resource named with
the console URL where it will appear and the monthly line it adds. Run it in
order; every step is idempotent enough to re-run after a failure.

The estimates are specs/17 §10's, unchanged, and they are *estimates* — the
only honest number is the one on the invoice, and the last section says how to
watch it.

---

## 0. What you are about to spend

| Line | Est. / month | When it starts |
|---|---|---|
| Cloud SQL Postgres (db-f1-micro, 10 GB) | $10–30 | **the moment the instance exists** — this one does not scale to zero |
| Cloud Run `record-api` (min-instances 0) | $0–5 | only when someone reads |
| Cloud Run Jobs `record-pipeline` | ~$0 | only when the nightly job runs |
| GCS + CDN (editions, documents) | $1–5 | with the first pressing |
| Gemini embeddings + Flash passes (~50 meetings/mo) | $1–5 | only if `RECORD_GEMINI_KEY` is set |
| Cloud Scheduler, logging | ~$0 | — |
| **Steady state** | **~$15–45** | |
| One-time backfill (300 meetings, captions-first) | ~$5–15 | once |
| ASR | **$0** | via the desk drain (specs/17 §6.4); cloud GPU is a priced decision nobody has made |

**Cloud SQL is the only line that bills while nothing is happening.** If the
Studio is idle for a season, that is the line to stop — and stopping it is
safe, because the reader is static and does not notice (§6.2, and there is a
test for it).

---

## 1. The project

One new project, so the bill is legible from day one rather than mixed into an
existing one.

```bash
gcloud projects create publicrecord-studio --name="publicrecord.studio"
gcloud config set project publicrecord-studio

# Attach billing. `gcloud billing accounts list` shows the open ones.
gcloud billing projects link publicrecord-studio \
    --billing-account=<ACCOUNT_ID>

gcloud services enable \
    run.googleapis.com sqladmin.googleapis.com storage.googleapis.com \
    cloudscheduler.googleapis.com secretmanager.googleapis.com \
    artifactregistry.googleapis.com generativelanguage.googleapis.com
```

Console: <https://console.cloud.google.com/home/dashboard?project=publicrecord-studio>

**Region: `us-east1`.** Nearest to Brookline of the cheap regions, and every
resource below must share it — a Cloud Run service in one region talking to a
Cloud SQL instance in another pays for the crossing and gets slower for it.

---

## 2. Cloud SQL — the corpus

```bash
gcloud sql instances create record-pg \
    --database-version=POSTGRES_16 \
    --edition=ENTERPRISE \
    --tier=db-f1-micro \
    --region=us-east1 \
    --storage-size=10GB \
    --storage-auto-increase \
    --backup-start-time=07:00 \
    --database-flags=cloudsql.iam_authentication=on

gcloud sql databases create studio --instance=record-pg
gcloud sql users create studio --instance=record-pg --password=<PICK ONE>

# pgvector is an extension, and CREATE EXTENSION is in 001_corpus.sql —
# Cloud SQL for Postgres 16 carries it. Nothing to install here.
```

Console: <https://console.cloud.google.com/sql/instances?project=publicrecord-studio>
**Adds: $10–30/mo.** Automated backups are on by default with the flag above;
that is the line item that makes this a record rather than a cache.

> **`--edition=ENTERPRISE` is not optional.** Cloud SQL now defaults
> PostgreSQL 16 to ENTERPRISE_PLUS, which rejects every shared-core tier
> with *"Invalid Tier (db-f1-micro) for (ENTERPRISE_PLUS) Edition"*. Without
> the flag the cheapest instance you can create is roughly ten times this
> line. Found by running this runbook, 2026-07-19.
>
> `db-f1-micro` is a shared-core tier. It is right for two meetings and will
> not be right for three hundred — the upgrade is `gcloud sql instances patch
> record-pg --tier=db-g1-small`, a restart, and roughly double the line. Do it
> when the nightly job starts timing out, not before.

---

## 3. Secrets

Never in the repo, never in a `--set-env-vars`, never in this file.

```bash
printf '%s' '<gemini key>'   | gcloud secrets create record-gemini-key --data-file=-
printf '%s' '<oauth client>' | gcloud secrets create record-google-client-id --data-file=-
printf '%s' 'you@example.org' | gcloud secrets create record-steward-allowlist --data-file=-
printf '%s' "$(openssl rand -hex 32)" | gcloud secrets create record-service-token --data-file=-
printf '%s' 'postgresql://studio:<pw>@/studio?host=/cloudsql/publicrecord-studio:us-east1:record-pg' \
    | gcloud secrets create record-dsn --data-file=-
```

Console: <https://console.cloud.google.com/security/secret-manager?project=publicrecord-studio>
**Adds: ~$0.**

Each of these is optional and publicrecord says so when one is missing: with no
Gemini key search is lexical and the reader is told; with no allowlist every
steward route returns 503. It fails closed, not open.

---

## 4. The image

```bash
gcloud artifacts repositories create record \
    --repository-format=docker --location=us-east1

gcloud builds submit --tag us-east1-docker.pkg.dev/community-ai-record/record/api:1 \
    --file record/Dockerfile .
```

Console: <https://console.cloud.google.com/artifacts?project=publicrecord-studio>
**Adds: <$1/mo** for a handful of image versions.

---

## 5. Cloud Run — the API

```bash
gcloud run deploy record-api \
    --image=us-east1-docker.pkg.dev/community-ai-record/record/api:1 \
    --region=us-east1 \
    --allow-unauthenticated \
    --min-instances=0 --max-instances=4 \
    --cpu=1 --memory=512Mi --concurrency=40 \
    --add-cloudsql-instances=publicrecord-studio:us-east1:record-pg \
    --set-secrets=RECORD_DSN=record-dsn:latest,\
RECORD_GEMINI_KEY=record-gemini-key:latest,\
RECORD_GOOGLE_CLIENT_ID=record-google-client-id:latest,\
RECORD_STEWARD_ALLOWLIST=record-steward-allowlist:latest,\
RECORD_SERVICE_TOKEN=record-service-token:latest
```

Console: <https://console.cloud.google.com/run?project=publicrecord-studio>
**Adds: $0–5/mo.** `--min-instances=0` is the whole cost posture: an idle
Studio costs nothing but its database.

`--allow-unauthenticated` is correct and deliberate. The public endpoints are
public by covenant — readers never log in — and the steward routes carry their
own Google check. Putting IAM in front of the whole service would lock out the
readers this exists for.

Then run the migrations once, from a job with the same connection:

```bash
gcloud run jobs create record-migrate \
    --image=us-east1-docker.pkg.dev/community-ai-record/record/api:1 \
    --region=us-east1 \
    --add-cloudsql-instances=publicrecord-studio:us-east1:record-pg \
    --set-secrets=RECORD_DSN=record-dsn:latest \
    --command=python --args=-m,record.migrate
gcloud run jobs execute record-migrate --region=us-east1 --wait
```

---

## 6. GCS — the pressed editions

```bash
gcloud storage buckets create gs://publicrecord-edition \
    --location=us-east1 --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding gs://publicrecord-edition \
    --member=allUsers --role=roles/storage.objectViewer
```

Console: <https://console.cloud.google.com/storage/browser?project=publicrecord-studio>
**Adds: $1–5/mo** including egress at launch scale.

`record/press.py` uploads pre-gzipped objects with `Content-Encoding: gzip`,
which matters more than it sounds: the bake writes JSON plain on the assumption
a CDN gzips on the wire, GCS does not transcode by default, and
`search/segs.json` is fetched **in full on every search**. Serving it raw would
turn the reader's first search into a multi-megabyte download on exactly the
connections this project exists to serve. On the real Brookline record the
difference measured 6.1 MB → 2.0 MB.

---

## 7. The load balancer, and why both halves share an origin

`web/emit.py` sets `connect-src 'self'` in the edition's CSP. An edition served
from a bucket on one origin and an API on another **breaks every fetch in the
reader** — so they must share a hostname, and widening the CSP is the wrong
trade for a page whose footer promises *no accounts · no tracking · yours*.

One HTTPS load balancer, two backends:

- `communityai.record/app/*` → the GCS bucket
- `communityai.record/api/*` → Cloud Run `record-api`

**Adds: ~$18/mo for the load balancer** — the one line specs/17 §10 did not
count, and the largest single item after the database. If that is not worth it
at launch, the honest alternative is to serve the edition *from* Cloud Run
(same origin, no LB, slightly slower and slightly more Run cost) and add the LB
when traffic earns it. **Recommendation: start without the LB.**

Then DNS, per §14's open question, which Stephen answers:
`communityai.studio` currently redirects to `community.weirdmachine.org` at
Squarespace; point it here instead.

---

## 8. Scheduler — the nightly poll

```bash
gcloud run jobs create record-pipeline \
    --image=us-east1-docker.pkg.dev/community-ai-record/record/api:1 \
    --region=us-east1 \
    --add-cloudsql-instances=publicrecord-studio:us-east1:record-pg \
    --set-secrets=RECORD_DSN=record-dsn:latest,RECORD_GEMINI_KEY=record-gemini-key:latest \
    --command=python --args=-m,record.connectors.youtube,--all-towns

gcloud scheduler jobs create http record-nightly \
    --location=us-east1 --schedule="0 3 * * *" --time-zone="America/New_York" \
    --uri="https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/community-ai-record/jobs/record-pipeline:run" \
    --http-method=POST --oauth-service-account-email=<RUN_SA>
```

Console: <https://console.cloud.google.com/cloudscheduler?project=publicrecord-studio>
**Adds: ~$0** (3 free jobs).

03:00 local, because that is after the towns have posted the evening's meeting
and before anyone reads it. The connector backs off politely and reports a
throttling source rather than hammering it.

---

## 9. Import the record

```bash
gcloud run jobs create record-import \
    --image=... --region=us-east1 \
    --add-cloudsql-instances=... --set-secrets=RECORD_DSN=record-dsn:latest \
    --command=python --args=-m,record.import_desk,--corpus,/corpus/corpus.db
```

The corpus is a local SQLite file on a desk, so in practice this runs from the
desk against the Cloud SQL proxy rather than as a job:

```bash
cloud-sql-proxy publicrecord-studio:us-east1:record-pg --port 55432 &
RECORD_DSN="postgresql://studio:<pw>@localhost:55432/studio" \
    .venv/bin/python -m record.import_desk \
    --corpus ~/Movies/control-z/memory/corpus.db
```

It verifies itself and refuses to claim success: every table counted, a sample
of vectors re-read bit-for-bit, and the issue rollups diffed between the two
stores. Locally, against the real record: 16,443 segments in 24s, 487/487
sampled vectors identical, all 41 issue rollups agreeing.

---

## 10. Watching the bill

```bash
gcloud billing budgets create --billing-account=<ACCOUNT_ID> \
    --display-name="publicrecord.studio" \
    --budget-amount=60USD \
    --threshold-rule=percent=0.5 --threshold-rule=percent=0.9
```

$60 against a $15–45 estimate: high enough not to cry wolf, low enough that a
runaway job is a phone call and not a month.

Publicrecord also keeps its own ledger. `spend` records every AI call — model,
purpose, town, units — and `/api/steward/spend` totals it on the console. That
is the desk's AI-audit pattern ported up (§6.6): the point is that the number is
visible to the person making the decision, not only to whoever opens the
invoice.

---

## 11. Turning it off

Because a runbook that cannot be reversed is a trap.

```bash
gcloud sql instances patch record-pg --activation-policy=NEVER   # stops the $10–30
gcloud run services update record-api --region=us-east1 --min-instances=0
```

The reader keeps working. That is not a consolation — it is the design
(specs/17 §6.2), and it was tested by stopping Postgres and walking the reader,
which searched all 16,443 segments and never noticed.

To delete the lot: `gcloud projects delete publicrecord-studio`. The record
itself is not in there — it is in `corpus.db` on the desk and in every pressed
edition anyone has downloaded, which is what the anti-lock-in promise was for.
