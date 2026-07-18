# The Studio's container — the API and the jobs, which are the same image.
#
# One image rather than two because they are one codebase and the difference is
# a command; two images is two things to keep in step and a class of bug where
# the job ships an engine the API does not have.
#
# The repo is copied whole rather than pip-installed, deliberately: `web/emit.py`
# reads `suite/static/app.css`, `web/static/app.web.css` and `web/static/app.js`
# relative to the checkout to press an edition, so a container that carries only
# the `studio` package can serve search and cannot press. That is exactly the
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

# google-genai is deliberately NOT installed here. Without it the Studio runs,
# search is lexical, and the reader is told in one honest line. Add it when a
# key exists and the spend is intended:
#   RUN pip install --no-cache-dir "google-genai>=1.0"

COPY czcore/    /app/czcore/
COPY memory/    /app/memory/
COPY web/       /app/web/
COPY studio/    /app/studio/
COPY suite/static/app.css /app/suite/static/app.css
COPY highlighter/ /app/highlighter/

# Scale-to-zero on Cloud Run means this is also the cold-start path; keep it
# to an import check rather than anything that touches the network.
RUN python -c "import studio.app, studio.store, studio.press, studio.connectors.youtube"

EXPOSE 8330
CMD ["uvicorn", "studio.app:app", "--host", "0.0.0.0", "--port", "8330"]
