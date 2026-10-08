"""
Tests for the uncertainty signals of FlintNPC (ignored rare words) and
for the learned dataset that holds entries written by the LLM fallback.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

os.chdir(ROOT)  # FlintNPC resolves "npcs/<name>" relative to the cwd

from FlintNPC import FlintNPC  # noqa: E402


class TestIgnoredWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.npc = FlintNPC("termy", log_level="CRITICAL")

    def ask(self, prompt):
        self.npc.active_context_map = {}
        return self.npc.process_messages(prompt)

    def test_match_that_ignores_a_rare_word_reports_it_example(self):
        result = self.ask("find and drop empty folders")
        self.assertEqual(result["status"], "probabilistic match")
        self.assertIn("empty", result["ignored_words"])

    def test_typo_match_ignores_no_word_example(self):
        result = self.ask("show me the contnts of this folder")
        self.assertEqual(result["status"], "probabilistic match")
        self.assertEqual(result["ignored_words"], [])

    def test_exact_match_ignores_no_word_example(self):
        self.assertEqual(self.ask("what time is it").get("ignored_words", []), [])

    def test_composite_prompt_collects_words_of_every_part_example(self):
        result = self.ask("find and drop empty folders; show me the contnts of this folder")
        self.assertIn("empty", result["ignored_words"])

class TestLearnedDataset(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.learned = self.root / "learned.json"
        npc = self.root / "npcs" / "mini"
        (npc / "dataset").mkdir(parents=True)
        (npc / "config.json").write_text(json.dumps({"learned_dataset": str(self.learned)}))
        (npc / "dataset" / "dataset_a.json").write_text(
            json.dumps([{"input": ["say hello"], "output": ["hello"]}])
        )
        old = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old)

    def test_learned_entries_are_loaded_example(self):
        self.learned.write_text(json.dumps([{"input": ["say goodbye"], "output": ["bye"]}]))
        npc = FlintNPC("mini", log_level="CRITICAL")
        self.assertIn("say goodbye", npc.exact_match_map)
        self.assertIn("say hello", npc.exact_match_map)

    def test_missing_learned_file_is_fine_example(self):
        npc = FlintNPC("mini", log_level="CRITICAL")
        self.assertIn("say hello", npc.exact_match_map)

if __name__ == "__main__":
    unittest.main()
