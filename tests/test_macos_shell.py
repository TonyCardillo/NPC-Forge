"""
Tests that TERMy shell code works under macOS /bin/bash (3.2) and BSD
tools, not only under GNU/Linux.
"""
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "npcs" / "termy" / "scripts"
DATASET = ROOT / "npcs" / "termy" / "dataset"
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
        [BASH, "-c", script], input=stdin, capture_output=True, text=True, timeout=60
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

class TestHelpersOnBash32(unittest.TestCase):
    def test_termy_question_sets_caller_variable_example(self):
        script = f'source "{SCRIPTS / "termy.sh"}"; {STUBS} termy_question "Name" ans; printf "[%s]" "$ans"'
        res = run_bash(script, stdin="hello\n")
        self.assertEqual(res.stdout.split("Name: ")[-1], "[hello]", res.stderr)
        self.assertEqual(res.stderr, "")

    def test_termy_execute_extension_case_invariant(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("run.py", "run.PY", "run.Py"):
                with self.subTest(name=name):
                    path = Path(tmp) / name
                    path.write_text("print('ok')\n")
                    script = f'source "{SCRIPTS / "files.sh"}"; {STUBS} termy_execute "{path}"'
                    res = run_bash(script)
                    self.assertEqual(res.returncode, 0, res.stderr)
                    self.assertEqual(res.stdout.strip(), "ok")

OPTIONAL_TOOLS = {"pstree", "watch", "qrencode", "yt-dlp", "chocolate-doom"}  # all in Homebrew

READ_ONLY_INTENTS = {
    "dataset_system.json": [
        "give me info about my motherboard",
        "daemon status",
        "show memory usage",
        "show gpu information",
        "show info about my drives",
        "show connected usb devices",
        "show me system logs",
        "show me kernel logs",
        "show me auth logs",
        "what is this cpu",
        "check the current internal temperature of the CPU",
        "find which processes are consuming the most RAM",
        "check battery status",
        "kernel modules dependency view",
        "display history of reboots",
        "How much RAM is free right now?",
        "Show memory usage in gigabytes.",
        "Print the percentage of memory currently in use.",
    ],
    "dataset_network.json": [
        "show network interfaces",
        "which ports are currently listening",
        "List connections stuck in TIME-WAIT.",
        "List all listening TCP and UDP sockets with programs.",
        "Print all the IP addresses assigned to this host.",
        "What's listening on this machine and on which ports?",
        "Show every listening socket and its process.",
        "List all listening ports with the owning programs.",
    ],
}

def commands_by_intent(file_name):
    """Maps the first input of each entry in a TERMy dataset file to its command."""
    entries = json.loads((DATASET / file_name).read_text(encoding="utf-8"))
    return {e["input"][0]: t["arguments"]["command"] for e in entries for t in e.get("tools") or []}

PORTED_FILES = [
    "dataset_system.json",
    "dataset_network.json",
    "dataset_files.json",
    "templates_files.json",
    "templates_nl2bash.json",
    "dataset_formats.json",
    "dataset_games.json",
    "dataset_http.json",
]

def file_commands(file_name):
    return list(gap.commands_in(json.loads((DATASET / file_name).read_text(encoding="utf-8"))))

def find_command(file_name, text):
    """Returns the one command in a dataset file that contains the given text."""
    (command,) = [c for c in file_commands(file_name) if text in c]
    return command

def fill_slots(command, slots):
    for name, value in slots.items():
        command = command.replace(f"<||{name}||>", value)
    return command

class TestPortedDatasets(unittest.TestCase):
    def test_ported_datasets_have_no_linux_problems_invariant(self):
        helpers = gap.helper_functions()
        for file_name in PORTED_FILES:
            for command in file_commands(file_name):
                with self.subTest(file=file_name, command=command[:60]):
                    issues = gap.classify(command, helpers)
                    self.assertFalse(issues["linux-only"] | issues["gnu-flags"] | issues["bash4"])
                    self.assertLessEqual(issues["not-installed"], OPTIONAL_TOOLS)

    @unittest.skipUnless(sys.platform == "darwin", "runs macOS system commands")
    def test_read_only_ported_commands_run_on_macos_invariant(self):
        for file_name, intents in READ_ONLY_INTENTS.items():
            commands = commands_by_intent(file_name)
            for intent in intents:
                with self.subTest(file=file_name, intent=intent):
                    res = run_bash(f"{STUBS} {commands[intent]}")
                    self.assertEqual(res.returncode, 0, res.stderr)
                    self.assertTrue(res.stdout.strip())
                    self.assertNotIn("command not found", res.stderr)

# (dataset file, text in the command, slots, file name, content before, content after, stdin)
FILE_EDIT_CASES = [
    ("templates_files.json", "s/\\r$//", {"file": "f.txt"}, "f.txt", "a\r\nb\r\n", "a\nb\n", ""),
    ("templates_files.json", "s/.$//", {"url": "f.txt"}, "f.txt", "abc\n", "ab\n", ""),
    ("templates_files.json", "s/\\t/", {"file": "f.txt", "indents": "2"}, "f.txt", "x\ty\n", "x  y\n", ""),
    ("templates_nl2bash.json", "1s/^/hi", {}, "a.py", "print(1)\n", "hi\nprint(1)\n", ""),
    ("dataset_files.json", 'sed -i', {}, "f.txt", "foo foo\n", "bar bar\n", "f.txt\nfoo\nbar\n"),
]

class TestFileCommandsOnBsd(unittest.TestCase):
    def run_in(self, folder, command, stdin=""):
        script = f'source "{SCRIPTS / "termy.sh"}"; {STUBS} {command}'
        return subprocess.run(  # noqa: S603
            [BASH, "-c", script], input=stdin, capture_output=True, text=True, timeout=60, cwd=folder
        )

    def test_file_edit_commands_on_bsd_example(self):
        for file_name, text, slots, target, before, after, stdin in FILE_EDIT_CASES:
            with self.subTest(file=file_name, text=text), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / target).write_text(before)
                res = self.run_in(tmp, fill_slots(find_command(file_name, text), slots), stdin)
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertEqual((Path(tmp) / target).read_text(), after)

    def test_python_def_names_on_bsd_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src.py").write_text("  def foo(x):\n\tdef _bar2 ( ):\nclass A:\n")
            command = find_command("templates_files.json", "def")
            res = self.run_in(tmp, fill_slots(command, {"file": "src.py"}))
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout, "foo\n_bar2\n")

if __name__ == "__main__":
    unittest.main()
