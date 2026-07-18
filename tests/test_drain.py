"""The drain's desk side (specs/17 §6.4) — built to a proposed AsrTask
contract, wired against a fake Studio so no real Studio, network, or ASR runs.

The Studio does not exist yet; these tests pin the DESK behaviour so that when
the wire lands, poll → claim → transcribe → post already works and the honest
"waiting for the Studio" surface is proven.
"""

import http.server
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from czcore import drain


class FakeStudio:
    """A minimal server speaking the proposed contract: hand out one task,
    honor a claim once, accept the transcript — and check the steward key on
    every call."""

    def __init__(self, tasks, key="studio-secret"):
        self.tasks = list(tasks)
        self.key = key
        self.claimed = set()
        self.posted = {}
        self.calls = []
        srv = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=None):
                self.send_response(code)
                if body is not None:
                    out = json.dumps(body).encode()
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(out)))
                    self.end_headers()
                    self.wfile.write(out)
                else:
                    self.send_header("Content-Length", "0")
                    self.end_headers()

            def _auth_ok(self):
                return self.headers.get("X-Studio-Key") == srv.key

            def do_GET(self):
                srv.calls.append(("GET", self.path,
                                  self.headers.get("X-Studio-Key")))
                if not self._auth_ok():
                    return self._send(401, {"error": "bad key"})
                if self.path.startswith("/api/asr/next"):
                    if srv.tasks:
                        return self._send(200, srv.tasks[0])
                    return self._send(204, None)
                self._send(404, {"error": "no"})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n) or b"{}")
                srv.calls.append(("POST", self.path,
                                  self.headers.get("X-Studio-Key")))
                if not self._auth_ok():
                    return self._send(401, {"error": "bad key"})
                parts = self.path.strip("/").split("/")  # api asr <id> <verb>
                tid = parts[2] if len(parts) > 2 else ""
                verb = parts[3] if len(parts) > 3 else ""
                if verb == "claim":
                    if tid in srv.claimed:
                        return self._send(409, {"ok": False})
                    srv.claimed.add(tid)
                    return self._send(200, {"ok": True})
                if verb == "transcript":
                    srv.posted[tid] = body
                    srv.tasks = [t for t in srv.tasks if t.get("id") != tid]
                    return self._send(200, {"ok": True})
                self._send(404, {"error": "no"})

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def stop(self):
        self.httpd.shutdown()


TASK = {"id": "t1", "meeting_id": "m1", "town": "Brookline",
        "source_url": "https://youtube.com/watch?v=abc", "title": "Select Board"}


def fake_transcribe(task):
    """Stand in for Scribe's engine: no fetch, no whisper — just a transcript
    shaped like the real one, so the post path is exercised end to end."""
    tj = json.dumps({"source": task["source_url"], "language": "en",
                     "duration": 12.0, "model": "base",
                     "segments": [{"start": 0.0, "end": 12.0,
                                   "text": "the meeting came to order"}]})
    return tj, "base"


class TestDrainConfig(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-drain-")
        p = mock.patch.object(drain, "support_dir",
                              lambda sub="": Path(self.td.name))
        p.start(); self.addCleanup(p.stop)
        self.addCleanup(self.td.cleanup)
        saved = {k: os.environ.pop(k, None) for k in (
            "CONTROL_Z_STUDIO_URL", "CONTROL_Z_STUDIO_KEY",
            "CONTROL_Z_STUDIO_DESK")}
        self.addCleanup(lambda: [os.environ.update({k: v})
                                 for k, v in saved.items() if v is not None])

    def test_unconfigured_waits_for_the_studio(self):
        st = drain.status()
        self.assertFalse(st["configured"])
        self.assertFalse(st["enabled"])
        self.assertIn("waiting for the Studio", st["sentence"])
        self.assertIsNone(st["key_masked"])

    def test_config_roundtrip_masks_the_key_and_gates_on_enable(self):
        st = drain.set_config(studio_url="https://studio.example",
                              key="studio-secret-1234")
        self.assertTrue(st["configured"])
        self.assertFalse(st["enabled"])          # off until switched on
        self.assertFalse(drain.active())
        self.assertEqual(st["key_masked"], "…1234")
        self.assertNotIn("studio-secret", str(st))
        mode = (Path(self.td.name) / "drain.json").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)
        drain.set_config(studio_url="https://studio.example", enabled=True)
        self.assertTrue(drain.active())

    def test_clearing_removes_the_file(self):
        drain.set_config(studio_url="https://s", key="k-abcdefgh")
        drain.set_config(studio_url="")
        self.assertFalse((Path(self.td.name) / "drain.json").exists())
        self.assertFalse(drain.configured())


class TestDrainCycle(unittest.TestCase):
    def setUp(self):
        self.studio = FakeStudio([dict(TASK)])
        self.addCleanup(self.studio.stop)
        self.client = drain.DrainClient(self.studio.url, "studio-secret", "desk-x")

    def test_poll_claim_transcribe_post_end_to_end(self):
        res = drain.run_once(self.client, fake_transcribe)
        self.assertEqual(res["did"], "transcribed")
        self.assertEqual(res["task"], "t1")
        # the transcript reached the Studio, shaped as Scribe writes it
        self.assertIn("t1", self.studio.posted)
        posted = self.studio.posted["t1"]
        self.assertEqual(posted["desk"], "desk-x")
        self.assertEqual(posted["transcript"]["segments"][0]["text"],
                         "the meeting came to order")
        # every call carried the steward key
        self.assertTrue(all(c[2] == "studio-secret" for c in self.studio.calls))

    def test_empty_queue_is_idle_not_an_error(self):
        empty = drain.DrainClient(FakeStudio([]).url, "studio-secret", "d")
        self.assertEqual(drain.run_once(empty, fake_transcribe)["did"], "idle")

    def test_a_lost_claim_yields_without_transcribing(self):
        self.studio.claimed.add("t1")            # another desk got it first
        called = []
        res = drain.run_once(
            self.client, lambda t: called.append(t) or fake_transcribe(t))
        self.assertEqual(res["did"], "yielded")
        self.assertEqual(called, [])             # never spent the ASR
        self.assertNotIn("t1", self.studio.posted)

    def test_a_bad_key_is_a_sentence(self):
        wrong = drain.DrainClient(self.studio.url, "not-the-key", "d")
        with self.assertRaises(RuntimeError):
            drain.run_once(wrong, fake_transcribe)


if __name__ == "__main__":
    unittest.main()
