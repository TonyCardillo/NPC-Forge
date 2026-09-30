"""
Tests for the shared logger: importing it must work on a fresh machine,
before setup.sh has created ~/.local/share/npc-forge.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class TestLogger(unittest.TestCase):
    def test_import_creates_log_folder_in_fresh_home_example(self):
        with tempfile.TemporaryDirectory() as home:
            res = subprocess.run(  # noqa: S603
                [sys.executable, "-c", "import logger"],
                cwd=ROOT / "src",
                env={**os.environ, "HOME": home},
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue((Path(home) / ".local/share/npc-forge/logs").is_dir())

if __name__ == "__main__":
    unittest.main()
