"""The fetch proxy — the web app's Webshare workaround, shared with desktop.

YouTube gates caption/timedtext delivery by IP reputation now; the
community-highlighter web app routes those requests through a Webshare
rotating residential proxy, and this module brings the same credentials to
the suite. Configuration comes from the same environment variable names the
web app uses (one account, both apps), or from a settings file the app's
Settings page writes:

    WEBSHARE_PROXY_USERNAME / WEBSHARE_PROXY_PASSWORD
    WEBSHARE_PROXY_HOST (default p.webshare.io:80)

Covenant note: this is the user's own proxy account, configured by the
user, used only for the fetches the user asks for. The credentials stay in
app support on this machine; the status surface masks the username and
never returns the password.
"""

from __future__ import annotations

import json
import os
from typing import Optional
from urllib.parse import quote

from .paths import support_dir

DEFAULT_HOST = "p.webshare.io:80"
_SESSION_SUFFIXES = ("-1", "-rotate", "-country-us")


def _file() -> "os.PathLike":
    return support_dir() / "proxy.json"


def get_config() -> dict:
    """{username, password, host, source} — env wins over the settings file,
    matching how the web app deploys (env on Render, file here)."""
    user = os.getenv("WEBSHARE_PROXY_USERNAME", "")
    pw = os.getenv("WEBSHARE_PROXY_PASSWORD", "")
    host = os.getenv("WEBSHARE_PROXY_HOST", "")
    if user and pw:
        return {"username": user, "password": pw,
                "host": host or DEFAULT_HOST, "source": "env"}
    try:
        d = json.loads(_file().read_text())
        if d.get("username") and d.get("password"):
            return {"username": str(d["username"]),
                    "password": str(d["password"]),
                    "host": str(d.get("host") or DEFAULT_HOST),
                    "source": "file"}
    except (OSError, ValueError):
        pass
    return {"username": "", "password": "", "host": host or DEFAULT_HOST,
            "source": None}


def _read_file() -> dict:
    try:
        return json.loads(_file().read_text())
    except (OSError, ValueError):
        return {}


def _write_file(d: dict):
    _file().write_text(json.dumps(d))
    try:
        os.chmod(_file(), 0o600)  # credentials: owner-only
    except OSError:
        pass


def set_config(username: str, password: str, host: str = "") -> dict:
    """Write (or clear, with empty strings) the settings-file credentials.
    The relay preference riding in the same file is preserved either way."""
    username, password = username.strip(), password.strip()
    d = _read_file()
    if not (username and password):
        d.pop("username", None)
        d.pop("password", None)
        d.pop("host", None)
    else:
        d.update({"username": username, "password": password,
                  "host": (host or "").strip() or DEFAULT_HOST})
    if d:
        _write_file(d)
    else:
        try:
            _file().unlink()
        except OSError:
            pass
    return status()


def relay_enabled() -> bool:
    """The community caption service (the web app's public transcript
    engine): on unless the user turned it off."""
    return bool(_read_file().get("relay", True))


def set_relay(enabled: bool) -> dict:
    d = _read_file()
    if enabled:
        d.pop("relay", None)   # default-true needs no stored key
    else:
        d["relay"] = False
    if d:
        _write_file(d)
    else:
        try:
            _file().unlink()
        except OSError:
            pass
    return status()


def build_url(username: str, password: str, host: str = DEFAULT_HOST) -> str:
    """Exactly the web app's construction: rotating-session suffix (-1)
    unless one is already present, credentials URL-encoded."""
    if not username.endswith(_SESSION_SUFFIXES):
        username = f"{username}-1"
    return (f"http://{quote(username, safe='')}:{quote(password, safe='')}"
            f"@{host or DEFAULT_HOST}/")


def proxy_url() -> Optional[str]:
    """The URL every fetch passes to yt-dlp / urllib, or None when unset."""
    c = get_config()
    if not (c["username"] and c["password"]):
        return None
    return build_url(c["username"], c["password"], c["host"])


def status() -> dict:
    """What UIs may show. Password never leaves this module."""
    c = get_config()
    enabled = bool(c["username"] and c["password"])
    masked = ""
    if enabled:
        u = c["username"]
        masked = (u[:3] + "…" + u[-2:]) if len(u) > 6 else (u[:2] + "…")
    return {"enabled": enabled, "source": c["source"], "host": c["host"],
            "username_masked": masked, "relay": relay_enabled()}
