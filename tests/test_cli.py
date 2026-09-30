"""
Tests for the npc-forge command line tool.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import cli  # noqa: E402
import logger  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import is_live, make_home, socket_path, wait_for  # noqa: E402

HAS_FLASK = importlib.util.find_spec("flask") is not None


class TestLogs(unittest.TestCase):
    def test_watch_follows_the_logger_file_example(self):
        self.assertEqual(cli.LOG_FILE_PATH, logger.log_file_path)


@unittest.skipUnless(HAS_FLASK, "needs Flask: run with .venv/bin/python")
class TestServerCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.sock = socket_path(make_home(self.tmp.name))

    def tearDown(self):
        subprocess.run(["pkill", "-f", f"server.py --unix {self.sock}"], check=False)  # noqa: S603, S607
        self.tmp.cleanup()

    def npc_forge(self, *args):
        return subprocess.run(  # noqa: S603
            [sys.executable, str(SRC / "cli.py"), *args],
            env={**os.environ, "HOME": str(self.home)},
            cwd=SRC, capture_output=True, text=True, timeout=60,
        )

    def is_running(self):
        res = subprocess.run(["pgrep", "-f", f"server.py --unix {self.sock}"], capture_output=True)  # noqa: S603, S607
        return res.returncode == 0

    def test_serve_starts_the_server_example(self):
        res = self.npc_forge("serve")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(is_live(self.sock))

    def test_serve_twice_keeps_one_server_idempotence(self):
        self.npc_forge("serve")
        res = self.npc_forge("serve")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("already running", res.stdout)
        self.assertTrue(is_live(self.sock))

    def test_stop_stops_the_server_and_removes_the_socket_example(self):
        self.npc_forge("serve")
        res = self.npc_forge("stop")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(wait_for(lambda: not self.is_running(), timeout=10))
        self.assertFalse(self.sock.exists())

    def test_stop_without_server_example(self):
        res = self.npc_forge("stop")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("not running", res.stdout)

    def test_restart_leaves_a_running_server_example(self):
        self.npc_forge("serve")
        res = self.npc_forge("restart")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(is_live(self.sock))


if __name__ == "__main__":
    unittest.main()
