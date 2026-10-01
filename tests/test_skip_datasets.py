"""
Tests that an NPC can skip dataset folders, so TERMy starts fast
without the four Python snippet sets.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (str(ROOT / "src"), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.chdir(ROOT)  # FlintNPC resolves "npcs/<name>" relative to the cwd

from support import make_home  # noqa: E402

import cli  # noqa: E402
from FlintNPC import FlintNPC, load_json, load_json_recursive  # noqa: E402

DATASET = ROOT / "npcs" / "termy" / "dataset"
PYTHON_SETS = {
    "python_ppqd",
    "python-glaive-100",
    "python-functions-reasoning-100",
    "Tested-143k-Python-Alpaca-80",
}

def write_set(folder, name, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps([{"input": [text]}]))

def inputs(blocks):
    return {text for block in blocks for text in block["input"]}

class TestLoadJsonRecursive(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        write_set(self.root, "dataset_root.json", "root")
        write_set(self.root / "keep", "dataset_keep.json", "keep")
        write_set(self.root / "skip", "dataset_skip.json", "skip")
        write_set(self.root / "skipped", "dataset_skipped.json", "skipped")

    def test_skipped_folders_are_not_loaded_example(self):
        blocks = load_json_recursive(str(self.root), "dataset_*.json", skip=["skip"])
        self.assertEqual(inputs(blocks), {"root", "keep", "skipped"})

    def test_no_skip_loads_every_folder_example(self):
        blocks = load_json_recursive(str(self.root), "dataset_*.json")
        self.assertEqual(inputs(blocks), {"root", "keep", "skip", "skipped"})

class TestTermySkipsPythonSets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start = time.perf_counter()
        cls.npc = FlintNPC("termy", log_level="WARNING")
        cls.startup = time.perf_counter() - start

    def test_config_skips_the_python_sets_example(self):
        config = load_json(str(ROOT / "npcs" / "termy"), "config.json")
        self.assertEqual(set(config["skip_datasets"]), PYTHON_SETS)
        for name in PYTHON_SETS:
            self.assertTrue((DATASET / name).is_dir(), name)

    def test_every_shell_input_still_matches_invariant(self):
        for path in sorted(DATASET.glob("dataset_*.json")):
            for text in inputs(b for b in json.loads(path.read_text()) if "input" in b):
                self.assertTrue(text.lower().strip() in self.npc.exact_match_map, f"{path.name}: {text}")

    def test_python_set_inputs_are_not_loaded_example(self):
        self.assertFalse("write a python function to reverse a string" in self.npc.exact_match_map)

    def test_termy_starts_fast_example(self):
        self.assertLess(self.startup, 0.5)

class TestCliList(unittest.TestCase):
    def test_list_counts_only_loaded_intents_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            forge = make_home(tmp)
            out = io.StringIO()
            old = cli.FORGE_DATA_DIR
            cli.FORGE_DATA_DIR = forge
            try:
                with contextlib.redirect_stdout(out):
                    cli.list_installed_npcs()
            finally:
                cli.FORGE_DATA_DIR = old
        row = next(line for line in out.getvalue().splitlines() if "termy" in line)
        intents = int(row.split()[2])
        self.assertLess(intents, 5000)

if __name__ == "__main__":
    unittest.main()
