"""One interface, two stores — what the engine is allowed to assume.

`memory/` is the civic-record engine: ingest, issues, votes, documents, the
analysis passes. Until now it had exactly one place to put things, and the
distinction between "the record's logic" and "SQLite" was never forced. specs/17
forces it: the desk keeps its one file under `~/Movies`, publicrecord keeps a
Postgres the towns share, and the same hand-audited issue engine has to run
against both and produce the same record.

So this is the line. Anything below it may differ between stores; anything
above it may not. `Corpus` (SQLite) satisfies this as written — that is the
acceptance test, not an aspiration — and `record.store.PgCorpus` implements it
beside.

It is a `Protocol`, not a base class, on purpose. `Corpus` is the most
hand-audited object in the tree and giving it a parent changes its MRO and its
`__init__` for no benefit; structural typing asks only that the methods match.
`isinstance(Corpus(...), CorpusStore)` is checked in the suite.

The four contracts a store cannot see for itself, written down for the first
time because a second implementation is the moment they start to matter:

**Ordering.** `list_meetings` and `list_documents` are newest-first with blank
dates last. `transcript` and `segments_of` are in `idx` order. `issue_appearances`
is oldest-first with blank dates first, and its beads are in `start` order —
`issues.delta` slices `beads[:30]` and `beads[:3]` and would quietly describe
the wrong moment if that changed. `list_events` is newest-first; `digest` calls
the first match "latest" and is only correct under it.

**Embeddings are opaque.** A store hands back whatever its column holds — raw
float32 bytes at the desk, a pgvector array in publicrecord. Callers read them
only through `embed.as_vec()`. No caller may assume `bytes`, and none may
assume a dimension: `embed.DIM` is the single source of truth and there is no
dim tag on the desk's blobs, so a mismatch raises a shape error rather than
degrading. A zero-norm vector (3.2% of the live corpus — segments that are
`[music]` or pure filler) is stored as absent, not as zeros, and never appears
in a vector result on either store.

**None is not empty string.** `transcript()` promises `speaker: None` for an
unattributed segment, never `""`. The desk gets this from `r["speaker"] or None`;
a store with a `NOT NULL DEFAULT ''` column owes the same conversion.

**Ids are opaque tokens.** Segment, chunk, event and vote ids are unique
positive integers, stable for the row's lifetime. Nothing may assume density,
contiguity, or that a higher id means a later row — SQLite's AUTOINCREMENT and
a Postgres identity column gap differently, and the engine treats them as
tokens everywhere.
"""

from __future__ import annotations

from typing import Any, ContextManager, Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable


