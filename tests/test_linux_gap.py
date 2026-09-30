"""
Tests for scripts/linux-gap, the read-only report of dataset commands
that are likely to fail on macOS.
"""
import importlib.machinery
import importlib.util
import random
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def load_linux_gap():
    path = str(ROOT / "scripts" / "linux-gap")
    loader = importlib.machinery.SourceFileLoader("linux_gap", path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("linux_gap", loader))
    loader.exec_module(module)
    return module

gap = load_linux_gap()

HEREDOC_BODY = "declare -A m\nsed -i 's/a/b/' f\napt-get install x\nmktemp /tmp/aXXXXXX.py\n"

COMMANDS = [
    "sudo apt-get install -y qrencode && qrencode -t UTF8 \"$t\"",
    "ls -la | grep foo; echo done",
    "if [ -d \"$d\" ]; then rm -rf -- \"$d\"; fi",
    "OUT=$(get_public_ip | head -n 1) && printf '%s\\n' \"$OUT\"",
    "find . -name '*.log' -printf '%p\\n' | xargs -r rm",
]

def respace(command, rng):
    """Adds random spaces around separators, which bash ignores."""
    def pad(match):
        return " " * rng.randint(0, 3) + match.group(1) + " " * rng.randint(0, 3)

    return re.sub(r"(&&|\|\||[|;])", pad, command)

class TestCommandNames(unittest.TestCase):
    def test_command_names_example(self):
        names = gap.command_names("sudo apt-get install -y x && ls | grep foo")
        self.assertEqual(names, {"sudo", "apt-get", "ls", "grep"})

    def test_command_names_skip_assignments_and_keywords_example(self):
        names = gap.command_names("OUT=$(get_public_ip | head -n 1) && if [ -n \"$OUT\" ]; then echo ok; fi")
        self.assertEqual(names, {"get_public_ip", "head", "echo", "["})

    def test_command_names_ignore_quoted_text_example(self):
        names = gap.command_names("printf 'Found (files) here; wow' && echo \"a | b\"")
        self.assertEqual(names, {"printf", "echo"})

    def test_command_names_ignore_heredoc_body_example(self):
        command = "cat << 'EOF' > f.py\nimport os\nprint(os.getcwd())\nEOF\npython3 f.py"
        self.assertEqual(gap.command_names(command), {"cat", "python3"})

    def test_command_names_ignore_expansions_and_comments_example(self):
        command = (
            "echo ${target_file:-x} # Debian or CentOS\n"
            "n=$(( half_range - 2 )) && (( t + 1 ))\n"
            "ls /var/log/{auth.log,secure}"
        )
        self.assertEqual(gap.command_names(command), {"echo", "ls"})

    def test_command_names_ignore_case_patterns_example(self):
        command = 'case "$u" in\n  km) bc -l ;;\n  q|Q) exit ;;\n  *) echo no ;;\nesac'
        self.assertEqual(gap.command_names(command), {"bc", "exit", "echo"})

    def test_command_names_invariant_under_spacing_invariant(self):
        rng = random.Random(0)  # noqa: S311
        for command in COMMANDS:
            for _ in range(20):
                with self.subTest(command=command):
                    self.assertEqual(gap.command_names(respace(command, rng)), gap.command_names(command))

class TestFlagChecks(unittest.TestCase):
    def test_mktemp_with_suffix_flagged_example(self):
        self.assertIn("mktemp suffix", gap.gnu_flags("F=$(mktemp /tmp/termy_XXXXXX.py)"))

    def test_mktemp_trailing_xs_not_flagged_example(self):
        self.assertNotIn("mktemp suffix", gap.gnu_flags("F=$(mktemp /tmp/termy_XXXXXX)"))

    def test_gnu_sed_in_place_flagged_example(self):
        self.assertIn("sed -i", gap.gnu_flags("sed -i 's/a/b/' file"))

    def test_bsd_sed_in_place_not_flagged_example(self):
        self.assertNotIn("sed -i", gap.gnu_flags("sed -i '' 's/a/b/' file"))

    def test_bash4_features_flagged_example(self):
        self.assertIn("declare -A", gap.bash4_features("declare -A counts; counts[x]=1"))
        self.assertIn("mapfile", gap.bash4_features("mapfile -t lines < f"))

    def test_checks_ignore_heredoc_body_invariant(self):
        for command in COMMANDS:
            with self.subTest(command=command):
                wrapped = f"cat << 'EOF' > f.txt\n{HEREDOC_BODY}EOF\n{command}"
                self.assertEqual(gap.gnu_flags(wrapped), gap.gnu_flags(command))
                self.assertEqual(gap.bash4_features(wrapped), gap.bash4_features(command))
                self.assertEqual(gap.command_names(wrapped), gap.command_names(command) | {"cat"})

class TestClassify(unittest.TestCase):
    def test_classify_example(self):
        issues = gap.classify("sudo apt-get install x && free -h && cat /proc/cpuinfo", helpers={"termy_say"})
        self.assertEqual(issues["linux-only"], {"apt-get", "free", "/proc/"})

    def test_classify_skips_builtins_and_helpers_example(self):
        issues = gap.classify("termy_say hi && echo ok && cd /tmp", helpers={"termy_say"})
        self.assertFalse(any(issues.values()))

if __name__ == "__main__":
    unittest.main()
