"""Publicrecord's HTTP surface — small on purpose.

The reader is static. That is not a limitation being worked around; it is the
resilience answer and the cost answer in one move (specs/17 §6.2). The pressed
edition carries the meetings, the issues, the timelines, the ledgers and the
lexical search index, and it reads with this service dead, the database gone,
and the aeroplane mode on. So the API's job is only the part an envelope of
static files structurally cannot hold:

  · **semantic search**, which needs a vector index at query time — the one
    feature that is publicrecord's whole reason to have a server;
  · **freshness**, so a reader looking at yesterday's pressing can be told a
    newer one exists rather than silently reading history;
  · **submissions**, so "Add a meeting" finally POSTs instead of composing a
    GitHub issue — the specs/16 contract shape unchanged, landing in a queue;
  · **the steward console**, behind Google sign-in, which is the only place
    anybody logs into anything.

Everything else the reader wants, it already has on disk.

**No reader is identified, counted, or followed here.** There is no cookie, no
session, no analytics, no fingerprint, and the public endpoints take no
identity and set no state. The server logs what Cloud Run logs — operational,
rotated, never product data (specs/17 §9). If a future endpoint needs to know
who is reading, it is the wrong endpoint.

Every public response says what it could not do rather than quietly doing less:
a search with the neural half unavailable reports `"space": "lexical"` and a
sentence, and the reader prints it. Degrading is allowed; degrading silently is
not.

    uvicorn record.app:app --port 8080
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, Response

from memory import embed

from . import auth
from .settings import settings

STARTED = time.time()


def get_corpus():
    """One store for the process, opened lazily so importing this module —
    which the tests do — never needs a database."""
    global _CORPUS
    try:
        return _CORPUS
    except NameError:
        pass
    from .store import PgCorpus
    _CORPUS = PgCorpus()
    return _CORPUS


def create_app(corpus=None) -> FastAPI:
    app = FastAPI(title="publicrecord.studio",
                  description="The record, hosted. specs/17.",
                  docs_url=None, redoc_url=None)
    _store = {"corpus": corpus}

    def store():
        if _store["corpus"] is None:
            _store["corpus"] = get_corpus()
        return _store["corpus"]

    # -- the covenant, in a header ---------------------------------------
    @app.middleware("http")
    async def no_tracking(request: Request, call_next):
        """Readers are never tracked. Saying so in a header is cheap, and it
        makes the promise checkable by somebody who does not read Python."""
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noarchive"
        response.headers["Cache-Control"] = response.headers.get(
            "Cache-Control", "no-store")
        return response

    @app.exception_handler(auth.AuthError)
    async def _auth_error(request: Request, exc: auth.AuthError):
        return JSONResponse({"error": exc.detail}, status_code=exc.status)

    def steward_of(authorization: Optional[str]) -> dict:
        return auth.verify_token(auth.bearer(authorization))

    # -- public: is anything alive ----------------------------------------

    @app.get("/api/health")
    def health():
        """Deliberately honest about halves. A green health check that hides a
        dead neural index is how a degraded search ships for a month."""
        from . import embed_neural
        out = {"ok": True, "uptime_s": round(time.time() - STARTED, 1),
               "store": settings.redacted(),
               "neural": embed_neural.status(),
               "steward_console": auth.configured() or auth.why_unconfigured()}
        try:
            out["record"] = store().stats()
        except Exception as exc:
            out["ok"] = False
            out["record"] = None
            out["error"] = f"the corpus is unreachable ({exc})"
            return JSONResponse(out, status_code=503)
        return out

    # -- public: the feature the envelope cannot hold ---------------------

    @app.get("/api/search")
    def search(q: str = Query("", description="what to ask the record"),
               town: str = Query("", description="scope to one town"),
               space: str = Query("lexical", pattern="^(lexical|neural)$"),
               limit: int = Query(40, ge=1, le=200)):
        """Blended search, with the provenance the reader shows as chips.

        `town` is passed through explicitly and never defaulted at this layer —
        aggregating across towns is a covenant question, and the caller has to
        have meant it."""
        from . import embed_neural
        q = (q or "").strip()
        if not q:
            return {"q": "", "hits": [], "space": "lexical", "note": ""}

        want_neural = space == "neural"
        have_neural = embed_neural.available()
        used = "neural" if (want_neural and have_neural) else "lexical"
        note = ""
        if want_neural and not have_neural:
            # The honest line specs/17 §8 asks for, served from the server side
            # so the reader can print it verbatim instead of inventing one.
            note = ("meaning-search needs publicrecord; words still work — "
                    + embed_neural.status()["reason"])
        try:
            hits = store().search(q, limit=limit, town=town, space=used)
            if used == "neural" and not any(h["why"] in ("meaning", "both")
                                            for h in hits):
                # The key is set and the SDK imports, which is all available()
                # can see — it cannot see that the corpus was never backfilled,
                # or that this query's vector failed. Reporting "neural" on a
                # purely lexical result is the exact dishonesty the note exists
                # to prevent, so the claim is made from the result, not the
                # configuration.
                used = "lexical"
                note = ("meaning-search found nothing to compare against — "
                        "this corpus has not been embedded yet; words still work")
        except Exception as exc:
            return JSONResponse(
                {"q": q, "hits": [], "space": "none",
                 "note": f"the record is unreachable; the edition still reads ({exc})"},
                status_code=503)
        return {"q": q, "town": town, "space": used, "note": note,
                "count": len(hits), "hits": hits}

    # -- public: is what I am reading current -----------------------------

    @app.get("/api/freshness")
    def freshness():
        """Answers "is a newer pressing out?" and nothing else.

        Deliberately NOT the edition date: `edition_date` is the newest meeting
        in the record, not the moment of pressing, because the bake must stay
        byte-idempotent. So freshness is the corpus fingerprint, named for what
        it is, and a reader compares it with the one baked into its edition."""
        from . import press
        try:
            return {"fingerprint": press.corpus_fingerprint(store()),
                    "checked_at": round(time.time(), 3)}
        except Exception as exc:
            return JSONResponse(
                {"fingerprint": "", "note": f"unreachable ({exc})"},
                status_code=503)

    # -- public: add a meeting --------------------------------------------

    @app.post("/api/submissions")
    def submissions(body: dict = Body(...)):
        """specs/16 §P0.4's contract, unchanged, finally landing somewhere.

        The static reader composed a GitHub issue because it had nowhere to
        POST. It has somewhere now — and the shape it sends is identical, which
        is the promise that spec made ("when a Bureau exists, the same JSON
        POSTs live; the contract never changes").

        Nothing ingests on the strength of a stranger's POST: a submission
        enters the queue and a steward approves it. That is the whole point of
        having a queue."""
        url = (body.get("url") or "").strip()
        if not url:
            return JSONResponse(
                {"error": "give me a meeting URL"}, status_code=422)
        from web.canon import canon
        canonical = canon(url) or ""
        corpus = store()

        known = corpus.find_by_url_canon(canonical) if canonical else None
        if known:
            return {"meeting_id": known["id"], "status": "exists"}

        from .store import submission_id
        sub_id = submission_id(canonical or url)
        now = time.time()
        with corpus._con() as con:
            row = con.execute(
                "SELECT id, status FROM submissions WHERE url_canon=%s AND "
                "url_canon<>'' ", (canonical,)).fetchone()
            if row:
                # Already queued, or already refused. A resubmission does not
                # overrule a steward who said no.
                return {"meeting_id": "", "status": row["status"],
                        "submission_id": row["id"]}
            con.execute(
                "INSERT INTO submissions (id, url, url_canon, town, body, date, "
                "note, status, added_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'submitted',%s,%s) "
                "ON CONFLICT (id) DO NOTHING",
                (sub_id, url, canonical, (body.get("town") or "").strip(),
                 (body.get("body") or "").strip(), (body.get("date") or "").strip(),
                 (body.get("note") or "").strip(), now, now))
        return {"meeting_id": "", "status": "submitted", "submission_id": sub_id,
                "note": "a steward reviews; the record updates on the next pressing"}

    @app.get("/api/towns")
    def towns():
        corpus = store()
        with corpus._con() as con:
            rows = con.execute(
                "SELECT slug, name, state, status FROM towns "
                "WHERE status='live' ORDER BY name").fetchall()
        return {"towns": [dict(r) for r in rows]}

    # -- the steward console, as a page -----------------------------------
    #
    # The console is served by this service rather than pressed into the
    # edition, and that separation is deliberate. The edition must read with
    # this service dead; a curation console cannot and should not. Keeping
    # them on different origins-of-authorship means a steward's sign-in can
    # never become something a reader's copy of the record carries around.
    #
    # **The CSP.** Every reader page ships `script-src 'self'` and
    # `connect-src 'self'` in a <meta> tag (web/emit.py) and no third party
    # rides in — that is the whole posture, and nothing here relaxes it. But
    # Google Identity Services is a script from accounts.google.com, and the
    # console cannot sign anybody in without it. So `/steward` carries its
    # own header naming exactly what Google documents and nothing else: the
    # GSI client script, its stylesheet, its iframe, and its token endpoint.
    # The choice is a *second, narrower* policy on one path — four files
    # nobody but a steward requests — rather than a hole in the reader's.
    # Note what stays strict even here: `script-src` has no 'unsafe-inline'
    # and no 'unsafe-eval', so console.js is the only code that can run, and
    # `connect-src` still names only ourselves and Google. `style-src` does
    # carry 'unsafe-inline' because Google's rendered button sets element
    # styles; that costs a great deal less than letting injected markup
    # execute, which is the thing script-src is holding.
    CONSOLE_CSP = (
        "default-src 'self'; base-uri 'self'; form-action 'self'; "
        "script-src 'self' https://accounts.google.com/gsi/client; "
        "style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style; "
        "frame-src https://accounts.google.com/gsi/; "
        "connect-src 'self' https://accounts.google.com/gsi/; "
        "img-src 'self' data:; font-src 'self'; object-src 'none'; "
        "frame-ancestors 'none'")

    # An allowlist of four names, not a directory mount. A console is a fixed
    # set of files; anything that resolves a path from the URL is a way to ask
    # this service for a file it did not mean to publish, and there is no
    # reason to own that risk for three assets.
    STATIC = Path(__file__).resolve().parent / "static"
    CONSOLE_FILES = {"console.html": "text/html; charset=utf-8",
                     "console.css": "text/css; charset=utf-8",
                     "console.js": "text/javascript; charset=utf-8"}

    def _console_file(name: str) -> Response:
        path = STATIC / name
        if not path.is_file():                          # pragma: no cover
            return JSONResponse(
                {"error": f"the console is missing {name} — this build is "
                          f"incomplete, and the API is unaffected"},
                status_code=500)
        return Response(path.read_bytes(), media_type=CONSOLE_FILES[name],
                        headers={"Content-Security-Policy": CONSOLE_CSP})

    @app.get("/steward", include_in_schema=False)
    @app.get("/steward/", include_in_schema=False)
    def console_page():
        return _console_file("console.html")

    @app.get("/steward/console.css", include_in_schema=False)
    def console_css():
        return _console_file("console.css")

    @app.get("/steward/console.js", include_in_schema=False)
    def console_js():
        return _console_file("console.js")

    @app.get("/steward/config.json", include_in_schema=False)
    def console_config():
        """Whether there is a console at all, and the client id to sign in
        against — the two things the page must know *before* it can make an
        authenticated call, so this one route cannot itself require auth.

        The client id is not a secret: Google's whole design puts it in the
        markup of every page that renders a sign-in button. The allowlist is
        a secret and is never in this response — who the stewards are is not
        the browser's business, and 403 already tells a signed-in stranger
        the only thing they need to hear.

        When nothing is configured this answers 200 with `configured: false`
        rather than 503, because "there is no console here" is a true and
        successful answer to the question the page asked. The steward API
        underneath keeps returning 503 to everything, which is where failing
        closed actually matters."""
        ok = auth.configured()
        return {"configured": ok,
                "client_id": settings.google_client_id if ok else "",
                "why": "" if ok else auth.why_unconfigured()}

    # -- the steward API ---------------------------------------------------
    # Everything below this line requires a signed-in steward on the
    # allowlist. Nothing above it takes an identity at all.

    from .steward import register_steward
    register_steward(app, store, steward_of)

    return app


app = create_app()
