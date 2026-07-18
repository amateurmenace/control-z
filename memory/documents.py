"""Documents in the record — the town's own paper, beside what was said.

Civic issues live in two registers: the spoken meeting and the written packet.
Memory already holds the spoken half (segments, issues, votes). This module
brings in the written half — the agendas, minutes, and packets a town publishes
on its portal — extracts and chunks their text, embeds each chunk, and links it
to the same issues the transcript joins. A rezoning article that a board *voted*
on and a resident *spoke* about is also *written down* in the warrant; now all
three sit on one timeline, and every citation names its page.

The covenant holds: the PDF bytes come from the town's own public portal
(anonymous GET, no key), the receipt is the sha256 of what we fetched, and the
issue links are the same auditable keyword/cosine assignment the transcript
uses — no new judgement, just the paper joined to the record.

Extraction is pypdf (pure-python, no native deps). A town without pypdf
installed loses documents gracefully, exactly as a town without numpy loses
semantics: the feature reports it's unavailable and nothing else breaks.
"""

from __future__ import annotations

import hashlib
import re
import urllib.request
from typing import List, Optional

from memory import embed
from memory.store import Corpus

# chunk sizing — ~180 content words keeps a chunk near one embedding's worth of
# meaning while staying small enough that a citation points at a real paragraph,
# not a whole page. Pages over the cap are dropped with an honest note (covenant:
# no silent truncation — the document row records how many pages it actually read).
CHUNK_WORDS = 180
MAX_PAGES = 80              # a 300-page packet is capped; the note says so
MIN_CHUNK_WORDS = 6
COS_ASSIGN = 0.82          # the same floor the transcript uses (issues.COS_ASSIGN)
_WORD = re.compile(r"[a-z0-9]+")
_BOILER = {"the", "and", "for", "with", "that", "this", "will", "from",
           "shall", "any", "all", "was", "are", "not", "has", "have"}


# --------------------------------------------------------------------------
# extraction — bytes → pages → chunks (no network, fully testable)
# --------------------------------------------------------------------------

def available() -> bool:
    """True when pypdf is importable — the honest gate the status line reads."""
    try:
        import pypdf  # noqa: F401
        return True
    except Exception:
        return False


def extract_pages(pdf_bytes: bytes) -> List[str]:
    """One cleaned text string per page (pypdf). Empty list without pypdf or on
    an unreadable file — the caller records the document as status 'error' with
    a sentence, never crashes the pipeline."""
    import io

    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    out = []
    for pg in reader.pages:
        try:
            txt = pg.extract_text() or ""
        except Exception:
            txt = ""
        # collapse the ragged whitespace PDF text extraction leaves behind
        txt = re.sub(r"[ \t]+", " ", txt)
        txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
        out.append(txt)
    return out


def chunk_pages(pages: List[str], words: int = CHUNK_WORDS) -> List[dict]:
    """Group page text into ~`words`-word chunks, each tagged with the (1-based)
    page it starts on. A chunk never spans a page boundary silently — it carries
    the page it opened on, so a citation reads 'p. 12' truthfully."""
    chunks: List[dict] = []
    for pi, text in enumerate(pages[:MAX_PAGES], start=1):
        toks = text.split()
        if not toks:
            continue
        for i in range(0, len(toks), words):
            piece = " ".join(toks[i:i + words]).strip()
            if len(piece.split()) >= MIN_CHUNK_WORDS:
                chunks.append({"page": pi, "text": piece})
    return chunks


def _doc_id(meeting_id: str, sha: str) -> str:
    return f"doc:{sha[:16]}" if sha else f"doc:{hashlib.sha1(meeting_id.encode()).hexdigest()[:16]}"


# --------------------------------------------------------------------------
# issue assignment — the paper twin of issues._assign
# --------------------------------------------------------------------------

def _matchers(keywords: List[str]):
    return [re.compile(r"\b" + re.escape(k) + r"\b") for k in keywords if k]


