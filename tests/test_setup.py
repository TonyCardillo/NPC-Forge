"""
End-to-end tests for setup.sh on macOS, with a fake HOME. They create a
venv and install packages from PyPI, so they run only when
NPC_FORGE_SLOW_TESTS=1 is set.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH_LINE = 'export PATH="$HOME/.local/bin:$PATH"'
SLOW = os.environ.get("NPC_FORGE_SLOW_TESTS") == "1"


def clean_path():
    """PATH without any ~/.local/bin entry, as on a fresh Mac."""
    return ":".join(p for p in os.environ["PATH"].split(":") if not p.endswith("/.local/bin"))


@unittest.skipUnless(SLOW, "set NPC_FORGE_SLOW_TESTS=1 to run the installer end to end")
class TestSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.tmp.name)
        cls.env = {**os.environ, "HOME": str(cls.home), "SHELL": "/bin/zsh", "PATH": clean_path()}
        cls.first = cls.setup_sh()
        cls.second = cls.setup_sh()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def setup_sh(cls, *args):
        return subprocess.run(  # noqa: S603
            ["/bin/bash", str(ROOT / "setup.sh"), *args],
            env=cls.env, cwd=ROOT, capture_output=True, text=True, timeout=600,
        )

    def test_install_succeeds_example(self):
        self.assertEqual(self.first.returncode, 0, self.first.stdout + self.first.stderr)
        self.assertEqual(self.second.returncode, 0, self.second.stdout + self.second.stderr)

    def test_npc_forge_command_works_example(self):
        res = subprocess.run(  # noqa: S603
            [str(self.home / ".local/bin/npc-forge"), "list"],
            env=self.env, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("termy", res.stdout)

    def test_installed_serve_and_stop_work_example(self):
        npc_forge = str(self.home / ".local/bin/npc-forge")
        sock = self.home / ".local/share/npc-forge/run/server.sock"
        serve = subprocess.run([npc_forge, "serve"], env=self.env, capture_output=True, text=True, timeout=60)  # noqa: S603
        self.assertEqual(serve.returncode, 0, serve.stdout + serve.stderr)
        self.assertTrue(sock.exists())
        stop = subprocess.run([npc_forge, "stop"], env=self.env, capture_output=True, text=True, timeout=60)  # noqa: S603
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)
        self.assertFalse(sock.exists())

    def test_zshrc_gets_one_path_line_idempotence(self):
        zshrc = (self.home / ".zshrc").read_text()
        self.assertEqual(zshrc.count(PATH_LINE), 1)

    def test_no_systemd_files_example(self):
        self.assertFalse((self.home / ".config/systemd").exists())

    def test_old_python_is_refused_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**self.env, "HOME": tmp, "PATH": "/usr/bin:/bin"}  # macOS system Python 3.9
            res = subprocess.run(  # noqa: S603
                ["/bin/bash", str(ROOT / "setup.sh")], env=env, cwd=ROOT, capture_output=True, text=True
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("3.10", res.stdout + res.stderr)
            self.assertFalse((Path(tmp) / ".local/share/npc-forge").exists())

    def test_uninstall_removes_everything_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**self.env, "HOME": tmp}
            install = subprocess.run(  # noqa: S603
                ["/bin/bash", str(ROOT / "setup.sh")], env=env, cwd=ROOT, capture_output=True, timeout=600
            )
            self.assertEqual(install.returncode, 0)
            res = subprocess.run(  # noqa: S603
                ["/bin/bash", str(ROOT / "setup.sh"), "--uninstall"], env=env, cwd=ROOT, capture_output=True
            )
            self.assertEqual(res.returncode, 0)
            self.assertFalse((Path(tmp) / ".local/share/npc-forge").exists())
            self.assertFalse((Path(tmp) / ".local/bin/npc-forge").exists())


if __name__ == "__main__":
    unittest.main()
