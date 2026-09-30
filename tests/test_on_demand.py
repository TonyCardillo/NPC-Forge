"""
Tests for the on-demand NPC-Forge server: it listens on a private Unix
socket, stops itself when idle, and is started by the first client.
"""
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from providers.unix_socket import UnixSocketProvider  # noqa: E402

HAS_FLASK = importlib.util.find_spec("flask") is not None

def make_home(tmp):
    """Creates a fake HOME whose NPC-Forge data folder links to the repo NPCs."""
    forge = Path(tmp) / ".local" / "share" / "npc-forge"
    forge.mkdir(parents=True)
    (forge / "npcs").symlink_to(ROOT / "npcs")
    return forge

def socket_path(forge):
    return forge / "run" / "server.sock"

def start_server(home, *args):
    return subprocess.Popen(  # noqa: S603
        [sys.executable, str(SRC / "server.py"), *args],
        env={**os.environ, "HOME": str(home)},
        cwd=SRC,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def is_live(path):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(path))
        return True
    except OSError:
        return False

def wait_for(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False

class ServerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.forge = make_home(self.tmp.name)
        self.sock = socket_path(self.forge)
        self.procs = []

    def tearDown(self):
        for proc in self.procs:
            proc.kill()
            proc.wait()
        self.tmp.cleanup()

    def serve(self, *args):
        proc = start_server(self.home, "--unix", str(self.sock), *args)
        self.procs.append(proc)
        return proc

class TestUnixSocketProvider(unittest.TestCase):
    def test_provider_returns_none_without_server_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = UnixSocketProvider(Path(tmp) / "missing.sock", timeout=1.0)
            self.assertIsNone(provider.request("termy", "what time is it"))

@unittest.skipUnless(HAS_FLASK, "needs Flask: run with .venv/bin/python")
class TestOnDemandServer(ServerCase):
    def test_server_answers_over_unix_socket_example(self):
        self.serve("--idle-seconds", "60")
        self.assertTrue(wait_for(lambda: is_live(self.sock)))
        result = UnixSocketProvider(self.sock).request("termy", "what time is it")
        self.assertEqual(result["status"], "exact match")

    def test_socket_folder_is_private_example(self):
        self.serve("--idle-seconds", "60")
        self.assertTrue(wait_for(lambda: is_live(self.sock)))
        self.assertEqual(self.sock.parent.stat().st_mode & 0o777, 0o700)

    def test_server_exits_when_idle_example(self):
        proc = self.serve("--idle-seconds", "2")
        self.assertTrue(wait_for(lambda: is_live(self.sock)))
        self.assertTrue(wait_for(lambda: proc.poll() is not None))
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(self.sock.exists())

    def test_second_server_exits_when_one_is_live_example(self):
        self.serve("--idle-seconds", "60")
        self.assertTrue(wait_for(lambda: is_live(self.sock)))
        second = self.serve("--idle-seconds", "60")
        self.assertTrue(wait_for(lambda: second.poll() is not None, timeout=10))
        self.assertEqual(second.returncode, 0)
        result = UnixSocketProvider(self.sock).request("termy", "what time is it")
        self.assertEqual(result["status"], "exact match")

    def test_server_replaces_stale_socket_example(self):
        self.sock.parent.mkdir(mode=0o700)
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(str(self.sock))
        stale.close()
        self.serve("--idle-seconds", "60")
        self.assertTrue(wait_for(lambda: is_live(self.sock)))

@unittest.skipUnless(HAS_FLASK, "needs Flask: run with .venv/bin/python")
class TestAsk(ServerCase):
    def run_ask(self, start=True):
        """Calls on_demand.ask in a child process with the fake HOME."""
        code = (
            "import json, on_demand\n"
            "class Local:\n"
            "    def request(self, npc, query): return {'source': 'local'}\n"
            "import time\n"
            "t = time.monotonic()\n"
            f"result = on_demand.ask('termy', 'what time is it', Local(), start={start})\n"
            "print(json.dumps([result.get('source', 'server'), time.monotonic() - t]))\n"
        )
        res = subprocess.run(  # noqa: S603
            [sys.executable, "-c", code],
            env={**os.environ, "HOME": str(self.home), "NPC_FORGE_IDLE_SECONDS": "30"},
            cwd=SRC, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def tearDown(self):
        subprocess.run(["pkill", "-f", f"server.py --unix {self.sock}"], check=False)  # noqa: S603, S607
        super().tearDown()

    def test_first_ask_answers_locally_and_starts_server_example(self):
        self.assertEqual(self.run_ask()[0], "local")
        self.assertTrue(wait_for(lambda: is_live(self.sock)))
        time.sleep(3)  # the server preloads the engine in the background
        source, seconds = self.run_ask()
        self.assertEqual(source, "server")
        self.assertLess(seconds, 0.5)

    def test_ask_without_start_never_starts_server_example(self):
        self.assertEqual(self.run_ask(start=False)[0], "local")
        self.assertFalse(wait_for(lambda: is_live(self.sock), timeout=3))

if __name__ == "__main__":
    unittest.main()
