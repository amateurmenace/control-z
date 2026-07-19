# Publicrecord's container — the API and the jobs, which are the same image.
#
# One image rather than two because they are one codebase and the difference is
# a command; two images is two things to keep in step and a class of bug where
# the job ships an engine the API does not have.
#
# The repo is copied whole rather than pip-installed, deliberately: `web/emit.py`
# reads `suite/static/app.css`, `web/static/app.web.css` and `web/static/app.js`
# relative to the checkout to press an edition, so a container that carries only
# the `record` package can serve search and cannot press. That is exactly the
# sort of half-working deployment that looks fine until the nightly press runs.

FROM python:3.12-slim

# Nothing here needs a compiler: psycopg ships a binary wheel, and the suite's
# heavy local-AI dependencies are the desk's business, not the server's.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The server's own bill, and only it. No torch, no faster-whisper, no PyAV —
# the desk stays local-first and BYO-key, and a container that transcribes is
# a GPU decision nobody has made (specs/17 §6.4: the drain, not a bill).
RUN pip install --no-cache-dir \
        "psycopg[binary,pool]>=3.2" \
        "pgvector>=0.3" \
        "fastapi" \
        "uvicorn[standard]" \
        "google-auth[requests]>=2.30" \
        "numpy"

# The neural half. Installed now that a key exists and the spend is intended:
# a project-scoped key restricted to generativelanguage only, billed to the
# same budget as everything else here.
#
# Note what this does NOT do. Installing the SDK starts no spending. Embedding
# happens at ingest, batched, and at query time only when a caller asks for
# space=neural. Without a key the module reports itself unavailable and search
# stays lexical with an honest line — which remains the state every environment
# except this one runs in, and the tests still cover it.
RUN pip install --no-cache-dir "google-genai>=1.0"

# The edition's ride to the bucket. `record/press.py` treats this as optional
# and says so when it is missing — it presses to disk and reports plainly that
# the edition did not travel — which is the right behaviour for a desk and the
# wrong one for the job whose entire purpose is to put the record where readers
# reach it. A press that "succeeds" without uploading is the quiet failure this
# line removes.
RUN pip install --no-cache-dir "google-cloud-storage>=2.14"

COPY czcore/    /app/czcore/
COPY memory/    /app/memory/
COPY web/       /app/web/
COPY record/    /app/record/
COPY suite/static/app.css /app/suite/static/app.css
COPY highlighter/ /app/highlighter/

# Scale-to-zero on Cloud Run means this is also the cold-start path; keep it
# to an import check rather than anything that touches the network.
#
# `record.pipeline` and `memory.ingest` are on this line for a specific reason:
# the ingest engine is desk code running in a container that ships neither
# Scribe nor the tool directories, so its imports are the ones most likely to
# reach for something that is not here. Catching that at build time costs a
# second; catching it at 3am costs a night's meetings.
RUN python -c "import record.app, record.store, record.press, record.pipeline, \
    record.connectors.youtube, memory.ingest"

EXPOSE 8330
CMD ["uvicorn", "record.app:app", "--host", "0.0.0.0", "--port", "8330"]
