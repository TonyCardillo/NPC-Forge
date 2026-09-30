"""
Tests for the npc-forge command line tool.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import cli  # noqa: E402
import logger  # noqa: E402


class TestLogs(unittest.TestCase):
    def test_watch_follows_the_logger_file_example(self):
        self.assertEqual(cli.LOG_FILE_PATH, logger.log_file_path)


if __name__ == "__main__":
    unittest.main()
