"""Configuration from the environment, and nowhere else.

The desk reads its settings out of `~/Library/Application Support` and writes
its media under `~/Movies`; `czcore.paths` will happily *create* those
directories as a side effect of being asked where they are. None of that has
any meaning in a container, so none of it is imported here.

Secrets arrive as environment variables — from Secret Manager in the Studio,
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
        "STUDIO_DSN", "postgresql://studio:studio@localhost:55432/studio"))
    pool_min: int = field(default_factory=lambda: int(_env("STUDIO_POOL_MIN", "1")))
    pool_max: int = field(default_factory=lambda: int(_env("STUDIO_POOL_MAX", "8")))

    # -- the neural half ---------------------------------------------------
    # Absent by design: with no key the Studio still runs, search still works,
    # and the reader is told which half is missing rather than shown a blank.
    gemini_key: str = field(default_factory=lambda: _env("STUDIO_GEMINI_KEY"))

    # -- stewards ----------------------------------------------------------
    # The allowlist is server-side and small on purpose. specs/17 §3: steward
    # auth is thirty lines, not a platform.
    steward_allowlist: List[str] = field(default_factory=lambda: _env_list(
        "STUDIO_STEWARD_ALLOWLIST"))
    google_client_id: str = field(default_factory=lambda: _env("STUDIO_GOOGLE_CLIENT_ID"))
    # A shared secret for machine callers (the pipeline job, the drain). Never a
    # steward's identity — those are people, this is a robot.
    service_token: str = field(default_factory=lambda: _env("STUDIO_SERVICE_TOKEN"))

    # -- the edition -------------------------------------------------------
    site_base: str = field(default_factory=lambda: _env(
        "STUDIO_SITE_BASE", "https://communityai.studio"))
    edition_bucket: str = field(default_factory=lambda: _env("STUDIO_EDITION_BUCKET"))
    edition_dir: str = field(default_factory=lambda: _env(
        "STUDIO_EDITION_DIR", "/tmp/studio-edition"))

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
