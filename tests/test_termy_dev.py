"""
Tests for scripts/termy-dev, which runs TERMy from the repo in dry-run
mode with no install and no server.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERMY_DEV = ROOT / "scripts" / "termy-dev"

def run_termy_dev(args, prompt):
    with tempfile.TemporaryDirectory() as home:
        return subprocess.run(  # noqa: S603
            [sys.executable, str(TERMY_DEV), *args],
            input=prompt,
            env={**os.environ, "HOME": home},
            capture_output=True,
            text=True,
        )

class TestTermyDev(unittest.TestCase):
    def test_termy_dev_prints_dry_run_example(self):
        res = run_termy_dev([], "what time is it")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Dry run: nothing was executed", res.stdout)
        self.assertIn("date +%T", res.stdout)

    def test_termy_dev_ignores_yes_flag_example(self):
        res = run_termy_dev(["-y"], "what time is it")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Dry run: nothing was executed", res.stdout)

    def test_termy_dev_hides_engine_logs_example(self):
        res = run_termy_dev([], "what time is it")
        self.assertNotIn("|INFO|", res.stderr)
        self.assertNotIn("|ERROR|", res.stderr)

if __name__ == "__main__":
    unittest.main()
