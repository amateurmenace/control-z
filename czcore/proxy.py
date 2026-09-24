"""The fetch proxy — a Webshare rotating residential pool, OFF until switched on.

YouTube sometimes refuses a computer outright: a 429 on captions, a "sign
in to confirm you're not a bot" wall, a robot check on the watch page. The
community-highlighter web app routes around that with a Webshare residential
proxy; this module brings the same thing to the desktop, as a SWITCH the
person flips when (and only when) YouTube is refusing them.

Where the credentials come from, first match wins:

    1. environment — WEBSHARE_PROXY_USERNAME / WEBSHARE_PROXY_PASSWORD
       (WEBSHARE_PROXY_HOST, default p.webshare.io:80). A deployment's own
       config — always on, the switch doesn't apply.
    2. your own account — typed into Settings → fetch network, stored in
       app support (owner-only file mode).
    3. the built-in account — the one the app ships with (house_proxy.json,
       baked in at build time, never committed; see set_house()).

Whether fetches USE the proxy is the separate `enabled` switch, stored in
the same app-support file, OFF by default. One legacy rule: a proxy.json
that already holds your own credentials but predates the switch counts as
ON — whoever typed their account in had already chosen it.

Covenant note: the switch is visible on every page that fetches, the status
says whose account is carrying the traffic, and the password never leaves
this module (status() masks the username and omits the password).
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from .paths import support_dir

DEFAULT_HOST = "p.webshare.io:80"
_SESSION_SUFFIXES = ("-1", "-rotate", "-country-us")

# The built-in account ships beside this module, obfuscated so a casual
# grep of the app bundle doesn't read it out. Obfuscation, NOT secrecy:
# anything inside a distributed app can be extracted by someone determined
# — scope the account (a Webshare sub-user with a bandwidth cap) to match.
HOUSE_FILE = Path(__file__).with_name("house_proxy.json")
_MASK = b"civicmedia.studio/control-z/fetch"


def _file() -> "os.PathLike":
    return support_dir() / "proxy.json"


def _read_file() -> dict:
    try:
        return json.loads(_file().read_text())
    except (OSError, ValueError):
        return {}


def _write_file(d: dict):
    if not d:
        try:
            _file().unlink()
        except OSError:
            pass
        return
    _file().write_text(json.dumps(d))
    try:
        os.chmod(_file(), 0o600)  # credentials: owner-only
    except OSError:
        pass


# -- the built-in account ------------------------------------------------------

def _xor(b: bytes) -> bytes:
    return bytes(c ^ _MASK[i % len(_MASK)] for i, c in enumerate(b))


def _house() -> Optional[dict]:
    """{username, password, host} of the account the app ships with, or None."""
    try:
        blob = json.loads(HOUSE_FILE.read_text())
        d = json.loads(_xor(base64.b64decode(blob["d"])).decode("utf-8"))
        if d.get("username") and d.get("password"):
            return {"username": str(d["username"]),
                    "password": str(d["password"]),
                    "host": str(d.get("host") or DEFAULT_HOST)}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def house_available() -> bool:
    return _house() is not None


def set_house(username: str, password: str, host: str = "",
              path: Optional[Path] = None) -> Path:
    """Write the built-in account (the builder runs this once; the file is
    gitignored and the freeze bakes it in — packaging/suite.spec)."""
    d = {"username": username.strip(), "password": password.strip(),
         "host": (host or "").strip() or DEFAULT_HOST}
    if not (d["username"] and d["password"]):
        raise ValueError("the built-in account needs a username and password")
    raw = base64.b64encode(_xor(json.dumps(d).encode("utf-8"))).decode()
    p = Path(path or HOUSE_FILE)
    p.write_text(json.dumps({"v": 1, "d": raw}))
    return p


# -- configuration ---------------------------------------------------------------

def get_config() -> dict:
    """{username, password, host, source} — the credentials that WOULD carry
    traffic, whether or not the switch is on. source: env | file | house | None
    ("file" is your own account, kept under that name for compatibility)."""
    user = os.getenv("WEBSHARE_PROXY_USERNAME", "")
    pw = os.getenv("WEBSHARE_PROXY_PASSWORD", "")
    host = os.getenv("WEBSHARE_PROXY_HOST", "")
    if user and pw:
        return {"username": user, "password": pw,
                "host": host or DEFAULT_HOST, "source": "env"}
    d = _read_file()
    if d.get("username") and d.get("password"):
        return {"username": str(d["username"]),
                "password": str(d["password"]),
                "host": str(d.get("host") or DEFAULT_HOST),
                "source": "file"}
    h = _house()
    if h:
        return {**h, "source": "house"}
    return {"username": "", "password": "", "host": host or DEFAULT_HOST,
            "source": None}


def switch_on() -> bool:
    """The person's switch. Env config is always on; otherwise the stored
    flag, defaulting OFF — except a legacy file that already holds your own
    credentials, which counts as ON (you chose it by typing it in)."""
    if os.getenv("WEBSHARE_PROXY_USERNAME") and os.getenv("WEBSHARE_PROXY_PASSWORD"):
        return True
    d = _read_file()
    if "enabled" in d:
        return bool(d["enabled"])
    return bool(d.get("username") and d.get("password"))


def set_enabled(on: bool) -> dict:
    d = _read_file()
    d["enabled"] = bool(on)
    _write_file(d)
    return status()


def set_config(username: str, password: str, host: str = "") -> dict:
    """Write (or clear, with empty strings) YOUR OWN credentials. Saving an
    account turns the switch on — typing it in is the choice. Removing it
    turns the switch OFF: traffic never moves onto the built-in account
    without the person flipping the switch for it. The relay preference
    riding in the same file is preserved either way."""
    username, password = username.strip(), password.strip()
    d = _read_file()
    if not (username and password):
        had_own = bool(d.get("username"))
        d.pop("username", None)
        d.pop("password", None)
        d.pop("host", None)
        if had_own:
            d["enabled"] = False
    else:
        d.update({"username": username, "password": password,
                  "host": (host or "").strip() or DEFAULT_HOST,
                  "enabled": True})
    _write_file(d)
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
    _write_file(d)
    return status()


def build_url(username: str, password: str, host: str = DEFAULT_HOST) -> str:
    """Exactly the web app's construction: session suffix (-1, a sticky
    exit so a download's requests share one address) unless the username
    already carries one; credentials URL-encoded."""
    if not username.endswith(_SESSION_SUFFIXES):
        username = f"{username}-1"
    return (f"http://{quote(username, safe='')}:{quote(password, safe='')}"
            f"@{host or DEFAULT_HOST}/")


def config_url() -> Optional[str]:
    """The proxy URL the credentials would make, switch or no switch."""
    c = get_config()
    if not (c["username"] and c["password"]):
        return None
    return build_url(c["username"], c["password"], c["host"])


def proxy_url() -> Optional[str]:
    """The URL every fetch passes to yt-dlp / urllib — None when the switch
    is off or no credentials exist."""
    return config_url() if switch_on() else None


def status() -> dict:
    """What UIs may show. Password never leaves this module.

    enabled   — traffic rides a proxy right now (switch on AND credentials)
    switch    — the person's switch (env config reads as on)
    available — some credentials exist (env, own, or built-in)
    source    — whose account: env | file (your own) | house (built-in) | None
    """
    c = get_config()
    available = bool(c["username"] and c["password"])
    on = switch_on()
    masked = ""
    if available and c["source"] != "house":
        u = c["username"]
        masked = (u[:3] + "…" + u[-2:]) if len(u) > 6 else (u[:2] + "…")
    return {"enabled": bool(on and available), "switch": on,
            "available": available, "source": c["source"],
            "host": c["host"] if c["source"] != "house" else "built-in",
            "username_masked": masked if c["source"] != "house" else "",
            "own": bool(_read_file().get("username")),
            "house": house_available(), "relay": relay_enabled()}


def test(timeout: float = 20.0) -> dict:
    """One real request through the configured account (switch or no
    switch — this is how you check it BEFORE turning it on). Answers the
    exit address, or the failure as a sentence that names the fix."""
    import urllib.error
    import urllib.request

    url = config_url()
    if not url:
        return {"ok": False, "error": "no proxy account to test — add yours "
                                      "in Settings → fetch network"}
    op = urllib.request.build_opener(urllib.request.ProxyHandler(
        {"http": url, "https": url}))
    for probe in ("https://ipv4.webshare.io/", "https://api.ipify.org/"):
        try:
            ip = op.open(urllib.request.Request(
                probe, headers={"User-Agent": "control-z-suite"}),
                timeout=timeout).read().decode("utf-8", "replace").strip()
            return {"ok": True, "ip": ip[:64], "source": get_config()["source"]}
        except urllib.error.HTTPError as e:
            if e.code == 407:
                return {"ok": False, "error": "Webshare rejected the username "
                        "or password (HTTP 407) — copy both again from the "
                        "Webshare dashboard (Proxy → Proxy List)"}
            last = f"HTTP {e.code}"
        except OSError as e:
            reason = str(getattr(e, "reason", e))
            if "407" in reason:
                return {"ok": False, "error": "Webshare rejected the username "
                        "or password (407) — copy both again from the "
                        "Webshare dashboard"}
            last = reason[:160]
    return {"ok": False, "error": f"couldn't get through the proxy ({last}) — "
            "check the host (normally p.webshare.io:80) and that the Webshare "
            "plan is active"}


def main(argv=None):
    """python -m czcore.proxy set-house USER PASS [HOST] | clear-house | status | test"""
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "status"
    if cmd == "set-house" and len(args) >= 3:
        p = set_house(args[1], args[2], args[3] if len(args) > 3 else "")
        print(f"built-in account written → {p} (gitignored; the freeze bakes it in)")
    elif cmd == "clear-house":
        HOUSE_FILE.unlink(missing_ok=True)
        print("built-in account removed")
    elif cmd == "test":
        print(json.dumps(test(), indent=1))
    else:
        print(json.dumps(status(), indent=1))


if __name__ == "__main__":
    main()
