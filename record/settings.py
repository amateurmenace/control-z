"""Configuration from the environment, and nowhere else.

The desk reads its settings out of `~/Library/Application Support` and writes
its media under `~/Movies`; `czcore.paths` will happily *create* those
directories as a side effect of being asked where they are. None of that has
any meaning in a container, so none of it is imported here.

Secrets arrive as environment variables — from Secret Manager in publicrecord,
from a `.env` the developer never commits locally. Nothing in this file has a
secret as its default, and `redacted()` exists so a store can say which
database it is talking to without putting a password in a log line.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

# The neural half of search. Pinned here, in the schema, in the CHECK
# constraint, and in meta('embed_neural') — the way czcore/models.py pins
# hashes, because a silently-changed embedding model is a corpus that no longer
# agrees with itself (specs/17 §14).
NEURAL_MODEL = "gemini-embedding-001"
NEURAL_DIM = 768


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_list(name: str) -> List[str]:
    return [x.strip().lower() for x in _env(name).replace(",", " ").split() if x.strip()]


@dataclass
class Settings:
    """Everything the service needs to know, read once at import."""

    # -- the corpus --------------------------------------------------------
    dsn: str = field(default_factory=lambda: _env(
        "RECORD_DSN", "postgresql://record:record@localhost:55432/record"))
    pool_min: int = field(default_factory=lambda: int(_env("RECORD_POOL_MIN", "1")))
    pool_max: int = field(default_factory=lambda: int(_env("RECORD_POOL_MAX", "8")))

    # -- the spend ceiling -------------------------------------------------
    # A hard stop on embedding, checked against the `spend` ledger before each
    # batch is bought rather than after — so it survives a restart, a second
    # job, and a job somebody ran last week. The full Brookline+Boston backfill
    # at present scale estimates well under a dollar; this is a runaway brake,
    # not a budget. The GCP project budget ($100, alerting at 50/90/100%) is
    # the backstop underneath it, and it watches every service, not just this.
    spend_cap_usd: float = field(default_factory=lambda: float(
        _env("RECORD_SPEND_CAP_USD", "100") or 100))

    # -- the neural half ---------------------------------------------------
    # Absent by design: with no key publicrecord still runs, search still works,
    # and the reader is told which half is missing rather than shown a blank.
    gemini_key: str = field(default_factory=lambda: _env("RECORD_GEMINI_KEY"))

    # -- stewards ----------------------------------------------------------
    # The allowlist is server-side and small on purpose. specs/17 §3: steward
    # auth is thirty lines, not a platform.
    steward_allowlist: List[str] = field(default_factory=lambda: _env_list(
        "RECORD_STEWARD_ALLOWLIST"))
    google_client_id: str = field(default_factory=lambda: _env("RECORD_GOOGLE_CLIENT_ID"))
    # A shared secret for machine callers (the pipeline job, the drain). Never a
    # steward's identity — those are people, this is a robot.
    service_token: str = field(default_factory=lambda: _env("RECORD_SERVICE_TOKEN"))

    # -- who may ask from a browser ----------------------------------------
    # The edition is static and lives somewhere else — GitHub Pages today, a
    # bucket behind a CDN tomorrow — so the one call the reader makes to this
    # service is cross-origin, and a browser will not make it unless the
    # service says out loud that it consents. This is that consent.
    #
    # It is an allowlist rather than `*` for the reason every other list in
    # this file is one: naming who may ask costs a line, and a wildcard is a
    # decision nobody ever revisits. It is also the exact mirror of the CSP
    # exception `web/emit.py` writes into the edition — the reader names the
    # service it may call, the service names the readers that may call it, and
    # neither half works alone. When the two eventually share an origin behind
    # one load balancer, both halves go quiet together.
    #
    # Note what is deliberately absent: credentials. No reader is identified,
    # so no reader's request carries one, so this never allows them — and the
    # steward console is served from this same origin and needs none of it.
    reader_origins: List[str] = field(default_factory=lambda: _env_list(
        "RECORD_READER_ORIGINS"))

    # -- the edition -------------------------------------------------------
    site_base: str = field(default_factory=lambda: _env(
        "RECORD_SITE_BASE", "https://communityai.studio"))
    # The address a pressed edition tells its reader to call for meaning-search
    # and freshness. Empty means "press a purely static edition", which is the
    # right default everywhere except the job that presses the live site: an
    # edition is complete without it, and baking a guessed URL into thousands
    # of pages is worse than baking none.
    api_base: str = field(default_factory=lambda: _env("RECORD_API_BASE"))
    edition_bucket: str = field(default_factory=lambda: _env("RECORD_EDITION_BUCKET"))
    edition_dir: str = field(default_factory=lambda: _env(
        "RECORD_EDITION_DIR", "/tmp/record-edition"))

    @property
    def has_neural(self) -> bool:
        return bool(self.gemini_key)

    @property
    def has_auth(self) -> bool:
        return bool(self.google_client_id and self.steward_allowlist)

    def redacted(self) -> str:
        """The DSN with every secret removed — safe for a log line or a health
        endpoint, which is the only reason a service ever prints its DSN.

        This used to return the string verbatim whenever it was not clean URI
        form, which is exactly backwards: libpq also accepts keyword/value
        (`host=… password=…`) and URI form with the password in the query
        string, and both fell through the early returns straight onto an
        anonymous /api/health response. A redactor whose failure mode is
        "publish it" is worse than none, so this one redacts first and parses
        second, and anything it does not recognise it refuses to echo."""
        import re
        dsn = (self.dsn or "").strip()
        if not dsn:
            return ""
        # keyword/value form, and any URI query parameter
        out = re.sub(r"(?i)\b(password|pgpassword)\s*=\s*[^\s&]+",
                     r"\1=***", dsn)
        if "://" in out:
            scheme, rest = out.split("://", 1)
            if "@" in rest:
                creds, host = rest.rsplit("@", 1)
                user = creds.split(":", 1)[0]
                out = f"{scheme}://{user}:***@{host}"
        if out == dsn and re.search(r"(?i)password", dsn):
            # It carries a password and nothing above matched its shape. Do not
            # guess, and do not print it.
            return "<dsn redacted>"
        return out

    def is_steward(self, email: str) -> bool:
        return bool(email) and email.strip().lower() in self.steward_allowlist


settings = Settings()
