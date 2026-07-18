"""corpus.db → the Studio. A transliteration, never a re-derivation.

specs/17 §11.3 is explicit: *nothing is re-derived that was hand-audited*. The
Brookline corpus this imports was measured — 41 issues over two Select Board
meetings, every one of its 392 issue links made by exact alias match, its
segment vectors written by `memory/embed.py` and verified byte-for-byte. Running
`discover()` again on the other side would produce *a* set of issues; it would
not produce *these*, and the difference is a season of someone's judgement.

So this reads and writes. It does not cluster, it does not re-embed, it does not
re-assign, and it does not tidy. The 41 names come across as they are — including
`City Realy`, which is a caption garble that became a permanent issue id, and
`Anti Semitic`, which reads oddly as a label for what its member segments show
is a vandalism response. Those are wrong, and they are also the record as it
stands. The steward console's rename verb is the tool for them; fixing them here
would make the import the Studio's first unaudited edit, which is exactly the
thing this file exists not to be.

Four conversions are unavoidable, and each is mechanical:

  · `emb BLOB` → `vector(256)`: `np.frombuffer(blob, "<f4")`, same numbers.
  · a zero-norm vector → NULL, because cosine distance against zero is undefined
    under pgvector and one NaN silently poisons an HNSW ordering. The desk stores
    those zeros and skips them on read; here they are simply absent.
  · `town` is denormalised onto segments and doc_chunks, read from the parent
    meeting — the column a hosted, multi-town search cannot do without.
  · `shingles` TEXT stays, exactly as the desk spells it, so tier-three dedupe
    compares the same strings on both stores.

And then it checks itself: every table counted, a sample of vectors re-read and
compared bit-for-bit against the source blobs, and the issue rollups diffed
between the two stores. An import that cannot prove it landed is a backup nobody
has restored.

    python -m studio.import_desk --corpus ~/Movies/control-z/memory/corpus.db
    python -m studio.import_desk --corpus <path> --verify-only
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
import time
from typing import Dict, List, Optional

from memory import embed

# Read in pages: the live corpus is 16,443 segments and a single fetchall of
# every row with its vector is ~17 MB of blobs held at once for no reason.
PAGE = 2000


def _rows(con, sql: str, args=()) -> List[dict]:
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def _open_source(path: str) -> sqlite3.Connection:
    """Read-only, by URI. The source corpus is somebody's actual record and
    this command has no business being able to write to it — SQLite will
    happily create a journal beside a file opened read-write, which is enough
    to matter on a volume the desk is also using."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _vec_or_none(blob: Optional[bytes]):
    """A stored vector, or nothing at all. `memory/embed.py` writes 256 float32
    in raw C order — no header, no dtype tag, no length prefix — so this is a
    reinterpretation rather than a decode. A vector with no direction (3.2% of
    the live corpus: segments that are pure filler) becomes NULL."""
    v = embed.from_bytes(blob)
    if v is None:
        return None
    if len(v) != embed.DIM:
        raise ValueError(
            f"a stored vector has {len(v)} dimensions and memory.embed makes "
            f"{embed.DIM}. The blobs carry no dimension tag, so this cannot be "
            f"guessed at — re-embed the source corpus or pin embed.DIM back.")
    return v if float(v @ v) > 0 else None


