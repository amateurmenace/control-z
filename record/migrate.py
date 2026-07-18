"""Numbered SQL, applied once, recorded — because the desk has no such thing.

`memory/store.py` bootstraps with `CREATE TABLE IF NOT EXISTS` on every open,
which means schema evolution there is "add a line to _SCHEMA" and a database
that predates the line stays broken forever, silently. There is no
`user_version`, no ALTER anywhere in `memory/`, and the live corpus reports
version 0. At a desk, where the file is yours and re-ingest is cheap, that is
survivable. A Postgres several towns and a nightly job share is not.

So: plain `.sql` files, numbered, applied in order inside a transaction, each
recorded in `schema_migrations`. No Alembic — it drags SQLAlchemy in for a
schema that is hand-shaped and means to stay that way.

    python -m record.migrate            # apply what is pending
    python -m record.migrate --status   # say what is applied without applying
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Tuple

MIGRATIONS = Path(__file__).resolve().parent / "migrations"

_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL DEFAULT '',
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now())
"""


def available() -> List[Tuple[int, str, Path]]:
    """Every migration on disk, in order. A file that does not start with
    digits is not a migration and is skipped rather than guessed at."""
    out = []
    for p in sorted(MIGRATIONS.glob("*.sql")):
        head = p.stem.split("_", 1)
        if not head[0].isdigit():
            continue
        out.append((int(head[0]), head[1] if len(head) > 1 else p.stem, p))
    return out


def applied(con) -> set:
    con.execute(_TABLE)
    return {r[0] for r in con.execute(
        "SELECT version FROM schema_migrations").fetchall()}


def migrate(dsn: str = "", quiet: bool = False) -> List[int]:
    """Apply every pending migration. Returns the versions applied, which is
    empty on a second run — idempotence is the property that matters here, and
    the suite asserts it."""
    import psycopg
    from .settings import settings

    done: List[int] = []
    with psycopg.connect(dsn or settings.dsn, autocommit=False) as con:
        have = applied(con)
        con.commit()
        for version, name, path in available():
            if version in have:
                continue
            sql = path.read_text(encoding="utf-8")
            # One transaction per migration: a half-applied schema is worse
            # than an unapplied one, and Postgres can roll DDL back.
            with con.transaction():
                con.execute(sql)
                con.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                    (version, name))
            done.append(version)
            if not quiet:
                print(f"  applied {version:03d} {name}")
    return done


def status(dsn: str = "") -> List[Tuple[int, str, bool]]:
    import psycopg
    from .settings import settings

    with psycopg.connect(dsn or settings.dsn) as con:
        have = applied(con)
        con.commit()
    return [(v, n, v in have) for v, n, _ in available()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m record.migrate",
        description="Apply publicrecord's schema migrations.")
    ap.add_argument("--dsn", default="", help="override RECORD_DSN")
    ap.add_argument("--status", action="store_true",
                    help="report what is applied, change nothing")
    args = ap.parse_args(argv)

    from .settings import settings
    dsn = args.dsn or settings.dsn

    if args.status:
        for version, name, ok in status(dsn):
            print(f"  {'✓' if ok else '·'} {version:03d} {name}")
        return 0

    print(f"migrating {Settings_redacted(dsn)}…")
    t0 = time.time()
    done = migrate(dsn)
    if done:
        print(f"{len(done)} migration(s) applied in {time.time() - t0:.1f}s")
    else:
        print("already up to date")
    return 0


def Settings_redacted(dsn: str) -> str:
    from .settings import Settings
    return Settings(dsn=dsn).redacted()


if __name__ == "__main__":
    sys.exit(main())
