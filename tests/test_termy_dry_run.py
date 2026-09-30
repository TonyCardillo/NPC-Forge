"""
Tests for the TERMy --dry-run flag: it shows the matched command and
never runs anything.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
TERMY_DIR = ROOT / "npcs" / "termy"
for path in (str(ROOT), str(ROOT / "src"), str(TERMY_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.chdir(ROOT)  # FlintNPC resolves "npcs/<name>" relative to the cwd

import registry  # noqa: E402
from FlintNPC import load_json_recursive  # noqa: E402

SAMPLE_SIZE = 40


def load_termy():
    loader = importlib.machinery.SourceFileLoader("termy", str(TERMY_DIR / "termy"))
    spec = importlib.util.spec_from_loader("termy", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


termy = load_termy()


def canned_result(command, response=""):
    return {
        "status": "exact match",
        "confidence": 1.0,
        "permission": "yolo",
        "response": response,
        "tools": [[{"arguments": {"command": command, "explanation": "Test"}}]],
    }


def sample_prompts():
    dataset = load_json_recursive(str(TERMY_DIR / "dataset"), "dataset_*.json")
    prompts = [p for entry in dataset for p in entry.get("input", [])]
    return random.Random(0).sample(prompts, SAMPLE_SIZE)  # noqa: S311


class TestTermyDryRun(unittest.TestCase):
    def run_termy(self, argv, api_result=None):
        """Runs termy with every process-starting call replaced by a recorder."""
        run, popen = mock.MagicMock(), mock.MagicMock()
        stdin = mock.MagicMock(isatty=lambda: True)
        confirm = mock.MagicMock(side_effect=AssertionError("prompted"))
        out = io.StringIO()
        patches = [
            mock.patch.object(termy.ApiProvider, "request", return_value=api_result),
            mock.patch.object(termy.subprocess, "run", run),
            mock.patch.object(termy.subprocess, "Popen", popen),
            mock.patch.object(termy.tui, "confirm", confirm),
            mock.patch.object(sys, "argv", ["termy", *argv]),
            mock.patch.object(sys, "stdin", stdin),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ]
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            code = termy.run_cli()
        return code, run.call_count + popen.call_count, out.getvalue()

    def test_yolo_command_runs_without_dry_run_example(self):
        result = canned_result("echo should-not-run")
        _, calls, _ = self.run_termy(["say", "hi"], result)
        self.assertEqual(calls, 1)

    def test_dry_run_prints_command_without_running_example(self):
        result = canned_result("echo should-not-run", "Here you go.")
        code, calls, out = self.run_termy(["-n", "say", "hi"], result)
        self.assertEqual(code, 0)
        self.assertEqual(calls, 0)
        self.assertIn("echo should-not-run", out)
        self.assertIn("yolo", out)

    def test_dry_run_hides_permission_without_command_example(self):
        result = {"status": "rejected", "confidence": 0.0, "permission": "yolo"}
        _, calls, out = self.run_termy(["-n", "blorp"], result)
        self.assertEqual(calls, 0)
        self.assertNotIn("Permission", out)

    def test_dry_run_never_runs_commands_invariant(self):
        registry.REGISTRY_DIR = ROOT  # use the repo, not ~/.local/share
        for prompt in sample_prompts():
            with self.subTest(prompt=prompt):
                code, calls, _ = self.run_termy(["--dry-run", prompt])
                self.assertEqual(code, 0)
                self.assertEqual(calls, 0)


if __name__ == "__main__":
    unittest.main()
