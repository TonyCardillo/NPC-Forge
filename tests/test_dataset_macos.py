"""
Tests for dataset_macos.json: everyday macOS and developer tasks.
"""

import json
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (str(ROOT / "src"), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.chdir(ROOT)  # FlintNPC resolves "npcs/<name>" relative to the cwd

from test_macos_shell import gap, run_termy_shell  # noqa: E402

from FlintNPC import FlintNPC  # noqa: E402

DATASET = ROOT / "npcs" / "termy" / "dataset"
MACOS = DATASET / "dataset_macos.json"
TEMPLATES = DATASET / "templates_macos.json"
WRITES = {
    "macos_git_commit_all",
    "macos_git_push",
    "macos_git_stash",
    "macos_git_stash_pop",
    "macos_git_switch",
    "macos_git_switch_main",
    "macos_uv_sync",
    "macos_markdown_to_docx",
    "macos_resize_image",
    "macos_unzip",
    "macos_git_merge_into_main",
    "macos_git_delete_branch",
}
TEMPLATE_WRITES = {
    "macos_kill_pid",
    "macos_kill_port",
    "macos_unzip_named",
    "macos_docx_named",
    "macos_quit_app",
    "macos_force_quit_app",
}
OPTIONAL_TOOLS = {"pandoc", "pdftotext"}

# Prompts as I would type them, some of them not in the dataset
EXAMPLES = [
    ("commit everything", "git commit"),
    ("push my changes", "git push"),
    ("stash my changes", "git stash push"),
    ("pop the stash", "git stash pop"),
    ("switch branch", 'git switch "$branch"'),
    ("switch to main", "git switch main"),
    ("what changed in this repo", "git diff --stat"),
    ("uv sync", "uv sync"),
    ("run the tests", "unittest discover"),
    ("activate the venv", "source .venv/bin/activate"),
    ("open this folder in finder", "open ."),
    ("open a file", 'open "$file"'),
    ("what is using port 5000", "lsof -nP"),
    ("how long has my mac been up", "uptime"),
    ("keep my mac awake", "caffeinate"),
    ("paste the clipboard", "pbpaste"),
    ("copy this file to the clipboard", "pbcopy <"),
    ("show the size of this folder", "du -sh ."),
    ("what is taking space in this folder", "sort -h"),
    ("show hidden files", "ls -ld .[!.]*"),
    ("list running python processes", "pgrep -fl python"),
    ("convert markdown to docx", "pandoc"),
    ("extract text from a pdf", "pdftotext"),
    ("resize an image", "sips -Z"),
    ("unzip a file", "unzip"),
    ("take a screenshot", "screencapture -i"),
    ("lock my screen", "pmset displaysleepnow"),
    ("push", "git push"),
    ("commit this", "git commit"),
    ("merge to main", "git merge"),
    ("delete this branch", "git branch -d"),
    ("what is my local ip", "ipconfig getifaddr"),
]

# Prompts with an argument, matched by templates_macos.json
TEMPLATE_EXAMPLES = [
    ("open arithmetic.f", "open -- 'arithmetic.f'"),
    ("open arithmetic.f for me", "open -- 'arithmetic.f'"),
    ("open notes/README.md", "open -- 'notes/README.md'"),
    ("kill 91907", "pid='91907'"),
    ("kill process 91907", "pid='91907'"),
    ("kill the process on port 5000", "port='5000'"),
    ("kill port 5000", "port='5000'"),
    ("unzip archive.zip", "unzip -q -- 'archive.zip'"),
    ("convert notes.md to docx", "-- 'notes.md'"),
    ("convert notes.md to word", "-- 'notes.md'"),
    ("quit mail", "app='mail'"),
    ("force quit mail", "pkill -ix -- 'mail'"),
]
# (prompt, template it must not reach)
NOT_TEMPLATES = [
    ("open file README.md", "macos_open_named"),
    ("kill the process on port 5000", "macos_kill_pid"),
    ("open the readme", "macos_open_named"),
    ("unzip an archive", "macos_unzip_named"),
]

def blocks():
    return json.loads(MACOS.read_text())

def command(category):
    block = next(b for b in blocks() if b["category"] == category)
    return block["tools"][0]["arguments"]["command"]

def command_of(result):
    tools = result.get("tools") or []
    while tools and isinstance(tools[0], list):
        tools = tools[0]
    return " && ".join(t["arguments"]["command"] for t in tools if isinstance(t, dict))

def drop_letter(text, rng, known=()):
    """Drops one inner letter of the longest word, unless that makes another known word."""
    words = text.split()
    i = max(range(len(words)), key=lambda k: len(words[k]))
    word = words[i]
    if len(word) < 5:
        return None
    j = rng.randrange(1, len(word) - 1)
    words[i] = word[:j] + word[j + 1 :]
    return None if words[i] in known else " ".join(words)

def write_png(path, width, height):
    """Writes a plain white RGB PNG."""

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + b"\xff" * 3 * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )

