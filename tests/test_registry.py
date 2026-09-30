"""
Tests for the NPC registry, which loads each NPC engine once per process.
"""
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import registry  # noqa: E402


class TestRegistry(unittest.TestCase):
    def test_concurrent_loads_create_one_engine_idempotence(self):
        created = []

        class SlowEngine:
            def __init__(self, name):
                time.sleep(0.2)
                created.append(name)

        engines = []
        with mock.patch.object(registry, "REGISTRY_DIR", ROOT), \
             mock.patch.dict(registry.NPC_REGISTRY, clear=True), \
             mock.patch("FlintNPC.FlintNPC", SlowEngine):
            threads = [threading.Thread(target=lambda: engines.append(registry.get_npc_engine("termy")))
                       for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(created, ["termy"])
        self.assertEqual(len({id(engine) for engine in engines}), 1)


if __name__ == "__main__":
    unittest.main()