def assign_document(corpus: Corpus, doc_id: str) -> dict:
    """Attach a document's chunks to the issues they name — keyword-first (word
    boundary, why 'alias'), then a single nearest issue by cosine when it clears
    COS_ASSIGN (why 'related'). Exactly the transcript's rule, so the written and
    spoken record join the same issues by the same auditable logic."""
    doc = corpus.get_document(doc_id)
    if not doc:
        return {"linked": 0}
    town = doc.get("town", "")
    chunks = corpus.doc_chunks_of(doc_id)
    if not chunks:
        return {"linked": 0}
    issues = [i for i in corpus.issue_keywords(active_only=True)
              if not town or not i.get("town") or i.get("town") == town]
    if not issues:
        return {"linked": 0}
    pats = {i["id"]: _matchers(i.get("keywords") or []) for i in issues}
    have_cos = embed.np is not None and any(i.get("centroid") is not None
                                            for i in issues)
    cen_ids, cen_mat = [], None
    if have_cos:
        cen_ids = [i["id"] for i in issues if i.get("centroid") is not None]
        cen_mat = embed.np.vstack([i["centroid"] for i in issues
                                   if i.get("centroid") is not None])
    corpus.clear_doc_links(doc_id)
    links: dict = {}
    for c in chunks:
        text = (c.get("text") or "").lower()
        hit = set()
        for i in issues:
            for pat in pats[i["id"]]:
                if pat.search(text):
                    links.setdefault(i["id"], []).append(
                        (c["id"], doc_id, 1.0, "alias"))
                    hit.add(i["id"])
                    break
        if not hit and cen_mat is not None:
            v = embed.as_vec(c.get("emb"))
            if v is not None:
                sims = cen_mat @ v
                b = int(sims.argmax())
                if float(sims[b]) >= COS_ASSIGN:
                    links.setdefault(cen_ids[b], []).append(
                        (c["id"], doc_id, float(sims[b]), "related"))
    n = 0
    for iid, ls in links.items():
        n += corpus.link_doc_chunks(iid, ls)
    return {"linked": n, "issues": len(links)}


# --------------------------------------------------------------------------
# the core: store one document, chunk + embed + assign (no network)
# --------------------------------------------------------------------------

def ingest_bytes(corpus: Corpus, meeting_id: str, pdf_bytes: bytes, *,
                 town: str = "", kind: str = "", title: str = "",
                 date: str = "", url: str = "", source: str = "",
                 assign: bool = True) -> dict:
    """Store one document from its bytes: extract → chunk → embed → link to
    issues. Returns {doc_id, pages, chunks, linked, note}. Idempotent by content
    hash — re-ingesting the same bytes overwrites the same doc row."""
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    did = _doc_id(meeting_id, sha)
    try:
        pages = extract_pages(pdf_bytes)
    except Exception as e:
        corpus.upsert_document({
            "id": did, "meeting_id": meeting_id, "town": town, "kind": kind,
            "title": title, "date": date, "url": url, "source": source,
            "sha256": sha, "status": "error",
            "error": f"couldn't read the PDF — {e}"})
        return {"doc_id": did, "pages": 0, "chunks": 0, "linked": 0,
                "note": f"unreadable: {e}"}
    chunks = chunk_pages(pages)
    note = ""
    if len(pages) > MAX_PAGES:
        note = f"read the first {MAX_PAGES} of {len(pages)} pages"
    corpus.upsert_document({
        "id": did, "meeting_id": meeting_id, "town": town, "kind": kind,
        "title": title, "date": date, "url": url, "source": source,
        "pages": len(pages), "sha256": sha, "status": "live", "error": ""})
    corpus.replace_doc_chunks(did, chunks)
    res = assign_document(corpus, did) if assign else {"linked": 0}
    return {"doc_id": did, "pages": len(pages), "chunks": len(chunks),
            "linked": res.get("linked", 0), "note": note}


# --------------------------------------------------------------------------
# the fetch layer — the town's portal (CivicClerk), anonymous GET
# --------------------------------------------------------------------------

# which document kinds we pull, in priority order. Agendas name the articles;
# minutes carry the roll calls; the packet is the full paper but can run to
# hundreds of pages, so it rides last and under the page cap.
WANTED_KINDS = ("Agenda", "Minutes", "Agenda Packet")