def tool(*args, folder=None):
    res = subprocess.run(args, cwd=folder, check=True, capture_output=True, text=True)  # noqa: S603
    return res.stdout

def git(folder, *args):
    return tool("git", *args, folder=folder)

def make_repo(folder):
    git(folder, "init", "-q", "-b", "main")
    git(folder, "config", "user.email", "test@example.com")
    git(folder, "config", "user.name", "Test")
    (Path(folder) / "a.txt").write_text("one\n")

class TestMacosDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.npc = FlintNPC("termy", log_level="CRITICAL")

    def ask(self, prompt):
        self.npc.active_context_map = {}
        return self.npc.process_messages(prompt)

    def test_my_prompts_match_example(self):
        for prompt, expected in EXAMPLES:
            with self.subTest(prompt=prompt):
                self.assertIn(expected, command_of(self.ask(prompt)))

    def test_every_input_matches_its_own_command_invariant(self):
        for block in blocks():
            for text in block["input"]:
                with self.subTest(text=text):
                    self.assertEqual(command_of(self.ask(text)), command(block["category"]))

    def test_one_dropped_letter_keeps_the_command_invariant(self):
        rng = random.Random(0)  # noqa: S311
        for block in blocks():
            for text in block["input"]:
                typo = drop_letter(text, rng, self.npc.nlp.weights)
                if typo:
                    with self.subTest(typo=typo):
                        self.assertEqual(command_of(self.ask(typo)), command(block["category"]))

    def test_inputs_are_not_in_other_datasets_invariant(self):
        mine = {t.lower().strip() for b in blocks() for t in b["input"]}
        for path in DATASET.glob("dataset_*.json"):
            if path == MACOS:
                continue
            for block in json.loads(path.read_text()):
                for text in block.get("input", []):
                    self.assertNotIn(text.lower().strip(), mine, path.name)

    def test_commands_that_change_things_ask_first_example(self):
        for block in blocks():
            expected = "ask" if block["category"] in WRITES else "yolo"
            self.assertEqual(block["permission"], expected, block["category"])

    def test_my_template_prompts_fill_the_slots_example(self):
        for prompt, expected in TEMPLATE_EXAMPLES:
            with self.subTest(prompt=prompt):
                result = self.ask(prompt)
                self.assertEqual(result["status"], "template match")
                self.assertIn(expected, command_of(result))

    def test_other_prompts_do_not_reach_these_templates_example(self):
        for prompt, intent in NOT_TEMPLATES:
            with self.subTest(prompt=prompt):
                self.assertNotEqual(self.matched_intent(prompt), intent)

    def matched_intent(self, prompt):
        structure, _ = self.npc.nlp.parse_structure(prompt, self.npc.sentence_threshold)
        template = self.npc.nlp.match_structure(self.npc.templates, structure)
        return template.get("intent") if template else None

    def test_templates_that_change_things_ask_first_example(self):
        for template in json.loads(TEMPLATES.read_text()):
            expected = "ask" if template["intent"] in TEMPLATE_WRITES else "yolo"
            self.assertEqual(template["permission"], expected, template["intent"])

    def test_commands_have_no_linux_problems_invariant(self):
        helpers = gap.helper_functions()
        for block in blocks():
            with self.subTest(category=block["category"]):
                issues = gap.classify(command(block["category"]), helpers)
                self.assertFalse(issues["linux-only"] | issues["gnu-flags"] | issues["bash4"])
                self.assertLessEqual(issues["not-installed"], OPTIONAL_TOOLS)

