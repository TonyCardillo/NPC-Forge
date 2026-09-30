"""
Tests for LocalProvider, the in-process fallback TERMy uses when the
NPC-Forge server is offline.
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (str(ROOT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

os.chdir(ROOT)  # FlintNPC resolves "npcs/<name>" relative to the cwd

import registry  # noqa: E402
from FlintNPC import FlintNPC  # noqa: E402

PROMPTS = [
    "what time is it",
    "how are you",
    "list the files in this directory",
    "xyzzy plugh",
]


class TestLocalProvider(unittest.TestCase):
    def test_local_provider_module_imports_example(self):
        from providers.local import LocalProvider

        self.assertTrue(callable(LocalProvider))

    def test_local_provider_matches_engine_oracle(self):
        from providers.local import LocalProvider

        registry.REGISTRY_DIR = ROOT  # use the repo, not ~/.local/share
        provider = LocalProvider(str(ROOT), str(ROOT / "npcs" / "termy"))
        engine = FlintNPC("termy", log_level="WARNING")

        for prompt in PROMPTS:
            with self.subTest(prompt=prompt):
                got = provider.request("termy", prompt)
                want = engine.process_messages(prompt)
                self.assertNotIn("error", got)
                self.assertEqual(got.get("status"), want.get("status"))
                self.assertEqual(got.get("confidence"), want.get("confidence"))


if __name__ == "__main__":
    unittest.main()