@runtime_checkable
class CorpusStore(Protocol):
    """The record, however it is stored."""

    # -- capability flags --------------------------------------------------
    # Neither store lies about what it has. `fts` false means keyword search
    # has degraded to a scan and the UI says so; `semantic` false means there
    # are no vectors to search at all.
    db_path: str
    fts: bool

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Release whatever the store holds. A no-op at the desk (every
        operation already opens and closes its own connection); returns the
        pool in publicrecord."""

    def unit(self) -> ContextManager:
        """One transaction across several calls.

        The curation verbs are call *sequences* — merge is `merge_issues` then
        `reassign_issue` then `get_issue` — and each call commits on its own.
        With one writer on one file that is invisible. With N workers against
        one Postgres it is a half-done merge, so publicrecord needs a way to say
        "these together or not at all". At the desk this yields immediately and
        changes nothing, which is why it can be added without touching a single
        existing caller."""

    # -- meetings ----------------------------------------------------------

    def upsert_meeting(self, m: dict) -> None: ...
    def set_status(self, meeting_id: str, status: str, error: str = "") -> None: ...
    def get_meeting(self, meeting_id: str) -> Optional[dict]: ...
    def list_meetings(self, limit: int = 500) -> List[dict]: ...
    def transcript(self, meeting_id: str) -> List[dict]: ...
    def forget(self, meeting_id: str) -> bool: ...

    # -- segments ----------------------------------------------------------

    def replace_segments(self, meeting_id: str, segments: List[dict]) -> int: ...
    def live_segments(self, town: str = "") -> List[dict]: ...
    def segments_of(self, meeting_id: str) -> List[dict]: ...
    def live_towns(self) -> List[str]: ...

    # -- dedupe ------------------------------------------------------------

    def find_by_url_canon(self, url_canon: str) -> Optional[dict]: ...
    def find_by_hash(self, source_hash: str) -> Optional[dict]: ...
    def find_by_shingles(self, shingles: str,
                         threshold: float = 0.9) -> Optional[dict]: ...

    # -- search ------------------------------------------------------------

    def search(self, q: str, limit: int = 60, town: str = "") -> List[dict]:
        """Words and meaning, blended, every hit time-coded to a segment.

        The hit envelope is fixed and identical on both stores:
        `meeting_id, seg_id, t, end, text, speaker, title, date, body, town,
        url, source_kind, video_id, media_path, duration, score, why` —
        where `why` is one of `word` / `related` / `both`, and is shown to the
        reader as a provenance chip. A store may add to the vocabulary (the
        Studio adds `meaning` for its neural half); it may not change what the
        existing values mean."""

    def semantic(self, qvec, limit: int = 40, town: str = "") -> List[dict]: ...

    # -- stats -------------------------------------------------------------

    def stats(self) -> dict: ...

    # -- issues ------------------------------------------------------------

    def upsert_issue(self, issue: dict) -> None: ...
    def get_issue(self, issue_id: str) -> Optional[dict]: ...
    def list_issues(self, town: str = "", status: str = "active",
                    limit: int = 300) -> List[dict]: ...
    def issue_keywords(self, active_only: bool = True) -> List[dict]: ...
    def issue_appearances(self, issue_id: str) -> List[dict]: ...
    def link_segments(self, issue_id: str, links: List[tuple]) -> int: ...
    def linked_seg_ids(self, meeting_id: str) -> set:
        """Which of a meeting's segments already belong to some issue — what
        the candidate queue needs to know what is left over. Replaces a raw
        SELECT the issue engine used to run through `corpus._con()`."""

    def unlink_meeting(self, issue_id: str, meeting_id: str) -> int:
        """Detach one meeting's segments from one issue — the second half of
        split, which used to reach past the store to do it."""

    def clear_issue_links(self, issue_id: str) -> None: ...
    def clear_meeting_links(self, meeting_id: str) -> None: ...
    def recompute_centroid(self, issue_id: str): ...
    def set_issue_status(self, issue_id: str, status: str) -> None: ...
    def rename_issue(self, issue_id: str, name: str,
                     aliases: Optional[list] = None) -> Optional[dict]: ...
    def merge_issues(self, src_ids: List[str], dst_id: str) -> Optional[dict]: ...
    def delete_issue(self, issue_id: str) -> bool: ...
    def clear_auto_issues(self, town: str = "") -> int: ...

    # -- threads + events --------------------------------------------------

    def follow(self, issue_id: str) -> Optional[dict]: ...
    def unfollow(self, issue_id: str) -> bool: ...
    def get_thread(self, issue_id: str) -> Optional[dict]: ...
    def list_threads(self) -> List[dict]: ...
    def add_event(self, kind: str, issue_id: str = "", meeting_id: str = "",
                  thread_id: str = "", payload: Optional[dict] = None) -> int: ...
    def list_events(self, unseen_only: bool = False,
                    limit: int = 100) -> List[dict]: ...
    def unseen_count(self) -> int: ...
    def mark_seen(self, issue_id: str = "") -> int: ...
    def advance_thread(self, issue_id: str, last_seen_date: str) -> None: ...

    # -- documents ---------------------------------------------------------

    def upsert_document(self, d: dict) -> None: ...
    def replace_doc_chunks(self, doc_id: str, chunks: List[dict]) -> int: ...
    def get_document(self, doc_id: str) -> Optional[dict]: ...
    def list_documents(self, town: str = "", meeting_id: str = "",
                       limit: int = 300) -> List[dict]: ...
    def doc_chunks_of(self, doc_id: str) -> List[dict]: ...
    def forget_document(self, doc_id: str) -> bool: ...
    def link_doc_chunks(self, issue_id: str, links: List[tuple]) -> int: ...
    def clear_doc_links(self, doc_id: str) -> None: ...
    def issue_paper(self, issue_id: str) -> List[dict]: ...

    # -- votes -------------------------------------------------------------

    def replace_votes(self, meeting_id: str, votes: List[dict]) -> int: ...
    def votes_of(self, meeting_id: str) -> List[dict]: ...
    def all_votes(self, town: str = "") -> List[dict]: ...
