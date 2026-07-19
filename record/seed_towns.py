"""Put the two towns the record serves into the database, with their rules.

The intake rules in `record/sources.py` were not designed at a desk — they were
tuned against live polls of the actual channels on 2026-07-19, which is why they
exclude *TV on TV* and *(Spanish) Recycling in the Club* by name and why Boston's
committee rule matches a date-shape rather than the words "Committee on". Those
findings are worth more than the code around them, so this command writes them
into `towns.sources` where a steward can see and edit them, rather than leaving
them as constants only a programmer can reach.

It is a seed, not a migration. It refuses to overwrite a town whose rules a
steward has already edited unless asked, because the whole point of the console
is that the rules become theirs.

    python -m record.seed_towns              # add what is missing
    python -m record.seed_towns --force      # overwrite, losing steward edits
    python -m record.seed_towns --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import sources


def seed(corpus, force: bool = False, dry_run: bool = False,
         verbose: bool = True) -> dict:
    say = print if verbose else (lambda *a, **k: None)
    out = {"added": [], "updated": [], "kept": []}
    now = time.time()
    with corpus._con() as con:
        for slug, town in sources.SEEDS.items():
            row = con.execute("SELECT slug, sources FROM towns WHERE slug=%s",
                              (slug,)).fetchone()
            payload = json.dumps(town["sources"])
            if row is None:
                if not dry_run:
                    con.execute(
                        "INSERT INTO towns (slug, name, state, status, sources, "
                        "added_at, updated_at) VALUES (%s,%s,%s,'live',%s,%s,%s)",
                        (town["slug"], town["name"], town["state"], payload,
                         now, now))
                out["added"].append(slug)
                say(f"  + {slug}: {len(town['sources'])} source(s), "
                    f"{sum(len(s['bodies']) for s in town['sources'])} body rules")
            else:
                existing = row["sources"]
                have = (existing if isinstance(existing, list)
                        else json.loads(existing or "[]"))
                # A town with no sources has nothing for the guard to protect.
                # The import creates bare town rows from whatever `meetings.town`
                # said, so refusing to seed those meant a freshly imported
                # corpus could never get its intake rules without --force —
                # which is a flag that also destroys real steward edits, and so
                # exactly the wrong thing to teach someone to reach for.
                if force or not have:
                    if not dry_run:
                        con.execute(
                            "UPDATE towns SET sources=%s, updated_at=%s "
                            "WHERE slug=%s", (payload, now, slug))
                    out["updated"].append(slug)
                    say(f"  ~ {slug}: {len(town['sources'])} source(s) written"
                        + (" (steward edits replaced)" if have else
                           " (the row had none)"))
                else:
                    out["kept"].append(slug)
                    say(f"  = {slug}: left alone ({len(have)} source(s) "
                        f"already configured)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m record.seed_towns",
        description="Seed Brookline and Boston with their intake rules.")
    ap.add_argument("--dsn", default="")
    ap.add_argument("--force", action="store_true",
                    help="overwrite rules a steward may have edited")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    from .store import PgCorpus
    corpus = PgCorpus(dsn=args.dsn)
    try:
        print(f"seeding {corpus.db_path}"
              + (" (dry run — nothing written)" if args.dry_run else ""))
        result = seed(corpus, force=args.force, dry_run=args.dry_run)
        print(f"\n{len(result['added'])} added, {len(result['updated'])} replaced, "
              f"{len(result['kept'])} left as the steward had them")
        if result["kept"] and not args.force:
            print("  (--force replaces those, and loses whatever they changed)")
        return 0
    finally:
        corpus.close()


if __name__ == "__main__":
    sys.exit(main())