@unittest.skipUnless(sys.platform == "darwin", "runs macOS commands")
class TestMacosCommandsRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.npc = FlintNPC("termy", log_level="CRITICAL")

    def setUp(self):
        self.npc.active_context_map = {}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def run_command(self, category, stdin="", stubs=""):
        res = run_termy_shell(command(category), stdin, str(self.tmp), stubs)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res

    def test_folder_size_example(self):
        (self.tmp / "a.txt").write_text("x" * 5000)
        self.assertIn("\t.", self.run_command("macos_folder_size").stdout)

    def test_biggest_items_come_last_example(self):
        (self.tmp / "big.bin").write_bytes(b"x" * 300_000)
        (self.tmp / "small.txt").write_text("x")
        (self.tmp / ".hidden").write_text("x")
        out = self.run_command("macos_biggest_items").stdout
        self.assertTrue(out.strip().splitlines()[-1].endswith("big.bin"), out)
        self.assertIn(".hidden", out)

    def test_hidden_files_example(self):
        self.assertIn("No hidden files", self.run_command("macos_hidden_files").stdout)
        (self.tmp / ".env").write_text("x")
        self.assertIn(".env", self.run_command("macos_hidden_files").stdout)

    def test_git_workflow_example(self):
        make_repo(self.tmp)
        self.run_command("macos_git_commit_all", "first commit\n")
        (self.tmp / "a.txt").write_text("two\n")
        self.assertIn("a.txt", self.run_command("macos_git_what_changed").stdout)
        self.run_command("macos_git_stash")
        self.assertEqual((self.tmp / "a.txt").read_text(), "one\n")
        self.run_command("macos_git_stash_pop")
        self.assertEqual((self.tmp / "a.txt").read_text(), "two\n")
        git(self.tmp, "branch", "feature")
        self.run_command("macos_git_switch", "feature\n")
        self.run_command("macos_git_switch_main")
        self.assertEqual(git(self.tmp, "branch", "--show-current").strip(), "main")

    def test_run_tests_falls_back_to_unittest_example(self):
        (self.tmp / "tests").mkdir()
        (self.tmp / "tests" / "test_one.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n"
        )
        self.assertIn("OK", self.run_command("macos_run_tests").stderr)

    def test_venv_hint_copies_the_command_example(self):
        stubs = "pbcopy() { cat > clip.txt; };"
        self.run_command("macos_venv_hint", stubs=stubs)
        self.assertEqual((self.tmp / "clip.txt").read_text(), "source .venv/bin/activate")

    def test_copy_file_to_clipboard_example(self):
        (self.tmp / "a.txt").write_text("hello\n")
        self.run_command("macos_copy_file_to_clipboard", "a.txt\n", stubs='pbcopy() { cat > clip.txt; };')
        self.assertEqual((self.tmp / "clip.txt").read_text(), "hello\n")

    def test_unzip_example(self):
        with zipfile.ZipFile(self.tmp / "pack.zip", "w") as z:
            z.writestr("inner.txt", "hello")
        self.run_command("macos_unzip", "pack.zip\n")
        self.assertEqual((self.tmp / "pack" / "inner.txt").read_text(), "hello")

    def test_resize_image_example(self):
        write_png(self.tmp / "pic.png", 8, 4)
        self.run_command("macos_resize_image", "pic.png\n2\n")
        self.assertIn("pixelWidth: 2", tool("sips", "-g", "pixelWidth", str(self.tmp / "pic-2px.png")))

    @unittest.skipUnless(shutil.which("pandoc"), "needs pandoc")
    def test_markdown_to_docx_example(self):
        (self.tmp / "notes.md").write_text("# Title\n")
        self.run_command("macos_markdown_to_docx", "notes.md\n")
        self.assertTrue((self.tmp / "notes.docx").exists())

    def test_port_lookup_with_no_listener_example(self):
        self.assertIn("Nothing is listening", self.run_command("macos_port_lookup", "1\n").stdout)

    def run_prompt(self, prompt, stdin="", stubs=""):
        res = run_termy_shell(command_of(self.npc.process_messages(prompt)), stdin, str(self.tmp), stubs)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res

    def test_open_named_file_example(self):
        stubs = 'open() { printf "%s\\n" "$@" > opened.txt; };'
        (self.tmp / "a.f").write_text("x")
        self.run_prompt("open a.f", stubs=stubs)
        self.assertEqual((self.tmp / "opened.txt").read_text(), "--\na.f\n")

    def test_open_missing_file_says_so_example(self):
        self.assertIn("No file or folder named nope.f", self.run_prompt("open nope.f").stdout)

    def test_kill_named_pid_example(self):
        proc = subprocess.Popen(["sleep", "30"])  # noqa: S603, S607
        self.addCleanup(proc.kill)
        self.run_prompt(f"kill {proc.pid}")
        self.assertIsNotNone(proc.wait(timeout=5))

    def test_kill_process_on_port_example(self):
        server = (
            "import socket, time; s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(); "
            "print(s.getsockname()[1], flush=True); time.sleep(30)"
        )
        proc = subprocess.Popen([sys.executable, "-c", server], stdout=subprocess.PIPE, text=True)  # noqa: S603
        self.addCleanup(proc.kill)
        port = proc.stdout.readline().strip()
        self.run_prompt(f"kill the process on port {port}")
        self.assertIsNotNone(proc.wait(timeout=5))

    def test_unzip_named_file_example(self):
        with zipfile.ZipFile(self.tmp / "pack.zip", "w") as z:
            z.writestr("inner.txt", "hello")
        self.run_prompt("unzip pack.zip")
        self.assertEqual((self.tmp / "pack" / "inner.txt").read_text(), "hello")

    @unittest.skipUnless(shutil.which("pandoc"), "needs pandoc")
    def test_docx_named_file_example(self):
        (self.tmp / "notes.md").write_text("# Title\n")
        self.run_prompt("convert notes.md to docx")
        self.assertTrue((self.tmp / "notes.docx").exists())

    def test_quit_app_uses_applescript_example(self):
        stubs = 'osascript() { printf "%s\\n" "$@" > script.txt; };'
        self.run_prompt("quit mail", stubs=stubs)
        self.assertEqual((self.tmp / "script.txt").read_text(), '-e\nquit app "mail"\n')

    def test_read_only_commands_run_example(self):
        for category in ("macos_uptime", "macos_python_processes"):
            with self.subTest(category=category):
                self.assertTrue(self.run_command(category).stdout.strip())

if __name__ == "__main__":
    unittest.main()
