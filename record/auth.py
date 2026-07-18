"""Who is allowed to change the record — and nobody else, for anything else.

specs/17 §3 rejected Firebase partly on this: steward auth is thirty lines, not
a platform. Here they are. A steward signs in with Google, the browser hands
back an ID token, this verifies the token's signature against Google's public
keys and checks the email against a server-side allowlist. There is no user
table to register into, no password to reset, no session store — an allowlist
of a handful of people is the honest shape of the problem, and IAP is the
graduation path if that ever stops being true (config, not code).

**Readers are never touched by any of this.** There is no reader account, no
reader cookie, no reader anything: that is covenant, not configuration
(specs/17 §9). Nothing in this module is on the path of a page a resident
reads, and the API's public endpoints must never import `require_steward`.

Two failure modes are deliberate. With no `RECORD_GOOGLE_CLIENT_ID` and no
allowlist configured, every steward route returns 503 with a sentence saying
the console is not configured — it does not fall open, and it does not pretend
to be broken. And a token that verifies but whose email is not on the list gets
403, not 401: the difference matters, because retrying the sign-in will not
help and the message should say so.

The verification itself is deliberately not hand-rolled. `google-auth` is a
guarded import; without it the module reports itself unconfigured rather than
accepting anything. Writing an RS256/JWKS verifier by hand is exactly the sort
of thing that looks fine until the day a key rotates.
"""

from __future__ import annotations

import time
from typing import Optional

# The verifier is optional at import time and never at use. The reason it is
# missing is kept verbatim rather than flattened to "not installed": google-auth
# imports fine on its own and then fails on its *transport*, so the honest
# message is "install google-auth[requests]", not "install google-auth" — which
# is advice that would send someone in a circle.
try:
    from google.auth.transport import requests as _g_requests
    from google.oauth2 import id_token as _g_id_token
    _HAVE_GOOGLE_AUTH = True
    _IMPORT_ERROR = ""
except Exception as _exc:                       # pragma: no cover
    _g_requests = _g_id_token = None
    _HAVE_GOOGLE_AUTH = False
    _IMPORT_ERROR = str(_exc)

# Google's own issuers. A token claiming any other issuer is not a Google
# token, whatever else it verifies against.
_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class AuthError(Exception):
    """Raised with the status the caller should return, so the route layer does
    not have to guess whether a failure was "sign in" or "you may not"."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def configured(settings=None) -> bool:
    from .settings import settings as default
    s = settings or default
    return bool(_HAVE_GOOGLE_AUTH and s.google_client_id and s.steward_allowlist)


def why_unconfigured(settings=None) -> str:
    from .settings import settings as default
    s = settings or default
    if not _HAVE_GOOGLE_AUTH:
        return (f"google-auth[requests] is not installed ({_IMPORT_ERROR})"
                if _IMPORT_ERROR else "google-auth[requests] is not installed")
    if not s.google_client_id:
        return "RECORD_GOOGLE_CLIENT_ID is not set"
    if not s.steward_allowlist:
        return "RECORD_STEWARD_ALLOWLIST is empty — no one is a steward yet"
    return ""


def verify_token(token: str, settings=None) -> dict:
    """Turn a Google ID token into a steward, or raise AuthError.

    Returns `{"email", "name", "sub"}`. The email is lowercased because the
    allowlist is, and a steward who signs in with a differently-cased address
    is the same person."""
    from .settings import settings as default
    s = settings or default

    if not configured(s):
        raise AuthError(503, f"the steward console is not configured: "
                             f"{why_unconfigured(s)}")
    if not token:
        raise AuthError(401, "sign in to curate the record")
    try:
        claims = _g_id_token.verify_oauth2_token(
            token, _g_requests.Request(), s.google_client_id)
    except Exception as exc:
        raise AuthError(401, f"that sign-in did not verify ({exc})") from exc

    if claims.get("iss") not in _ISSUERS:
        raise AuthError(401, "that token was not issued by Google")
    if not claims.get("email_verified"):
        raise AuthError(403, "that Google account has an unverified address")
    email = (claims.get("email") or "").strip().lower()
    if not s.is_steward(email):
        # 403 and not 401: signing in again will not help, and the message
        # should not send someone round a loop that cannot succeed.
        raise AuthError(403, f"{email} is not a steward of this record")
    return {"email": email, "name": claims.get("name") or "",
            "sub": claims.get("sub") or ""}


def bearer(header: Optional[str]) -> str:
    """The token out of an Authorization header, or empty."""
    if not header:
        return ""
    parts = header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


def verify_service(header: Optional[str], settings=None) -> bool:
    """Machine callers — the pipeline job, and one day the drain. A shared
    secret, never a steward's identity: those are people, this is a robot, and
    an audit row that says "the nightly job did it" should not name a person."""
    from .settings import settings as default
    s = settings or default
    token = bearer(header)
    if not (s.service_token and token):
        return False
    # Constant-time: the comparison is cheap and the habit is cheaper than
    # the day it matters.
    import hmac
    return hmac.compare_digest(token, s.service_token)


def audit(corpus, steward: str, verb: str, target: str = "", town: str = "",
          payload: Optional[dict] = None) -> None:
    """The record remembers its own edits (specs/14 §8) — now with a name and a
    time against each one. Never raises: an audit write that fails must not
    undo a curation the steward already saw succeed. It complains instead."""
    import json
    try:
        with corpus._con() as con:
            con.execute(
                "INSERT INTO audit (steward, verb, target, town, payload, "
                "added_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (steward, verb, target, town, json.dumps(payload or {}),
                 time.time()))
    except Exception as exc:                    # pragma: no cover
        print(f"  ! the audit log refused a {verb} by {steward}: {exc}")
