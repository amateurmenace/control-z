"""Studio · lend this desk — the drain's desk side (specs/17 §6.4).

A Settings surface and a dormant poller. When (and only when) a steward points
this desk at a Studio URL, sets a key, and switches lending on, the poller
claims caption-less meetings from the Studio's queue and transcribes them with
Scribe's engine on this desk's own hardware. Until then it says, honestly, that
it is waiting for the Studio to exist.

Gated: the Studio (specs/17) is not built yet, and its AsrTask contract is a
proposal (see czcore/drain.py and the handoff). Nothing here reaches the
network unless configured + enabled, and the poller sleeps first so a fresh
launch — and the test run — never trips it.
"""

from __future__ import annotations

import threading
import time

from czcore import drain

_POLL_INTERVAL = 300           # seconds between drain cycles when active
_STATE = {"last": None}        # last cycle's result, for the Settings line


def register_drain(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    @app.get("/api/drain/status")
    def api_status():
        return {**drain.status(), "last": _STATE["last"],
                "poll_interval": _POLL_INTERVAL}

    @app.post("/api/drain/config")
    def api_config(body: dict = Body(...)):
        # entering credentials is the operator's own action — we only store
        # what they typed here; nothing is entered on their behalf
        st = drain.set_config(
            studio_url=str(body.get("studio_url", "")),
            key=str(body.get("key", "")),
            desk_id=str(body.get("desk_id", "")),
            enabled=body.get("enabled"))
        return st

    @app.post("/api/drain/run-once")
    def api_run_once():
        """Run one drain cycle now (poll → claim → transcribe → post). Honest
        when there is nothing to talk to: no Studio configured is a sentence,
        not a stack trace."""
        if not drain.configured():
            return JSONResponse(
                {"error": drain.status()["sentence"]}, status_code=409)
        client = drain.client_from_config()

        def work(job):
            job.message = "asking the Studio for a caption-less meeting…"
            res = drain.run_once(client, drain.desk_transcribe)
            _STATE["last"] = {**res, "at": _now()}
            job.message = res.get("note", res.get("did", "done"))
            return res

        return jobs.start("drain", work, tool="suite",
                          label="the drain — one cycle").to_dict()

    def _poller():
        """Dormant until a steward switches lending on. Sleeps first, then runs
        a cycle each interval while active; the clock must never die."""
        while True:
            time.sleep(_POLL_INTERVAL)
            try:
                if not drain.active():
                    continue
                client = drain.client_from_config()
                if client is None:
                    continue
                res = drain.run_once(client, drain.desk_transcribe)
                _STATE["last"] = {**res, "at": _now()}
            except Exception as e:
                _STATE["last"] = {"did": "error", "note": str(e)[:160],
                                  "at": _now()}

    threading.Thread(target=_poller, daemon=True, name="drain-poller").start()


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")
