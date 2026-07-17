"""Bring-your-own-key AI — optional, honest, never the default.

Every reading the suite ships works locally and says what it is: the brief
is extractive, ask is retrieval. This module adds the one thing a local
read can't do — *generative* prose — for users who already have their own
Anthropic API key and want to spend it here. The covenant holds:

  - No key ships with the app and none is required; without one, every
    AI-shaped card keeps its local, labeled behavior.
  - The key is the USER'S, pasted into Settings (chmod 600 in app support)
    or present as ANTHROPIC_API_KEY in the environment — the same
    precedence as the Webshare proxy, env over file.
  - Only transcript text the user is already looking at is sent, only when
    the user clicks the button that says so. Nothing phones home.

stdlib urllib on purpose: one fewer dependency to audit, and the Messages
API is a single POST.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from .paths import support_dir

DEFAULT_MODEL = "claude-haiku-4-5"      # fast + cheap; meetings are long
DEFAULT_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


def _file():
    return support_dir() / "llm.json"


def get_config() -> dict:
    """{api_key, model, base_url, source} — env wins over the settings file.
    The env route needs the KEY present; a stray ANTHROPIC_BASE_URL alone
    (dev shells export those) never activates anything."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        return {"api_key": key,
                "model": os.getenv("CONTROL_Z_LLM_MODEL", DEFAULT_MODEL),
                "base_url": os.getenv("ANTHROPIC_BASE_URL", DEFAULT_BASE),
                "source": "env"}
    try:
        d = json.loads(_file().read_text())
        if d.get("api_key"):
            return {"api_key": str(d["api_key"]),
                    "model": str(d.get("model") or DEFAULT_MODEL),
                    "base_url": str(d.get("base_url") or DEFAULT_BASE),
                    "source": "file"}
    except (OSError, ValueError):
        pass
    return {"api_key": "", "model": DEFAULT_MODEL,
            "base_url": DEFAULT_BASE, "source": None}


def set_config(api_key: str, model: str = "") -> dict:
    """Write (or clear) the Settings-page key. 0600 like proxy.json —
    a credential file is nobody else's business."""
    f = _file()
    if not api_key:
        f.unlink(missing_ok=True)
        return status()
    f.write_text(json.dumps({"api_key": api_key,
                             "model": model or DEFAULT_MODEL}))
    f.chmod(0o600)
    return status()


def enabled() -> bool:
    return bool(get_config()["api_key"])


def status() -> dict:
    """What Settings and the tool pages may show — key masked to its tail,
    never returned whole."""
    c = get_config()
    key = c["api_key"]
    return {"enabled": bool(key), "source": c["source"], "model": c["model"],
            "key_masked": (f"…{key[-4:]}" if len(key) > 8 else "set")
            if key else None}


def complete(prompt: str, system: str = "", max_tokens: int = 1200,
             timeout: float = 90.0) -> str:
    """One Messages call with the user's key. Returns the text, or raises
    RuntimeError with a sentence — quota, auth and network each name
    themselves so the UI never shrugs."""
    c = get_config()
    if not c["api_key"]:
        raise RuntimeError("no API key configured — Settings → AI, or "
                           "ANTHROPIC_API_KEY in the environment")
    body = json.dumps({
        "model": c["model"], "max_tokens": max_tokens,
        **({"system": system} if system else {}),
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        c["base_url"].rstrip("/") + "/v1/messages", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "x-api-key": c["api_key"],
                 "anthropic-version": ANTHROPIC_VERSION,
                 "User-Agent": "control-z-suite"})
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read()
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8", "replace"))
            detail = (detail.get("error") or {}).get("message") or f"HTTP {e.code}"
        except Exception:
            detail = f"HTTP {e.code}"
        if e.code == 401:
            raise RuntimeError("the API key was refused (401) — check it in "
                               "Settings → AI") from e
        if e.code == 429:
            raise RuntimeError("rate limited by the API (429) — wait a "
                               "moment and retry") from e
        raise RuntimeError(f"the API said no — {detail[:300]}") from e
    except Exception as e:
        raise RuntimeError(f"couldn't reach the API ({e})") from e
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
    except ValueError as e:
        raise RuntimeError("the API answered with something that isn't "
                           "JSON") from e
    if not text.strip():
        raise RuntimeError("the API answered with no text")
    return text
