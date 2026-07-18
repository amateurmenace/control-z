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
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from .paths import support_dir

DEFAULT_MODEL = "claude-haiku-4-5"      # fast + cheap; meetings are long
DEFAULT_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


def _file():
    return support_dir() / "llm.json"


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
OPENAI_BASE = "https://api.openai.com"

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"     # fast + cheap, 1M window
GEMINI_BASE = "https://generativelanguage.googleapis.com"


def _provider_for(key: str) -> str:
    """The key's own shape names its provider: ``sk-ant-…`` is Anthropic,
    ``AIza…`` is Google Gemini, and anything else OpenAI-shaped is OpenAI (the
    same key the community-highlighter web app runs on). BYO-key only — the
    Studio's server bill is a separate world; this is the desk user's key."""
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("AIza"):
        return "gemini"
    return "openai"


# per-provider defaults, so env/file/status all read the same table
_DEFAULT_MODEL = {"anthropic": DEFAULT_MODEL, "openai": DEFAULT_OPENAI_MODEL,
                  "gemini": DEFAULT_GEMINI_MODEL}
_DEFAULT_BASE = {"anthropic": DEFAULT_BASE, "openai": OPENAI_BASE,
                 "gemini": GEMINI_BASE}


def get_config() -> dict:
    """{api_key, model, base_url, provider, source} — env wins over the
    settings file. The env route needs the KEY present; a stray
    ANTHROPIC_BASE_URL alone (dev shells export those) never activates
    anything."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        return {"api_key": key, "provider": "anthropic",
                "model": os.getenv("CONTROL_Z_LLM_MODEL", DEFAULT_MODEL),
                "base_url": os.getenv("ANTHROPIC_BASE_URL", DEFAULT_BASE),
                "source": "env"}
    key = os.getenv("OPENAI_API_KEY", "")
    if key:
        return {"api_key": key, "provider": "openai",
                "model": os.getenv("CONTROL_Z_LLM_MODEL",
                                   DEFAULT_OPENAI_MODEL),
                "base_url": OPENAI_BASE, "source": "env"}
    key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    if key:
        return {"api_key": key, "provider": "gemini",
                "model": os.getenv("CONTROL_Z_LLM_MODEL",
                                   DEFAULT_GEMINI_MODEL),
                "base_url": GEMINI_BASE, "source": "env"}
    try:
        d = json.loads(_file().read_text())
        if d.get("api_key"):
            prov = str(d.get("provider") or _provider_for(str(d["api_key"])))
            return {"api_key": str(d["api_key"]), "provider": prov,
                    "model": str(d.get("model")
                                 or _DEFAULT_MODEL.get(prov, DEFAULT_MODEL)),
                    "base_url": str(d.get("base_url")
                                    or _DEFAULT_BASE.get(prov, DEFAULT_BASE)),
                    "source": "file"}
    except (OSError, ValueError):
        pass
    return {"api_key": "", "provider": None, "model": DEFAULT_MODEL,
            "base_url": DEFAULT_BASE, "source": None}


def set_config(api_key: str, model: str = "") -> dict:
    """Write (or clear) the Settings-page key. 0600 like proxy.json —
    a credential file is nobody else's business. The provider is read off
    the key's own shape (sk-ant-… vs the web app's OpenAI key)."""
    f = _file()
    if not api_key:
        f.unlink(missing_ok=True)
        return status()
    f.write_text(json.dumps({"api_key": api_key,
                             "provider": _provider_for(api_key),
                             "model": model or ""}))
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
            "provider": c.get("provider"),
            "key_masked": (f"…{key[-4:]}" if len(key) > 8 else "set")
            if key else None}


# ---------------------------------------------------------------------------
# the token ledger — every call on the user's key, counted and attributed.
# The suite's generative passes run inside JobManager jobs; the job runner
# stamps its tool name into a thread-local (set_tool) so Memory's deltas,
# Interpreter's chunks and Narrator's vision drafts attribute themselves
# without those tools changing a line. Settings → AI shows the audit.
# ---------------------------------------------------------------------------

# context windows, tokens — conservative, for the "how full was the window"
# line; an unknown model falls back to the smallest common window
CONTEXT_WINDOWS = {
    "gpt-4o-mini": 128_000, "gpt-4o": 128_000,
    "gpt-4.1-mini": 1_000_000, "gpt-4.1": 1_000_000,
    "claude-haiku-4-5": 200_000, "claude-sonnet-4-5": 200_000,
    "claude-sonnet-4-6": 1_000_000, "claude-sonnet-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "gemini-1.5-flash": 1_000_000, "gemini-1.5-pro": 2_000_000,
    "gemini-2.0-flash": 1_000_000, "gemini-2.5-flash": 1_000_000,
    "gemini-2.5-pro": 1_000_000,
}
_WINDOW_DEFAULT = 128_000

_LEDGER: list = []          # this serve's session, in memory — the audit
_LEDGER_LOCK = threading.Lock()
_tool_ctx = threading.local()


def set_tool(name: str) -> None:
    """The job runner names whose turn it is; "" clears it."""
    _tool_ctx.name = str(name or "")


def context_window(model: str) -> int:
    for k, v in CONTEXT_WINDOWS.items():
        if str(model).startswith(k):
            return v
    return _WINDOW_DEFAULT


def _record(model: str, provider: str, tin: int, tout: int,
            tool: str = "", kind: str = "text") -> dict:
    entry = {"ts": round(time.time(), 1),
             "tool": tool or getattr(_tool_ctx, "name", "") or "app",
             "model": model, "provider": provider, "kind": kind,
             "tokens_in": int(tin), "tokens_out": int(tout),
             "window_pct": round(int(tin) / context_window(model) * 100, 1)}
    with _LEDGER_LOCK:
        _LEDGER.append(entry)
    return entry


def _usage_from(data: dict, provider: str, prompt_len: int) -> tuple:
    """(tokens_in, tokens_out) from the response; a length/4 estimate only
    when the API didn't say (and then it's still labeled in the audit by
    being divisible-looking — the audit never invents precision)."""
    if provider == "gemini":
        u = data.get("usageMetadata") or {}
        tin, tout = u.get("promptTokenCount"), u.get("candidatesTokenCount")
    else:
        u = data.get("usage") or {}
        if provider == "openai":
            tin, tout = u.get("prompt_tokens"), u.get("completion_tokens")
        else:
            tin, tout = u.get("input_tokens"), u.get("output_tokens")
    if tin is None:
        tin = prompt_len // 4
    if tout is None:
        tout = 0
    return int(tin), int(tout)


def _gemini_text(data: dict) -> str:
    """The text out of a Gemini generateContent response — the first
    candidate's parts, joined. A response blocked or empty comes back ""
    and the caller raises the honest 'no text' sentence."""
    cands = data.get("candidates") or []
    if not cands:
        return ""
    parts = (cands[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts)


def last_usage() -> Optional[dict]:
    """The most recent call's entry — pages append it to their origin
    lines so a user watches the window fill in real time."""
    with _LEDGER_LOCK:
        return dict(_LEDGER[-1]) if _LEDGER else None


def usage_summary() -> dict:
    """The session audit: totals, per tool, per model, and the fullest
    single call — everything Settings needs to keep the spend in view."""
    with _LEDGER_LOCK:
        calls = [dict(e) for e in _LEDGER]
    by_tool: dict = {}
    by_model: dict = {}
    for e in calls:
        t = by_tool.setdefault(e["tool"], {"calls": 0, "in": 0, "out": 0})
        t["calls"] += 1; t["in"] += e["tokens_in"]; t["out"] += e["tokens_out"]
        m = by_model.setdefault(e["model"], {"calls": 0, "in": 0, "out": 0})
        m["calls"] += 1; m["in"] += e["tokens_in"]; m["out"] += e["tokens_out"]
    return {"calls": len(calls),
            "tokens_in": sum(e["tokens_in"] for e in calls),
            "tokens_out": sum(e["tokens_out"] for e in calls),
            "by_tool": by_tool, "by_model": by_model,
            "fullest_call_pct": max([e["window_pct"] for e in calls] or [0]),
            "recent": calls[-40:]}


def complete(prompt: str, system: str = "", max_tokens: int = 1200,
             timeout: float = 90.0, tool: str = "") -> str:
    """One Messages call with the user's key. Returns the text, or raises
    RuntimeError with a sentence — quota, auth and network each name
    themselves so the UI never shrugs."""
    c = get_config()
    if not c["api_key"]:
        raise RuntimeError("no API key configured — Settings → AI, or "
                           "ANTHROPIC_API_KEY / OPENAI_API_KEY in the "
                           "environment")
    if c.get("provider") == "openai":
        body = json.dumps({
            "model": c["model"],
            "max_completion_tokens": max_tokens,
            "messages": ([{"role": "system", "content": system}]
                         if system else [])
            + [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            c["base_url"].rstrip("/") + "/v1/chat/completions", data=body,
            method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {c['api_key']}",
                     "User-Agent": "control-z-suite"})
    elif c.get("provider") == "gemini":
        # Google Generative Language API. The key rides the x-goog-api-key
        # header, never the URL query string — a credential in a URL leaks
        # into logs, and the covenant keeps keys out of sight.
        payload = {"contents": [{"role": "user",
                                 "parts": [{"text": prompt}]}],
                   "generationConfig": {"maxOutputTokens": max_tokens}}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        req = urllib.request.Request(
            c["base_url"].rstrip("/")
            + f"/v1beta/models/{c['model']}:generateContent",
            data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json",
                     "x-goog-api-key": c["api_key"],
                     "User-Agent": "control-z-suite"})
    else:
        body = json.dumps({
            "model": c["model"], "max_tokens": max_tokens,
            **({"system": system} if system else {}),
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            c["base_url"].rstrip("/") + "/v1/messages", data=body,
            method="POST",
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
        if c.get("provider") == "openai":
            text = ((data.get("choices") or [{}])[0]
                    .get("message", {}).get("content") or "")
        elif c.get("provider") == "gemini":
            text = _gemini_text(data)
        else:
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text")
    except ValueError as e:
        raise RuntimeError("the API answered with something that isn't "
                           "JSON") from e
    if not text.strip():
        raise RuntimeError("the API answered with no text")
    tin, tout = _usage_from(data, c.get("provider") or "", len(prompt))
    _record(c["model"], c.get("provider") or "", tin, tout, tool=tool)
    return text


def complete_vision(prompt: str, jpeg_b64: str, system: str = "",
                    max_tokens: int = 300, timeout: float = 60.0,
                    tool: str = "") -> str:
    """One message with a picture in it — the multimodal door Narrator
    asked for (its request shape, moved in). Each provider takes base64
    JPEG (Anthropic source blocks, OpenAI data-URI, Gemini inline_data);
    counted in the same ledger as every text call."""
    c = get_config()
    if not c["api_key"]:
        raise RuntimeError("no API key configured — Settings → AI")
    if c.get("provider") == "openai":
        body = {"model": c["model"], "max_completion_tokens": max_tokens,
                "messages": ([{"role": "system", "content": system}]
                             if system else [])
                + [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{jpeg_b64}"}},
                    {"type": "text", "text": prompt}]}]}
        req = urllib.request.Request(
            c["base_url"].rstrip("/") + "/v1/chat/completions",
            data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {c['api_key']}",
                     "User-Agent": "control-z-suite"})
    elif c.get("provider") == "gemini":
        payload = {"contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": jpeg_b64}},
            {"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        req = urllib.request.Request(
            c["base_url"].rstrip("/")
            + f"/v1beta/models/{c['model']}:generateContent",
            data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json",
                     "x-goog-api-key": c["api_key"],
                     "User-Agent": "control-z-suite"})
    else:
        body = {"model": c["model"], "max_tokens": max_tokens,
                **({"system": system} if system else {}),
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": jpeg_b64}},
                    {"type": "text", "text": prompt}]}]}
        req = urllib.request.Request(
            c["base_url"].rstrip("/") + "/v1/messages",
            data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json",
                     "x-api-key": c["api_key"],
                     "anthropic-version": ANTHROPIC_VERSION,
                     "User-Agent": "control-z-suite"})
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read()
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception as e:
        raise RuntimeError(
            f"the vision call didn't answer ({e.__class__.__name__})") from e
    if c.get("provider") == "openai":
        text = ((data.get("choices") or [{}])[0]
                .get("message", {}).get("content") or "")
    elif c.get("provider") == "gemini":
        text = _gemini_text(data)
    else:
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
    if not str(text).strip():
        raise RuntimeError("the model answered with no text")
    tin, tout = _usage_from(data, c.get("provider") or "", len(prompt) + 1500)
    _record(c["model"], c.get("provider") or "", tin, tout,
            tool=tool, kind="vision")
    return str(text)
