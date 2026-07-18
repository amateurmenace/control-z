"""The drain — a desk that volunteers to transcribe the Studio's captionless
meetings on its own hardware (specs/17 §6.4).

Most civic YouTube has captions; a meeting *without* them parks in the Studio
as an ``AsrTask``. Any desk running the suite can lend its hardware: it polls
the Studio's queue, claims a task, transcribes locally with **Scribe's engine**
(never its own whisper — the covenant), and posts the transcript back over the
steward-scoped API. Marginal cost stays zero; no cloud GPU bill.

**Gated — build to the contract, wait for the wire.** The Studio (specs/17)
does not exist yet, and specs/17 §5's ``AsrTask`` row names the object without a
field schema. So the shapes below are a *proposed* contract: the smallest set
the poll→claim→transcribe→post flow needs. Every field and endpoint is an ask
for the Studio session (see indexer/HANDOFF-DESK.md). Nothing here reaches the
network until a steward configures a Studio URL and key and switches it on, and
the poller sleeps first so a fresh launch and the test run never trip it.

--- PROPOSED CONTRACT (flag every line for the Studio session) -------------
  GET  {base}/api/asr/next?desk={desk}      -> 200 AsrTask | 204 (queue empty)
  POST {base}/api/asr/{id}/claim  {desk}    -> 200 {ok:true} | 409 {ok:false}
  POST {base}/api/asr/{id}/transcript
        {desk, model, transcript}           -> 200 {ok:true}
  auth: header  X-Studio-Key: {key}   on every call
  AsrTask := {id, meeting_id, town, source_url, title?, duration_hint?}
      source_url is the media the desk fetches itself (czcore.ytdlp +
      Grabber's patterns) — the Studio hosts no video (§3), captions-first.
  transcript := Scribe's Transcript.to_json() (segments/language/duration/…)
----------------------------------------------------------------------------

Stdlib urllib on purpose (one fewer dependency, same posture as czcore.llm).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable, Optional

from .paths import support_dir


def _file():
    return support_dir() / "drain.json"


def get_config() -> dict:
    """{studio_url, desk_id, key, enabled}. Env overrides the file, same
    precedence as the LLM key; a key present only in the file is 0600."""
    env_url = os.getenv("CONTROL_Z_STUDIO_URL", "")
    env_key = os.getenv("CONTROL_Z_STUDIO_KEY", "")
    if env_url and env_key:
        return {"studio_url": env_url.rstrip("/"),
                "desk_id": os.getenv("CONTROL_Z_STUDIO_DESK", _default_desk()),
                "key": env_key, "enabled": True, "source": "env"}
    try:
        d = json.loads(_file().read_text())
        return {"studio_url": str(d.get("studio_url") or "").rstrip("/"),
                "desk_id": str(d.get("desk_id") or _default_desk()),
                "key": str(d.get("key") or ""),
                "enabled": bool(d.get("enabled")), "source": "file"}
    except (OSError, ValueError):
        return {"studio_url": "", "desk_id": _default_desk(), "key": "",
                "enabled": False, "source": None}


def _default_desk() -> str:
    """A stable, non-identifying handle for this desk — the machine's host name
    is enough for a steward to tell two volunteers apart, and no more."""
    import socket
    try:
        return socket.gethostname().split(".")[0][:40] or "desk"
    except Exception:
        return "desk"


def set_config(studio_url: str = "", key: str = "", desk_id: str = "",
               enabled: Optional[bool] = None) -> dict:
    """Write the drain config (0600 — the key is a credential). An empty
    studio_url clears the file entirely; lending is off by construction until
    a URL, a key, and the switch are all set."""
    f = _file()
    if not studio_url:
        f.unlink(missing_ok=True)
        return status()
    cur = get_config()
    out = {"studio_url": studio_url.rstrip("/"),
           "desk_id": desk_id or cur["desk_id"],
           "key": key or cur["key"],
           "enabled": cur["enabled"] if enabled is None else bool(enabled)}
    f.write_text(json.dumps(out))
    f.chmod(0o600)
    return status()


def configured() -> bool:
    c = get_config()
    return bool(c["studio_url"] and c["key"])


def active() -> bool:
    return configured() and get_config()["enabled"]


def status() -> dict:
    """What the Settings section shows — honest about the Studio not existing
    yet, and never leaking the key whole."""
    c = get_config()
    key = c["key"]
    if not c["studio_url"]:
        line = ("waiting for the Studio to exist — when it does, point this "
                "desk at its URL and it can transcribe the record's "
                "caption-less meetings on your own hardware")
    elif not key:
        line = "Studio URL set, but no steward key yet — lending stays off"
    elif not c["enabled"]:
        line = f"ready to lend to {c['studio_url']} — switch it on to begin"
    else:
        line = f"lending this desk to {c['studio_url']} · {c['desk_id']}"
    return {"configured": configured(), "enabled": c["enabled"],
            "studio_url": c["studio_url"], "desk_id": c["desk_id"],
            "source": c["source"],
            "key_masked": (f"…{key[-4:]}" if len(key) > 8 else "set")
            if key else None,
            "sentence": line}


class DrainClient:
    """The steward-scoped HTTP surface, wrapped so a fake server can stand in
    for the (not-yet-existing) Studio in tests. One key, one desk id, urllib."""

    def __init__(self, base_url: str, key: str, desk_id: str,
                 timeout: float = 30.0):
        self.base = base_url.rstrip("/")
        self.key = key
        self.desk = desk_id
        self.timeout = timeout

    def _req(self, method: str, path: str, body: Optional[dict] = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json",
                     "X-Studio-Key": self.key,
                     "User-Agent": "control-z-drain"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
                code = r.getcode()
        except urllib.error.HTTPError as e:
            return e.code, _safe_json(e.read())
        except Exception as e:  # network/DNS/refused — the Studio may be down
            raise RuntimeError(
                f"couldn't reach the Studio ({e.__class__.__name__})") from e
        return code, _safe_json(raw)

    def poll(self) -> Optional[dict]:
        """The next AsrTask, or None when the queue is empty (204)."""
        code, data = self._req("GET", f"/api/asr/next?desk={self.desk}")
        if code == 204 or not data:
            return None
        if code != 200:
            raise RuntimeError(f"the Studio declined the poll ({code})")
        return data

    def claim(self, task_id: str) -> bool:
        """Lease a task so two desks never transcribe the same meeting.
        200 → ours; 409 → someone else got it first (not an error)."""
        code, data = self._req("POST", f"/api/asr/{task_id}/claim",
                               {"desk": self.desk})
        if code == 200:
            return True
        if code == 409:
            return False
        raise RuntimeError(f"the Studio refused the claim ({code})")

    def post_transcript(self, task_id: str, transcript_json: str,
                        model: str = "") -> bool:
        code, data = self._req(
            "POST", f"/api/asr/{task_id}/transcript",
            {"desk": self.desk, "model": model,
             "transcript": json.loads(transcript_json)})
        if code == 200:
            return True
        raise RuntimeError(f"the Studio rejected the transcript ({code})")


def _safe_json(raw: bytes) -> Optional[dict]:
    try:
        return json.loads(raw.decode("utf-8", "replace")) if raw else None
    except ValueError:
        return None


def client_from_config() -> Optional[DrainClient]:
    c = get_config()
    if not (c["studio_url"] and c["key"]):
        return None
    return DrainClient(c["studio_url"], c["key"], c["desk_id"])


def run_once(client: DrainClient,
             transcribe: Callable[[dict], tuple],
             claim: bool = True) -> dict:
    """Poll → claim → transcribe → post, once. ``transcribe(task)`` returns
    ``(transcript_json, model)`` — the real one fetches source_url with
    czcore.ytdlp and runs Scribe's engine (see ``desk_transcribe``); tests pass
    a fake so no whisper and no network run. Returns a short result dict; never
    raises for the ordinary empty-queue or lost-claim cases."""
    task = client.poll()
    if not task:
        return {"did": "idle", "note": "the Studio's queue is empty"}
    tid = str(task.get("id") or "")
    if not tid:
        return {"did": "skip", "note": "a task arrived without an id"}
    if claim and not client.claim(tid):
        return {"did": "yielded", "task": tid,
                "note": "another desk claimed it first"}
    transcript_json, model = transcribe(task)
    client.post_transcript(tid, transcript_json, model=model)
    return {"did": "transcribed", "task": tid,
            "meeting": task.get("meeting_id"), "model": model,
            "note": f"transcribed {task.get('title') or tid} on this desk"}


def desk_transcribe(task: dict) -> tuple:
    """The real transcribe: fetch the task's source with czcore.ytdlp (Grabber's
    patterns, never reimplemented), pull 16 kHz mono audio through the vendored
    ffmpeg, and run Scribe's engine. Returns (transcript_json, model). Kept out
    of run_once so tests never touch the network or an ASR model."""
    import subprocess
    import tempfile
    from pathlib import Path

    from czcore import ytdlp
    from czcore.tools import ffmpeg_path
    from scribe.transcribe import transcribe as asr

    src = str(task.get("source_url") or "")
    if not src:
        raise RuntimeError("the AsrTask carried no source_url to fetch")
    model = "base"
    with tempfile.TemporaryDirectory(prefix="drain-") as td:
        got = ytdlp.download(src, Path(td))   # {"path", "paths", "sidecars"}
        media = got["path"]
        wav16 = str(Path(td) / "a.16k.wav")
        subprocess.run([ffmpeg_path(), "-y", "-v", "quiet", "-i", str(media),
                        "-ac", "1", "-ar", "16000", wav16], check=True)
        t = asr(wav16, model=model)
    t.source = src
    return t.to_json(), model
