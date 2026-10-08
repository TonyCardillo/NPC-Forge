"""
Tests for the compact TERMy output in the style of Claude Code: a bullet
with the command, the description after a corner mark, and the rest
behind -v.
"""
import contextlib
import io
import logging
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

for path in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent / "src"):
    sys.path.insert(0, str(path))
from test_termy_dry_run import ROOT, termy  # noqa: E402

import logger as forge_logger  # noqa: E402
import registry  # noqa: E402
from tui.tools import TuiTools  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

def result(command="echo hi", status="exact match", confidence=1.0, response="Solved!", thinking="Ugh."):
    tools = [[{"arguments": {"command": command, "explanation": "Says hi."}}]] if command else []
    return {
        "status": status, "confidence": confidence, "permission": "yolo", "response": response,
        "thinking": thinking, "ignored_words": [], "tools": tools,
    }

def run_termy(argv, api_result):
    out, err = io.StringIO(), io.StringIO()
    run = mock.MagicMock(return_value=subprocess.CompletedProcess([], 0))
    handlers, level = list(forge_logger.logger.handlers), forge_logger.logger.level
    forge_logger.logger.setLevel(logging.INFO)  # other tests leave it at CRITICAL
    patches = [
        mock.patch.object(termy.on_demand.UnixSocketProvider, "request", return_value=api_result),
        mock.patch.object(termy.on_demand, "start_server", mock.MagicMock()),
        mock.patch.object(termy.subprocess, "run", run),
        mock.patch.object(termy.subprocess, "Popen", mock.MagicMock()),
        mock.patch.object(termy.tui, "confirm", mock.MagicMock(return_value=True)),
        mock.patch.object(sys, "argv", ["termy", *argv]),
        mock.patch.object(sys, "stdin", mock.MagicMock(isatty=lambda: True)),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ]
    try:
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            # A new termy process starts with a terminal handler; earlier tests may have removed it
            forge_logger.logger.handlers[:] = [h for h in handlers if isinstance(h, logging.FileHandler)]
            forge_logger.logger.addHandler(logging.StreamHandler(err))
            termy.run_cli()
    finally:
        forge_logger.logger.handlers[:] = handlers
        forge_logger.logger.setLevel(level)
    return ANSI.sub("", out.getvalue()), ANSI.sub("", err.getvalue())

class TestCompactOutput(unittest.TestCase):
    def test_command_shows_as_bullet_with_description_example(self):
        out, _ = run_termy(["say", "hi"], result())
        self.assertIn("⏺ echo hi\n  ⎿ Says hi.\n", out)
        self.assertNotIn("Description:", out)

    def test_personality_lines_only_with_verbose_example(self):
        out, _ = run_termy(["say", "hi"], result())
        self.assertNotIn("Ugh.", out)
        self.assertNotIn("Solved!", out)
        verbose, _ = run_termy(["-v", "say", "hi"], result())
        self.assertIn("Ugh.", verbose)
        self.assertIn("Solved!", verbose)

    def test_output_starts_without_blank_line_example(self):
        out, _ = run_termy(["say", "hi"], result())
        self.assertTrue(out.startswith("⏺"), repr(out[:20]))

    def test_fuzzy_match_shows_confidence_example(self):
        out, _ = run_termy(["say", "hi"], result(status="probabilistic match", confidence=0.86))
        self.assertIn("⏺ echo hi (86%)", out)
        exact, _ = run_termy(["say", "hi"], result())
        self.assertNotIn("%)", exact)

    def test_reply_without_command_shows_as_bullet_example(self):
        out, _ = run_termy(["how", "are", "you"], result(command="", response="Still here, sadly."))
        self.assertIn("⏺ Still here, sadly.", out)

    def test_multi_line_command_keeps_lines_under_the_bullet_example(self):
        out, _ = run_termy(["say", "hi"], result(command="echo a &&\necho b"))
        self.assertIn("⏺ echo a &&\n  echo b\n", out)

    def test_no_engine_logs_on_the_local_path_example(self):
        registry.REGISTRY_DIR = ROOT  # answer locally from the repo
        out, err = run_termy(["what", "time", "is", "it"], None)
        self.assertNotIn("[chatbot.py]", out + err)
        verbose_out, verbose_err = run_termy(["-v", "what", "time", "is", "it"], None)
        self.assertIn("[chatbot.py]", verbose_out + verbose_err)

class TestConfirmPrompt(unittest.TestCase):
    def test_confirm_asks_run_example(self):
        tui = TuiTools()
        err = io.StringIO()
        with mock.patch.object(tui, "keypress", return_value="y"), contextlib.redirect_stderr(err):
            self.assertTrue(tui.confirm())
        self.assertIn("Run?", ANSI.sub("", err.getvalue()))

if __name__ == "__main__":
    unittest.main()