def import_corpus(src_path: str, corpus, verbose: bool = True) -> Dict[str, int]:
    """Carry a desk corpus into the Studio. Returns a count per table."""
    counts: Dict[str, int] = {}
    say = print if verbose else (lambda *a, **k: None)
    src = _open_source(src_path)
    try:
        tables = {r["name"] for r in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}

        # -- meetings ---------------------------------------------------
        meetings = _rows(src, "SELECT * FROM meetings")
        town_of: Dict[str, str] = {}
        for m in meetings:
            m.pop("rowid", None)
            town_of[m["id"]] = m.get("town") or ""
            corpus.upsert_meeting(m)
        counts["meetings"] = len(meetings)
        say(f"  meetings   {len(meetings):>7,}")

        # -- segments ---------------------------------------------------
        # Written directly rather than through replace_segments, which would
        # re-embed every one of them. The vectors are the audited artifact.
        total = src.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
        done = blanks = 0
        with corpus._con() as con:
            # The desk's ids come across verbatim, because issue_segments
            # points at them — so a re-run has to clear the meeting's segments
            # first, exactly as replace_segments does. Without this, importing
            # twice is a primary-key collision rather than a no-op, and a
            # command nobody dares re-run after a partial failure is a command
            # nobody runs against the real corpus at all.
            for mid in town_of:
                con.execute("DELETE FROM segments WHERE meeting_id=%s", (mid,))
            for off in range(0, total, PAGE):
                page = _rows(src, "SELECT * FROM segments ORDER BY id "
                                  "LIMIT ? OFFSET ?", (PAGE, off))
                for s in page:
                    vec = _vec_or_none(s["emb"])
                    blanks += (vec is None)
                    con.execute(
                        "INSERT INTO segments (id, meeting_id, town, idx, start, "
                        "end_s, text, speaker, emb) "
                        "OVERRIDING SYSTEM VALUE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (s["id"], s["meeting_id"], town_of.get(s["meeting_id"], ""),
                         s["idx"], s["start"], s["end"], s["text"] or "",
                         s["speaker"] or "", vec))
                done += len(page)
                say(f"  segments   {done:>7,} / {total:,}", end="\r")
            # The desk's ids are carried across verbatim (issue_segments points
            # at them), so the identity sequence has to be told where they got to.
            con.execute("SELECT setval(pg_get_serial_sequence('segments','id'), "
                        "COALESCE((SELECT MAX(id) FROM segments), 1))")
        counts["segments"] = total
        say(f"  segments   {total:>7,}          ({blanks:,} with no vector)")

        # -- issues and their links -------------------------------------
        issues = _rows(src, "SELECT * FROM issues")
        for i in issues:
            i["centroid"] = _vec_or_none(i["centroid"])
            corpus.upsert_issue(i)
        counts["issues"] = len(issues)
        say(f"  issues     {len(issues):>7,}")

        links = _rows(src, "SELECT * FROM issue_segments")
        by_issue: Dict[str, list] = {}
        for g in links:
            by_issue.setdefault(g["issue_id"], []).append(
                (g["seg_id"], g["meeting_id"], g["score"], g["why"] or ""))
        for iid, ls in by_issue.items():
            corpus.link_segments(iid, ls)
        counts["issue_segments"] = len(links)
        say(f"  links      {len(links):>7,}")

        # -- threads, events, paper, votes ------------------------------
        threads = _rows(src, "SELECT * FROM threads")
        with corpus._con() as con:
            for t in threads:
                con.execute(
                    "INSERT INTO threads (id, issue_id, last_seen_date, added_at, "
                    "updated_at) VALUES (%s,%s,%s,%s,%s) "
                    "ON CONFLICT (issue_id) DO NOTHING",
                    (t["id"], t["issue_id"], t["last_seen_date"] or "",
                     t["added_at"], t["updated_at"]))
        counts["threads"] = len(threads)

        events = _rows(src, "SELECT * FROM events") if "events" in tables else []
        for e in events:
            corpus.add_event(e["kind"], e["issue_id"] or "", e["meeting_id"] or "",
                             e["thread_id"] or "", None)
        counts["events"] = len(events)

        docs = _rows(src, "SELECT * FROM documents") if "documents" in tables else []
        for d in docs:
            d.pop("rowid", None)
            corpus.upsert_document(d)
        counts["documents"] = len(docs)

        chunks = _rows(src, "SELECT * FROM doc_chunks") if "doc_chunks" in tables else []
        if chunks:
            with corpus._con() as con:
                for d in docs:
                    con.execute("DELETE FROM doc_chunks WHERE doc_id=%s", (d["id"],))
                for c in chunks:
                    con.execute(
                        "INSERT INTO doc_chunks (id, doc_id, meeting_id, town, idx, "
                        "page, text, emb) OVERRIDING SYSTEM VALUE "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (c["id"], c["doc_id"], c["meeting_id"] or "",
                         town_of.get(c["meeting_id"] or "", ""), c["idx"],
                         c["page"], c["text"] or "", _vec_or_none(c["emb"])))
                con.execute("SELECT setval(pg_get_serial_sequence('doc_chunks','id'), "
                            "COALESCE((SELECT MAX(id) FROM doc_chunks), 1))")
        counts["doc_chunks"] = len(chunks)

        dlinks = (_rows(src, "SELECT * FROM issue_documents")
                  if "issue_documents" in tables else [])
        by_doc: Dict[str, list] = {}
        for g in dlinks:
            by_doc.setdefault(g["issue_id"], []).append(
                (g["chunk_id"], g["doc_id"], g["score"], g["why"] or ""))
        for iid, ls in by_doc.items():
            corpus.link_doc_chunks(iid, ls)
        counts["issue_documents"] = len(dlinks)

        votes = _rows(src, "SELECT * FROM votes") if "votes" in tables else []
        by_meeting: Dict[str, list] = {}
        for v in votes:
            by_meeting.setdefault(v["meeting_id"], []).append(v)
        for mid, vs in by_meeting.items():
            corpus.replace_votes(mid, vs)
        counts["votes"] = len(votes)

        # -- the town becomes a row -------------------------------------
        now = time.time()
        with corpus._con() as con:
            for slug in sorted({t for t in town_of.values() if t}):
                con.execute(
                    "INSERT INTO towns (slug, name, status, added_at, updated_at) "
                    "VALUES (%s,%s,'live',%s,%s) ON CONFLICT (slug) DO NOTHING",
                    (slug, slug, now, now))
        counts["towns"] = len({t for t in town_of.values() if t})
    finally:
        src.close()
    return counts


