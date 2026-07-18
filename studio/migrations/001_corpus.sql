-- The corpus, hosted. Mirrors memory/store.py's _SCHEMA table for table.
--
-- Every divergence from the desk is a comment, because a silent divergence
-- between two stores of the same record is the whole failure mode this file
-- exists to avoid. What changed, and why:
--
--   · `end` is a reserved word in Postgres — even `s.end` is a syntax error,
--     because the token after a dot must be a ColId. The column is `end_s` and
--     every read aliases it back, so dict keys are identical on both stores.
--   · segments_fts (a full second copy of every segment's text, kept in step by
--     hand, with no trigger) becomes a GENERATED tsvector column. The desync
--     class of bug does not exist here.
--   · `emb BLOB` becomes `vector(256)` — the same 256 lexical dimensions
--     memory/embed.py has always written, now typed. `emb_neural` is new and
--     studio-only: beside, never instead of.
--   · `town` is denormalised onto segments and doc_chunks. The desk reaches it
--     by JOIN; a record serving many towns cannot afford to, and cannot afford
--     a search that forgets to.
--   · Real foreign keys, at last. The desk's cascades are hand-rolled, and one
--     of them was wrong until the commit before this one.

CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------------ towns
-- specs/17 §5: a town becomes a row instead of a TEXT column repeated
-- everywhere, so onboarding is configuration rather than a deploy.
CREATE TABLE IF NOT EXISTS towns (
    slug       TEXT PRIMARY KEY,
    name       TEXT NOT NULL DEFAULT '',
    state      TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'onboarding',   -- live | onboarding | requested
    sources    JSONB NOT NULL DEFAULT '[]'::jsonb,   -- [{kind, url, body}]
    governance JSONB NOT NULL DEFAULT '{}'::jsonb,
    added_at   DOUBLE PRECISION,
    updated_at DOUBLE PRECISION
);

-- --------------------------------------------------------------- meetings
CREATE TABLE IF NOT EXISTS meetings (
    id             TEXT PRIMARY KEY,
    town           TEXT NOT NULL DEFAULT '',
    body           TEXT NOT NULL DEFAULT '',
    title          TEXT NOT NULL DEFAULT '',
    date           TEXT NOT NULL DEFAULT '',   -- ISO text, exactly as the desk stores it
    url            TEXT NOT NULL DEFAULT '',
    url_canon      TEXT NOT NULL DEFAULT '',
    source_kind    TEXT NOT NULL DEFAULT '',
    video_id       TEXT NOT NULL DEFAULT '',
    media_path     TEXT NOT NULL DEFAULT '',
    duration       DOUBLE PRECISION NOT NULL DEFAULT 0,
    uploader       TEXT NOT NULL DEFAULT '',
    origin         TEXT NOT NULL DEFAULT '',   -- captions | scribe | none
    n_segments     INTEGER NOT NULL DEFAULT 0,
    n_speakers     INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'queued',
    error          TEXT NOT NULL DEFAULT '',
    source_hash    TEXT NOT NULL DEFAULT '',
    shingles       TEXT NOT NULL DEFAULT '',   -- the desk's exact string, for parity
    info_json      TEXT NOT NULL DEFAULT '',   -- TEXT, not JSONB: the desk stores json.dumps
    analysis_json  TEXT NOT NULL DEFAULT '',   -- output and both stores must round-trip it
    summary        TEXT NOT NULL DEFAULT '',
    summary_origin TEXT NOT NULL DEFAULT '',
    added_at       DOUBLE PRECISION,
    updated_at     DOUBLE PRECISION
);
-- The desk has PK(id) and nothing else — find_by_url_canon and find_by_hash are
-- full scans there. At two meetings nobody noticed; at three hundred they would.
CREATE INDEX IF NOT EXISTS idx_mtg_url_canon ON meetings (url_canon) WHERE url_canon <> '';
CREATE INDEX IF NOT EXISTS idx_mtg_hash      ON meetings (source_hash) WHERE source_hash <> '';
CREATE INDEX IF NOT EXISTS idx_mtg_town      ON meetings (town, status);
CREATE INDEX IF NOT EXISTS idx_mtg_date      ON meetings ((date = ''), date DESC, added_at DESC);

