"""
Tests for the LLM fallback: TERMy asks LM Studio when it has no match or
an uncertain one, asks before it runs the answer, and saves an answer
that ran as a learned entry.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

for path in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent / "src"):
    sys.path.insert(0, str(path))
from test_termy_dry_run import termy  # noqa: E402

import learned  # noqa: E402
from providers import lmstudio  # noqa: E402


def match(status, confidence, ignored=(), command="echo termy"):
    return {
        "status": status,
        "confidence": confidence,
        "permission": "yolo",
        "ignored_words": list(ignored),
        "tools": [[{"arguments": {"command": command, "explanation": "From TERMy"}}]],
    }

REJECTED = {"status": "rejected", "confidence": 0.0, "permission": "yolo", "related": []}
SUGGESTION = {"command": "echo from-llm", "explanation": "Prints a word."}

class FakeProvider:
    def __init__(self, ready=True, suggestion=SUGGESTION):
        self.ready, self.suggestion, self.asked = ready, suggestion, []
        self.model = "fake-model"

    def ensure_ready(self):
        return self.ready

    def suggest(self, query):
        self.asked.append(query)
        return self.suggestion

class TestIsUncertain(unittest.TestCase):
    def test_certain_statuses_example(self):
        for status in ("exact match", "template match", "context match"):
            self.assertFalse(termy.is_uncertain(match(status, 1.0), 0.8), status)

    def test_uncertain_cases_example(self):
        self.assertTrue(termy.is_uncertain(REJECTED, 0.8))
        self.assertTrue(termy.is_uncertain(match("probabilistic match", 0.79), 0.8))
        self.assertTrue(termy.is_uncertain(match("probabilistic match", 0.95, ["empty"]), 0.8))
        self.assertFalse(termy.is_uncertain(match("probabilistic match", 0.85), 0.8))

    def test_lower_confidence_is_never_more_certain_invariant(self):
        steps = [i / 100 for i in range(60, 101)]
        flags = [termy.is_uncertain(match("probabilistic match", c), 0.8) for c in steps]
        self.assertEqual(flags, sorted(flags, reverse=True))

class TestFallbackFlow(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.learned = self.home / ".local" / "share" / "termy" / "dataset_learned.json"

    def run_termy(self, argv, result, provider, confirm=True, returncode=0):
        run = mock.MagicMock(return_value=subprocess.CompletedProcess([], returncode))
        stop = mock.MagicMock()
        out = io.StringIO()
        patches = [
            mock.patch.dict(os.environ, {"HOME": str(self.home)}),
            mock.patch.object(termy.on_demand.UnixSocketProvider, "request", return_value=result),
            mock.patch.object(termy.on_demand, "start_server", mock.MagicMock()),
            mock.patch.object(termy.on_demand, "stop_server", stop),
            mock.patch.object(termy, "LmStudioProvider", return_value=provider),
            mock.patch.object(termy.subprocess, "run", run),
            mock.patch.object(termy.subprocess, "Popen", mock.MagicMock()),
            mock.patch.object(termy.tui, "confirm", mock.MagicMock(return_value=confirm)),
            mock.patch.object(termy.tui, "multi_choice", mock.MagicMock(return_value=0)),
            mock.patch.object(sys, "argv", ["termy", *argv]),
            mock.patch.object(sys, "stdin", mock.MagicMock(isatty=lambda: True)),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ]
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            os.environ.pop("TERMY_YES", None)
            code = termy.run_cli()
        return code, run, stop, out.getvalue()

    def ran(self, run):
        return [c.args[0] for c in run.call_args_list if c.args and isinstance(c.args[0], str)]

    def saved(self):
        return json.loads(self.learned.read_text()) if self.learned.exists() else []

    def test_no_match_asks_the_llm_runs_and_saves_example(self):
        provider = FakeProvider()
        code, run, stop, out = self.run_termy(["make", "a", "wifi", "qr", "code"], REJECTED, provider)
        self.assertEqual(code, 0)
        self.assertEqual(provider.asked, ["make a wifi qr code"])
        self.assertTrue(any("echo from-llm" in c for c in self.ran(run)))
        self.assertEqual(self.saved()[0]["input"], ["make a wifi qr code"])
        self.assertEqual(self.saved()[0]["permission"], "ask")
        stop.assert_called_once()

    def test_uncertain_match_asks_the_llm_example(self):
        provider = FakeProvider()
        result = match("probabilistic match", 0.72, command="pwd")
        _, run, _, out = self.run_termy(["search", "for", "todo", "here"], result, provider)
        self.assertEqual(provider.asked, ["search for todo here"])
        self.assertFalse(any(c.endswith("pwd") for c in self.ran(run)))
        self.assertIn("not sure", out)

    def test_declined_answer_is_not_run_or_saved_example(self):
        _, run, stop, _ = self.run_termy(["blorp"], REJECTED, FakeProvider(), confirm=False)
        self.assertEqual(self.ran(run), [])
        self.assertEqual(self.saved(), [])
        stop.assert_not_called()

    def test_failed_answer_is_not_saved_example(self):
        self.run_termy(["blorp"], REJECTED, FakeProvider(), returncode=1)
        self.assertEqual(self.saved(), [])

    def test_certain_match_never_asks_the_llm_example(self):
        provider = FakeProvider()
        _, run, _, _ = self.run_termy(["what", "time"], match("exact match", 1.0), provider)
        self.assertEqual(provider.asked, [])
        self.assertTrue(any("echo termy" in c for c in self.ran(run)))

    def test_llm_not_available_keeps_the_old_menu_example(self):
        provider = FakeProvider(ready=False)
        code, run, _, out = self.run_termy(["blorp"], REJECTED, provider)
        self.assertEqual(provider.asked, [])
        self.assertEqual(self.ran(run), [])
        self.assertIn("LM Studio", out)

    def test_dry_run_says_it_would_ask_the_llm_example(self):
        provider = FakeProvider()
        _, run, _, out = self.run_termy(["-n", "blorp"], REJECTED, provider)
        self.assertEqual(provider.asked, [])
        self.assertEqual(self.ran(run), [])
        self.assertIn("would ask", out)

class TestLearnedEntries(unittest.TestCase):
    def test_same_prompt_replaces_the_old_entry_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "learned.json"
            learned.save_entry(path, "Make a QR code", "echo one", "First.")
            learned.save_entry(path, "make a qr code", "echo two", "Second.")
            entries = json.loads(path.read_text())
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["tools"][0]["arguments"]["command"], "echo two")

class TestLmStudioProvider(unittest.TestCase):
    def test_parse_takes_the_bash_fence_and_drops_thinking_example(self):
        text = "<think>hmm</think>Shows the IP.\n```bash\nipconfig getifaddr en0\n```\nDone."
        self.assertEqual(
            lmstudio.parse_suggestion(text),
            {"command": "ipconfig getifaddr en0", "explanation": "Shows the IP. Done."},
        )

    def test_parse_without_code_returns_none_example(self):
        self.assertIsNone(lmstudio.parse_suggestion("I cannot help with that."))

    def make(self, server_up, loaded):
        calls = []

        def run(args, **_):
            calls.append(args[1:])
            out = "qwen/qwen3.5-9b" if loaded and args[1] == "ps" else ""
            return subprocess.CompletedProcess(args, 0, stdout=out, stderr="")

        provider = lmstudio.LmStudioProvider(
            {"model": "qwen/qwen3.5-9b", "ttl_seconds": 600}, run=run, lms="/x/lms"
        )
        provider.server_up = lambda: server_up
        return provider, calls

    def test_starts_server_and_loads_model_with_ttl_example(self):
        provider, calls = self.make(server_up=False, loaded=False)
        self.assertTrue(provider.ensure_ready())
        self.assertIn(["server", "start"], calls)
        self.assertIn(["load", "qwen/qwen3.5-9b", "--ttl", "600", "-y"], calls)

    def test_running_server_and_loaded_model_need_nothing_example(self):
        provider, calls = self.make(server_up=True, loaded=True)
        self.assertTrue(provider.ensure_ready())
        self.assertEqual(calls, [["ps"]])

    def test_request_turns_thinking_off_example(self):
        sent = {}
        class Response(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
        def urlopen(req, timeout):
            sent["url"], sent["body"] = req.full_url, json.loads(req.data)
            out = {"output": [{"type": "reasoning", "content": "hmm"}, {"type": "message", "content": "Hi."}]}
            return Response(json.dumps(out).encode())
        provider = lmstudio.LmStudioProvider({"model": "m"}, lms="/x/lms")
        with mock.patch.object(lmstudio.urllib.request, "urlopen", urlopen):
            self.assertEqual(provider.request("ask"), "Hi.")
        self.assertTrue(sent["url"].endswith("/api/v1/chat"))
        self.assertEqual(sent["body"]["reasoning"], "off")
        self.assertEqual(sent["body"]["input"], "ask")

    def test_without_lms_it_is_not_ready_example(self):
        provider = lmstudio.LmStudioProvider({}, lms=None)
        provider.lms = None
        self.assertFalse(provider.ensure_ready())

if __name__ == "__main__":
    unittest.main()