def verify(src_path: str, corpus, sample: int = 200,
           verbose: bool = True) -> Dict[str, object]:
    """Prove the import landed. Counts per table, a bit-for-bit re-read of a
    random sample of vectors, and the issue rollups diffed store to store —
    because an import that cannot prove itself is a backup nobody has restored."""
    say = print if verbose else (lambda *a, **k: None)
    out: Dict[str, object] = {"ok": True, "tables": {}, "problems": []}
    src = _open_source(src_path)
    try:
        pairs = [("meetings", "meetings"), ("segments", "segments"),
                 ("issues", "issues"), ("issue_segments", "issue_segments"),
                 ("threads", "threads"), ("documents", "documents"),
                 ("doc_chunks", "doc_chunks"), ("votes", "votes")]
        with corpus._con() as con:
            for name, table in pairs:
                try:
                    want = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.OperationalError:
                    continue
                got = con.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
                out["tables"][name] = {"source": want, "studio": got}
                mark = "ok" if want == got else "MISMATCH"
                if want != got:
                    out["ok"] = False
                    out["problems"].append(f"{name}: {want} → {got}")
                say(f"  {name:<16} {want:>7,} → {got:>7,}  {mark}")

            # Vectors, bit for bit — with one deliberate exception. A segment
            # of pure filler ("as to", "yes.") carries a 1024-byte blob of
            # zeros, which passes `length(emb)>0` while having no direction at
            # all. Those become NULL on purpose, so the check is not "the bytes
            # match" but "the conversion is the one this module documents":
            # a real vector survives bit-identical, a zero one is absent.
            ids = [r["id"] for r in _rows(
                src, "SELECT id FROM segments WHERE emb IS NOT NULL "
                     "AND length(emb)>0")]
            random.seed(17)
            picked = random.sample(ids, min(sample, len(ids)))
            same = differ = blanked = wrongly_kept = 0
            for sid in picked:
                blob = src.execute("SELECT emb FROM segments WHERE id=?",
                                   (sid,)).fetchone()["emb"]
                row = con.execute("SELECT emb FROM segments WHERE id=%s",
                                  (sid,)).fetchone()
                here = embed.as_vec(row["emb"]) if row else None
                expect = _vec_or_none(blob)
                if expect is None:
                    if here is None:
                        blanked += 1
                    else:
                        wrongly_kept += 1
                elif here is not None and embed.to_bytes(here) == blob:
                    same += 1
                else:
                    differ += 1
            out["vectors"] = {"checked": len(picked), "identical": same,
                              "differing": differ, "blanked": blanked,
                              "wrongly_kept": wrongly_kept}
            if differ or wrongly_kept:
                out["ok"] = False
                if differ:
                    out["problems"].append(
                        f"{differ} of {len(picked)} vectors differ")
                if wrongly_kept:
                    out["problems"].append(
                        f"{wrongly_kept} zero-norm vectors were stored as zeros "
                        f"rather than NULL — cosine against them is undefined")
            say(f"  vectors          {same:>7,} / {len(picked) - blanked:,} "
                f"bit-identical  ({blanked} zero-norm → NULL, as intended)")

        # the rollups both stores compute independently
        from memory.store import Corpus
        desk = Corpus(db_path=src_path)
        for town in desk.live_towns():
            a = {i["id"]: (i["n_meetings"], i["n_segments"])
                 for i in desk.list_issues(town=town, limit=1000)}
            b = {i["id"]: (i["n_meetings"], i["n_segments"])
                 for i in corpus.list_issues(town=town, limit=1000)}
            if a != b:
                out["ok"] = False
                diff = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
                out["problems"].append(
                    f"{town}: {len(diff)} issue rollup(s) disagree: {diff[:5]}")
            say(f"  rollups {town:<9} {len(a):>7,} issues  "
                f"{'agree' if a == b else 'DISAGREE'}")
    finally:
        src.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m studio.import_desk",
        description="Carry a desk corpus into the Studio, and prove it landed.")
    ap.add_argument("--corpus", required=True, help="path to the desk's corpus.db")
    ap.add_argument("--dsn", default="", help="override STUDIO_DSN")
    ap.add_argument("--verify-only", action="store_true",
                    help="check an import that already ran; write nothing")
    ap.add_argument("--sample", type=int, default=200,
                    help="how many vectors to re-read bit-for-bit (default 200)")
    args = ap.parse_args(argv)

    from .store import PgCorpus
    corpus = PgCorpus(dsn=args.dsn)
    try:
        if not args.verify_only:
            print(f"importing {args.corpus} → {corpus.db_path}")
            t0 = time.time()
            counts = import_corpus(args.corpus, corpus)
            print(f"imported in {time.time() - t0:.1f}s")
            print()
        print("verifying…")
        result = verify(args.corpus, corpus, sample=args.sample)
        print()
        if result["ok"]:
            print("the record arrived whole — nothing re-derived.")
            return 0
        print("the import did NOT land cleanly:")
        for p in result["problems"]:
            print(f"  · {p}")
        return 1
    finally:
        corpus.close()


if __name__ == "__main__":
    sys.exit(main())