def _phrase(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _score_event(ev: dict, title_words: set, body: str, days_off: int) -> float:
    """How well a portal event matches a meeting. The body PHRASE ('select
    board', 'school committee') appearing in the event name is the decisive
    signal — word overlap alone lets 'School Committee' match 'School Building
    Committee', which is a different body. Date proximity breaks ties (the
    meeting IS the event, so a real match is the same day)."""
    name = _phrase(ev.get("name") or "")
    words = {w for w in _WORD.findall(name) if w not in _BOILER}
    overlap = len(words & title_words)
    body_hit = bool(body) and _phrase(body) in name
    if not body_hit:
        # no confident body match — only a same-day, high-overlap event qualifies
        return (overlap if (days_off <= 1 and overlap >= 3) else 0) - days_off
    # body matches: reward it heavily, prefer the closest date, then overlap,
    # and nudge a "regular meeting" ahead of a same-body "hearing"/"subcommittee"
    score = 100 + overlap - days_off * 4
    if "regular meeting" in name or name.endswith("meeting"):
        score += 2
    if "subcommittee" in name or "hearing" in name:
        score -= 1
    return score


def _fetch_pdf(url: str, timeout: float = 45.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "control-z-grabber"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_for_meeting(corpus: Corpus, meeting_id: str, *,
                      tenant: str = "brooklinema", window_days: int = 14,
                      kinds=WANTED_KINDS, max_docs: int = 4,
                      job=None) -> dict:
    """Find the CivicClerk event that matches a meeting (nearest date + title
    overlap), fetch its published files, and ingest each. Network: one portal
    search + one GET per document. Returns a JSON-safe summary. Never raises for
    a portal hiccup — it records the reach and moves on (the record supplements
    the official paper; a missing packet is a note, not a failure)."""
    from grabber import civicclerk

    def say(msg, prog=None):
        if job is not None:
            job.message = msg
            if prog is not None:
                job.progress = prog

    m = corpus.get_meeting(meeting_id)
    if not m:
        return {"error": "no such meeting on the record", "documents": []}
    if not available():
        return {"error": "pypdf isn't installed — documents need it "
                          "(pip install pypdf)", "documents": []}
    date = m.get("date") or ""
    town = m.get("town") or ""
    body = m.get("body") or ""
    if not date:
        return {"error": "this meeting has no date to search the portal around",
                "documents": []}

    # a window around the meeting date
    from datetime import date as _date, timedelta
    try:
        d0 = _date.fromisoformat(date)
    except ValueError:
        return {"error": f"unparseable meeting date {date!r}", "documents": []}
    lo = (d0 - timedelta(days=window_days)).isoformat()
    hi = (d0 + timedelta(days=window_days)).isoformat()

    say("searching the town portal…", 0.1)
    try:
        events = civicclerk.search_events(tenant, lo, hi)
    except Exception as e:
        return {"error": f"couldn't reach the portal — {e}", "documents": []}

    from datetime import date as _d

    def _days_off(ev):
        w = (ev.get("when") or "")[:10]
        try:
            return abs((_d.fromisoformat(w) - d0).days)
        except ValueError:
            return window_days + 1

    title_words = {w for w in _WORD.findall((m.get("title") or "").lower())
                   if w not in _BOILER}
    scored = sorted(
        ((_score_event(ev, title_words, body, _days_off(ev)), ev)
         for ev in events if ev.get("files")),
        key=lambda sv: -sv[0])
    # one event per meeting on the portal — take the single best confident match
    # (a body-phrase hit scores ≥100; a same-day high-overlap fallback ≥3)
    picks = [ev for sc, ev in scored if sc >= 3][:1]
    if not picks:
        return {"matched": None, "documents": [],
                "note": "no portal event matched this meeting closely enough"}

    out = []
    n = 0
    for ev in picks:
        files = [f for f in (ev.get("files") or []) if f.get("type") in kinds]
        files.sort(key=lambda f: kinds.index(f["type"]) if f["type"] in kinds
                   else 99)
        for f in files:
            if n >= max_docs:
                break
            say(f"reading {f.get('type','document')} — {ev.get('name','')[:40]}",
                0.2 + 0.7 * n / max_docs)
            try:
                pdf = _fetch_pdf(f["url"])
            except Exception as e:
                out.append({"kind": f.get("type", ""), "title": f.get("name", ""),
                            "error": f"couldn't fetch — {e}"})
                continue
            res = ingest_bytes(
                corpus, meeting_id, pdf, town=town, kind=f.get("type", ""),
                title=f.get("name", "") or ev.get("name", ""),
                date=(ev.get("when") or "")[:10] or date,
                url=f["url"], source=f"civicclerk:{tenant}")
            res.update({"kind": f.get("type", ""), "event": ev.get("name", ""),
                        "event_id": ev.get("id")})
            out.append(res)
            n += 1
    return {"matched": picks[0].get("name", ""),
            "event_id": picks[0].get("id"),
            "documents": out, "n": n}


def reassign_all(corpus: Corpus, town: str = "") -> dict:
    """Re-link every live document's chunks after an issue rebuild — the paper
    twin of a re-discover. Cheap: chunks are already embedded."""
    docs = corpus.list_documents(town=town, limit=1000)
    total = 0
    for d in docs:
        if d.get("status") == "live":
            total += assign_document(corpus, d["id"]).get("linked", 0)
    return {"documents": len(docs), "linked": total}