-- --------------------------------------------------------------- segments
-- THE LEXICAL EMBEDDING DIMENSION IS PINNED IN FOUR PLACES, the way
-- czcore/models.py pins hashes (specs/17 §14 asks for exactly this):
--   1. memory/embed.py   DIM = 256          — the source of truth
--   2. this column       vector(256)
--   3. the CHECK below
--   4. meta('embed_lex_dim'), asserted against embed.DIM when a store opens
-- There is no dimension tag on the desk's blobs, so a mismatch does not
-- degrade: `mat @ qvec` raises a shape error. That is the migration hazard for
-- the whole pgvector move, and it is why the assertion is at connect time.
CREATE TABLE IF NOT EXISTS segments (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    town       TEXT NOT NULL DEFAULT '',   -- denormalised; the desk reaches it by JOIN
    idx        INTEGER NOT NULL DEFAULT 0,
    start      DOUBLE PRECISION NOT NULL DEFAULT 0,
    end_s      DOUBLE PRECISION NOT NULL DEFAULT 0,   -- `end` is reserved; aliased on read
    text       TEXT NOT NULL DEFAULT '',
    speaker    TEXT NOT NULL DEFAULT '',   -- read through NULLIF: transcript() promises None
    emb        vector(256),                -- lexical, deterministic, offline. NULL when the
                                           -- text is all filler (3.2% of the live corpus).
    emb_neural vector(768),                -- gemini-embedding-001 @ 768. Studio-only.
                                           -- An edition never depends on it.
    fts        tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    CONSTRAINT segments_emb_dim CHECK (emb IS NULL OR vector_dims(emb) = 256),
    CONSTRAINT segments_neural_dim CHECK (emb_neural IS NULL OR vector_dims(emb_neural) = 768)
);
CREATE INDEX IF NOT EXISTS idx_seg_meeting ON segments (meeting_id, idx);
CREATE INDEX IF NOT EXISTS idx_seg_town    ON segments (town);
CREATE INDEX IF NOT EXISTS idx_seg_fts     ON segments USING GIN (fts);
-- Cosine, because every vector memory/embed.py writes is L2-normalised and
-- memory.embed.cosine() is a bare dot product.
CREATE INDEX IF NOT EXISTS idx_seg_emb ON segments
    USING hnsw (emb vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_seg_emb_neural ON segments
    USING hnsw (emb_neural vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- ------------------------------------------------------------------- meta
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '');
-- The desk's _bump() counts writes to invalidate an in-process numpy matrix.
-- There is no such matrix here — HNSW is the index — so _bump is a documented
-- no-op. Worth noting the desk's SQL is a hard error in Postgres anyway:
--   ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1
--     -> column "value" is of type text but expression is of type integer
INSERT INTO meta (key, value) VALUES
    ('schema',        '1'),
    ('embed_lex_dim', '256'),
    ('embed_lex',     'blake2b-256:memory.embed'),
    ('embed_neural',  'gemini-embedding-001@768'),
    ('writes',        '0')
ON CONFLICT (key) DO NOTHING;

-- ----------------------------------------------------------------- issues
CREATE TABLE IF NOT EXISTS issues (
    id          TEXT PRIMARY KEY,
    town        TEXT NOT NULL DEFAULT '',
    name        TEXT NOT NULL DEFAULT '',
    name_origin TEXT NOT NULL DEFAULT 'extractive',
    aliases     TEXT NOT NULL DEFAULT '',   -- JSON list as TEXT (json.dumps, desk parity)
    keywords    TEXT NOT NULL DEFAULT '',
    related     TEXT NOT NULL DEFAULT '',
    centroid    vector(256),                -- was BLOB; mean of members, L2-normalised
    status      TEXT NOT NULL DEFAULT 'active',
    origin      TEXT NOT NULL DEFAULT 'auto',
    merged_into TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    added_at    DOUBLE PRECISION,
    updated_at  DOUBLE PRECISION,
    CONSTRAINT issues_centroid_dim CHECK (centroid IS NULL OR vector_dims(centroid) = 256)
);
CREATE INDEX IF NOT EXISTS idx_iss_town ON issues (town, status);

CREATE TABLE IF NOT EXISTS issue_segments (
    issue_id   TEXT   NOT NULL REFERENCES issues(id)   ON DELETE CASCADE,
    seg_id     BIGINT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    meeting_id TEXT   NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    score      DOUBLE PRECISION NOT NULL DEFAULT 0,
    why        TEXT NOT NULL DEFAULT '',    -- alias | related | steward | minted
    PRIMARY KEY (issue_id, seg_id)
);
CREATE INDEX IF NOT EXISTS idx_isg_meeting ON issue_segments (meeting_id);

CREATE TABLE IF NOT EXISTS threads (
    id             TEXT PRIMARY KEY,
    issue_id       TEXT NOT NULL UNIQUE REFERENCES issues(id) ON DELETE CASCADE,
    last_seen_date TEXT NOT NULL DEFAULT '',
    added_at       DOUBLE PRECISION,
    updated_at     DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS events (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind       TEXT NOT NULL,
    -- Deliberately NOT foreign keys. An event is a record of what the record
    -- noticed; outliving its meeting is honest history, not an orphan, and the
    -- desk never cleans these either. The cascade fix that landed before this
    -- schema left events alone on purpose, and so does this.
    issue_id   TEXT NOT NULL DEFAULT '',
    meeting_id TEXT NOT NULL DEFAULT '',
    thread_id  TEXT NOT NULL DEFAULT '',
    seen       SMALLINT NOT NULL DEFAULT 0,   -- integer, never BOOLEAN: the desk compares seen=0
    payload    TEXT NOT NULL DEFAULT '',
    added_at   DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_evt_issue  ON events (issue_id);
-- The desk has no index on the hot filter or the hot sort. list_events is
-- ORDER BY added_at DESC, and issues.digest() calls the first match "latest".
CREATE INDEX IF NOT EXISTS idx_evt_feed   ON events (added_at DESC);
CREATE INDEX IF NOT EXISTS idx_evt_unseen ON events (seen, added_at DESC) WHERE seen = 0;

-- -------------------------------------------------------------- documents
CREATE TABLE IF NOT EXISTS documents (
    id         TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL DEFAULT '',
    town       TEXT NOT NULL DEFAULT '',
    kind       TEXT NOT NULL DEFAULT '',
    title      TEXT NOT NULL DEFAULT '',
    date       TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL DEFAULT '',
    source     TEXT NOT NULL DEFAULT '',
    pages      INTEGER NOT NULL DEFAULT 0,
    n_chunks   INTEGER NOT NULL DEFAULT 0,
    sha256     TEXT NOT NULL DEFAULT '',   -- of the fetched bytes (the receipt)
    status     TEXT NOT NULL DEFAULT 'live',
    error      TEXT NOT NULL DEFAULT '',
    added_at   DOUBLE PRECISION,
    updated_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_doc_meeting ON documents (meeting_id);
CREATE INDEX IF NOT EXISTS idx_doc_town    ON documents (town, status);

CREATE TABLE IF NOT EXISTS doc_chunks (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    meeting_id TEXT NOT NULL DEFAULT '',
    town       TEXT NOT NULL DEFAULT '',
    idx        INTEGER NOT NULL DEFAULT 0,
    page       INTEGER NOT NULL DEFAULT 0,
    text       TEXT NOT NULL DEFAULT '',
    emb        vector(256),
    emb_neural vector(768),
    CONSTRAINT chunks_emb_dim CHECK (emb IS NULL OR vector_dims(emb) = 256)
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON doc_chunks (doc_id, idx);
CREATE INDEX IF NOT EXISTS idx_chunk_emb ON doc_chunks USING hnsw (emb vector_cosine_ops);

CREATE TABLE IF NOT EXISTS issue_documents (
    issue_id TEXT   NOT NULL REFERENCES issues(id)     ON DELETE CASCADE,
    chunk_id BIGINT NOT NULL REFERENCES doc_chunks(id) ON DELETE CASCADE,
    doc_id   TEXT   NOT NULL REFERENCES documents(id)  ON DELETE CASCADE,
    score    DOUBLE PRECISION NOT NULL DEFAULT 0,
    why      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (issue_id, chunk_id)
);
CREATE INDEX IF NOT EXISTS idx_idoc_doc ON issue_documents (doc_id);

-- ------------------------------------------------------------------ votes
CREATE TABLE IF NOT EXISTS votes (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    t          DOUBLE PRECISION NOT NULL DEFAULT 0,
    motion     TEXT NOT NULL DEFAULT '',   -- truncated to 400 by policy, not by the column
    outcome    TEXT NOT NULL DEFAULT '',
    tally      TEXT NOT NULL DEFAULT '',
    roll       TEXT NOT NULL DEFAULT '',   -- JSON [{name, vote, t, quote}]
    origin     TEXT NOT NULL DEFAULT 'extractive',
    added_at   DOUBLE PRECISION,
    updated_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_vote_meeting ON votes (meeting_id, t);

-- ------------------------------------------------- the Studio's own tables
-- The public "Add a meeting" stops composing a GitHub issue and POSTs here.
-- specs/16's contract shape is unchanged; it just lands in a queue now.
CREATE TABLE IF NOT EXISTS submissions (
    id         TEXT PRIMARY KEY,
    url        TEXT NOT NULL DEFAULT '',
    url_canon  TEXT NOT NULL DEFAULT '',
    town       TEXT NOT NULL DEFAULT '',
    body       TEXT NOT NULL DEFAULT '',
    date       TEXT NOT NULL DEFAULT '',
    note       TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'submitted',  -- submitted|approved|queued|live|rejected
    meeting_id TEXT NOT NULL DEFAULT '',
    reason     TEXT NOT NULL DEFAULT '',
    added_at   DOUBLE PRECISION,
    updated_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_sub_queue ON submissions (status, added_at DESC);
CREATE INDEX IF NOT EXISTS idx_sub_canon ON submissions (url_canon) WHERE url_canon <> '';

-- A meeting with no captions parks here for the desk drain (specs/17 §6.4).
-- Wave 1 only files them honestly; wave 2 gives a station Mac somewhere to poll.
CREATE TABLE IF NOT EXISTS asr_tasks (
    id         TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL DEFAULT '',
    town       TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'parked',   -- parked | claimed | done | failed
    claimed_by TEXT NOT NULL DEFAULT '',
    note       TEXT NOT NULL DEFAULT '',
    added_at   DOUBLE PRECISION,
    updated_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_asr_status ON asr_tasks (status, added_at);

-- Accounts exist for stewards only. Readers never log in — that is covenant,
-- not configuration (specs/17 §9).
CREATE TABLE IF NOT EXISTS stewards (
    email    TEXT PRIMARY KEY,
    name     TEXT NOT NULL DEFAULT '',
    towns    TEXT[] NOT NULL DEFAULT '{}',   -- empty means every town
    added_at DOUBLE PRECISION
);

-- The record remembers its own edits (specs/14 §8), now including who made them.
CREATE TABLE IF NOT EXISTS audit (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    steward  TEXT NOT NULL DEFAULT '',
    verb     TEXT NOT NULL,
    target   TEXT NOT NULL DEFAULT '',
    town     TEXT NOT NULL DEFAULT '',
    payload  JSONB NOT NULL DEFAULT '{}'::jsonb,
    added_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_audit_feed ON audit (added_at DESC);

-- The AI-audit ledger, ported from the desk: every token attributed, and
-- visible on the steward console rather than in a bill nobody reads.
CREATE TABLE IF NOT EXISTS spend (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model    TEXT NOT NULL DEFAULT '',
    purpose  TEXT NOT NULL DEFAULT '',   -- embed | summary | delta | label
    town     TEXT NOT NULL DEFAULT '',
    target   TEXT NOT NULL DEFAULT '',
    units    INTEGER NOT NULL DEFAULT 0, -- tokens, or items for an embedding batch
    added_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_spend_feed ON spend (added_at DESC);
