"""
Tests that TERMy shell code works under macOS /bin/bash (3.2) and BSD
tools, not only under GNU/Linux.
"""
import importlib.machinery
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "npcs" / "termy" / "scripts"
BASH = "/bin/bash"
STUBS = "termy_say() { :; }; termy_set_context() { :; }; tput() { :; };"

def load_linux_gap():
    path = str(ROOT / "scripts" / "linux-gap")
    loader = importlib.machinery.SourceFileLoader("linux_gap", path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("linux_gap", loader))
    loader.exec_module(module)
    return module

gap = load_linux_gap()

def run_bash(script, stdin=""):
    return subprocess.run(  # noqa: S603
        [BASH, "-c", script], input=stdin, capture_output=True, text=True
    )

def python_wrapper_line():
    """Returns the temp file line shared by every Python snippet entry."""
    command = next(c for group, _, c in gap.dataset_commands() if group == "python snippets")
    return command.splitlines()[0].removesuffix("&&").strip()

def remove_temp_script(path):
    """Removes only what the wrapper created: a termy_script_* folder or file."""
    if path.parent.name.startswith("termy_script_"):
        shutil.rmtree(path.parent)
    elif path.name.startswith("termy_script_"):
        path.unlink(missing_ok=True)

class TestPythonWrapper(unittest.TestCase):
    def test_python_wrapper_temp_files_are_unique_example(self):
        script = f'{python_wrapper_line()} && : > "$TMP_FILE" && printf "%s" "$TMP_FILE"'
        first, second = run_bash(script), run_bash(script)
        try:
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertNotEqual(first.stdout, second.stdout)
            self.assertTrue(first.stdout.endswith(".py"))
        finally:
            for res in (first, second):
                remove_temp_script(Path(res.stdout))

    def test_no_dataset_command_uses_mktemp_suffix_invariant(self):
        flagged = sum("mktemp suffix" in gap.gnu_flags(c) for _, _, c in gap.dataset_commands())
        self.assertEqual(flagged, 0)

if __name__ == "__main__":
    unittest.main()
