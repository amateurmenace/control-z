"""The BYO-key AI module and the names-for-Whisper harvest.

llm.py never touches the network here — these are config-precedence,
masking and covenant tests (no key ⇒ disabled, key never returned whole).
hotwords() is pure reading: the meeting's own words in, a decoder bias out.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from czcore import llm
from czcore.captions import parse_video_details
from highlighter.insight import hotwords


class TestLLMConfig(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-llm-test-")
        patch_dir = mock.patch.object(
            llm, "support_dir", lambda sub="": Path(self.td.name))
        patch_dir.start()
        self.addCleanup(patch_dir.stop)
        self.addCleanup(self.td.cleanup)
        saved = {k: os.environ.pop(k, None)
                 for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL",
                           "OPENAI_API_KEY", "GEMINI_API_KEY",
                           "GOOGLE_API_KEY", "CONTROL_Z_LLM_MODEL")}
        self.addCleanup(lambda: [os.environ.update({k: v})
                                 for k, v in saved.items() if v is not None])

    def test_disabled_by_default(self):
        self.assertFalse(llm.enabled())
        st = llm.status()
        self.assertFalse(st["enabled"])
        self.assertIsNone(st["key_masked"])

    def test_stray_base_url_alone_never_activates(self):
        # dev shells export ANTHROPIC_BASE_URL; without a key it means nothing
        os.environ["ANTHROPIC_BASE_URL"] = "http://localhost:9999"
        self.assertFalse(llm.enabled())

    def test_env_key_wins_over_file(self):
        llm.set_config("sk-file-key-123456", "claude-sonnet-5")
        os.environ["ANTHROPIC_API_KEY"] = "sk-env-key-654321"
        c = llm.get_config()
        self.assertEqual(c["source"], "env")
        self.assertEqual(c["api_key"], "sk-env-key-654321")

    def test_file_roundtrip_and_masking(self):
        st = llm.set_config("sk-ant-abcdef-7890", "")
        self.assertTrue(st["enabled"])
        self.assertEqual(st["model"], llm.DEFAULT_MODEL)
        self.assertEqual(st["key_masked"], "…7890")
        self.assertNotIn("sk-ant", str(st))  # the key never leaves whole
        mode = (Path(self.td.name) / "llm.json").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_clear_removes_file(self):
        llm.set_config("sk-something-longer", "")
        st = llm.set_config("", "")
        self.assertFalse(st["enabled"])
        self.assertFalse((Path(self.td.name) / "llm.json").exists())

    def test_complete_without_key_is_a_sentence(self):
        with self.assertRaises(RuntimeError) as cm:
            llm.complete("hello")
        self.assertIn("Settings", str(cm.exception))

    def test_key_shape_names_its_provider(self):
        self.assertEqual(llm._provider_for("sk-ant-abc"), "anthropic")
        self.assertEqual(llm._provider_for("AIzaSyD-xyz"), "gemini")
        self.assertEqual(llm._provider_for("sk-proj-openaiish"), "openai")

    def test_gemini_file_config_takes_gemini_defaults(self):
        st = llm.set_config("AIza-abcd-1234", "")
        self.assertTrue(st["enabled"])
        self.assertEqual(st["provider"], "gemini")
        self.assertEqual(st["model"], llm.DEFAULT_GEMINI_MODEL)
        self.assertEqual(st["key_masked"], "…1234")
        self.assertEqual(llm.get_config()["base_url"], llm.GEMINI_BASE)
        self.assertNotIn("AIza", str(st))  # the key never leaves whole

    def test_gemini_env_activates_from_either_name(self):
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("GOOGLE_API_KEY", None)
            os.environ[name] = "AIza-env-key"
            c = llm.get_config()
            self.assertEqual((c["source"], c["provider"]), ("env", "gemini"))
            self.assertEqual(c["model"], llm.DEFAULT_GEMINI_MODEL)
            os.environ.pop(name, None)


class TestVideoDetails(unittest.TestCase):
    HTML = ('junk"videoDetails":{"videoId":"abc12345678","title":"Select '
            'Board 7/15","lengthSeconds":"7260","author":"BIG"},'
            '"annotations":[]more')

    def test_parses_the_watch_page_fields(self):
        d = parse_video_details(self.HTML)
        self.assertEqual(d["title"], "Select Board 7/15")
        self.assertEqual(d["duration"], 7260)
        self.assertEqual(d["uploader"], "BIG")
        self.assertEqual(d["id"], "abc12345678")

    def test_page_shape_change_is_empty_not_a_crash(self):
        self.assertEqual(parse_video_details("<html>nothing here</html>"), {})
        self.assertEqual(parse_video_details(
            '"videoDetails": {broken json},"playerConfig"'), {})


class TestHotwords(unittest.TestCase):
    SEGS = [
        {"text": "Councilor Vitolo moved to approve. Heather Hamilton "
                 "seconded the motion.", "start": 5.0},
        {"text": "The Harvard Street crosswalk, Bernard Greene said.",
         "start": 9.0},
        {"text": "Bernard Greene asked about Harvard Street again.",
         "start": 12.0},
    ]

    def test_people_and_places_harvested(self):
        s = hotwords(self.SEGS)
        self.assertIn("Bernard Greene", s)
        self.assertIn("Harvard Street", s)

    def test_title_names_ride_along(self):
        s = hotwords(self.SEGS, {"title": "Brookline Select Board — July"})
        self.assertIn("Brookline Select Board", s)

    def test_deduped_case_insensitive(self):
        s = hotwords(self.SEGS + [{"text": "BERNARD GREENE spoke.",
                                   "start": 20.0}])
        self.assertEqual(s.lower().count("bernard greene"), 1)

    def test_cap_cuts_on_a_comma(self):
        segs = [{"text": f"Member Name{i} Surname{i} was recognized by "
                         f"Member Name{i} Surname{i}.", "start": float(i)}
                for i in range(120)]
        s = hotwords(segs, cap=200)
        self.assertLessEqual(len(s), 200)
        self.assertFalse(s.endswith(","))

    def test_empty_meeting_is_empty_string(self):
        self.assertEqual(hotwords([]), "")


if __name__ == "__main__":
    unittest.main()


class TestTokenLedger(unittest.TestCase):
    """The AI audit: every call counted, attributed, never invented."""

    def setUp(self):
        with llm._LEDGER_LOCK:
            self._saved = llm._LEDGER[:]
            llm._LEDGER.clear()
        llm.set_tool("")

    def tearDown(self):
        with llm._LEDGER_LOCK:
            llm._LEDGER[:] = self._saved
        llm.set_tool("")

    def test_jobs_name_the_spender(self):
        """The job runner stamps its tool; a direct call may still say
        its own name, and the explicit name wins."""
        llm.set_tool("interpreter")
        self.assertEqual(llm._record("gpt-4o-mini", "openai", 10, 1)["tool"],
                         "interpreter")
        self.assertEqual(
            llm._record("gpt-4o-mini", "openai", 10, 1, tool="kb")["tool"],
            "kb")
        llm.set_tool("")
        self.assertEqual(llm._record("gpt-4o-mini", "openai", 10, 1)["tool"],
                         "app")

    def test_usage_reads_both_providers_and_never_invents_output(self):
        self.assertEqual(
            llm._usage_from({"usage": {"prompt_tokens": 5,
                                       "completion_tokens": 7}},
                            "openai", 999), (5, 7))
        self.assertEqual(
            llm._usage_from({"usage": {"input_tokens": 9,
                                       "output_tokens": 4}},
                            "anthropic", 999), (9, 4))
        self.assertEqual(
            llm._usage_from({"usageMetadata": {"promptTokenCount": 8,
                                               "candidatesTokenCount": 2}},
                            "gemini", 999), (8, 2))
        # no usage block: input estimated from length, output stays zero
        self.assertEqual(llm._usage_from({}, "openai", 400), (100, 0))
        self.assertEqual(llm._usage_from({}, "gemini", 400), (100, 0))

    def test_summary_totals_and_fullest_call(self):
        llm._record("gpt-4o-mini", "openai", 12000, 300, tool="highlighter")
        llm._record("gpt-4o-mini", "openai", 64000, 900, tool="memory")
        s = llm.usage_summary()
        self.assertEqual(s["calls"], 2)
        self.assertEqual(s["tokens_in"], 76000)
        self.assertEqual(s["by_tool"]["memory"]["out"], 900)
        self.assertEqual(s["fullest_call_pct"], 50.0)

    def test_windows_match_by_prefix_and_fall_back_small(self):
        self.assertEqual(llm.context_window("claude-haiku-4-5-20251001"),
                         200_000)
        self.assertEqual(llm.context_window("gpt-4o-mini-2024-07-18"),
                         128_000)
        self.assertEqual(llm.context_window("gemini-2.0-flash-exp"),
                         1_000_000)
        self.assertEqual(llm.context_window("some-local-model"), 128_000)


class TestGeminiRoundTrip(unittest.TestCase):
    """A real request/response against a local fake server: the desk's third
    key shape sends what Gemini expects (contents + systemInstruction, the key
    in the x-goog-api-key header not the URL), parses the candidate text, and
    lands the usage in the same audit ledger as every other call."""

    def setUp(self):
        import http.server
        import json as _json
        import threading

        self.td = tempfile.TemporaryDirectory(prefix="cz-gem-")
        pd = mock.patch.object(llm, "support_dir",
                               lambda sub="": Path(self.td.name))
        pd.start(); self.addCleanup(pd.stop)
        self.addCleanup(self.td.cleanup)
        saved = {k: os.environ.pop(k, None) for k in (
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
            "GOOGLE_API_KEY", "CONTROL_Z_LLM_MODEL")}
        self.addCleanup(lambda: [os.environ.update({k: v})
                                 for k, v in saved.items() if v is not None])

        self.reqs = []
        reqs = self.reqs

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = _json.loads(self.rfile.read(n) or b"{}")
                reqs.append({"path": self.path,
                             "key": self.headers.get("x-goog-api-key"),
                             "body": body})
                out = _json.dumps({
                    "candidates": [{"content": {"parts": [{"text": "pong"}]}}],
                    "usageMetadata": {"promptTokenCount": 3,
                                      "candidatesTokenCount": 1}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown)
        (Path(self.td.name) / "llm.json").write_text(_json.dumps({
            "api_key": "AIza-test-key", "provider": "gemini",
            "model": "gemini-2.0-flash",
            "base_url": f"http://127.0.0.1:{self.srv.server_address[1]}"}))
        with llm._LEDGER_LOCK:
            self._saved = llm._LEDGER[:]
            llm._LEDGER.clear()

        def _restore():
            with llm._LEDGER_LOCK:
                llm._LEDGER[:] = self._saved
        self.addCleanup(_restore)

    def test_chat_round_trip_shape_and_ledger(self):
        out = llm.complete("hello there", system="be brief", tool="test")
        self.assertEqual(out, "pong")
        r = self.reqs[-1]
        self.assertEqual(
            r["path"], "/v1beta/models/gemini-2.0-flash:generateContent")
        self.assertEqual(r["key"], "AIza-test-key")   # header, not URL query
        self.assertEqual(
            r["body"]["contents"][0]["parts"][0]["text"], "hello there")
        self.assertEqual(
            r["body"]["systemInstruction"]["parts"][0]["text"], "be brief")
        u = llm.last_usage()
        self.assertEqual((u["tokens_in"], u["tokens_out"], u["provider"]),
                         (3, 1, "gemini"))

    def test_vision_sends_inline_data_and_counts_as_vision(self):
        out = llm.complete_vision("what is this", "QUJD")   # base64 'ABC'
        self.assertEqual(out, "pong")
        parts = self.reqs[-1]["body"]["contents"][0]["parts"]
        self.assertEqual(parts[0]["inline_data"]["data"], "QUJD")
        self.assertEqual(parts[0]["inline_data"]["mime_type"], "image/jpeg")
        self.assertEqual(llm.last_usage()["kind"], "vision")
