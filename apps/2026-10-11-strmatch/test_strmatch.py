"""test_strmatch.py -- strmatch.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

from strmatch import (all_agree, find_in_lines, kmp_search, naive_search,
                      prefix_function, rabin_karp_search)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample.txt"


class TestPrefixFunction(unittest.TestCase):
    def test_ababaca(self):
        self.assertEqual(prefix_function("ababaca"),
                         [0, 0, 1, 2, 3, 0, 1])

    def test_all_same(self):
        self.assertEqual(prefix_function("aaaaa"), [0, 1, 2, 3, 4])

    def test_abcabcd(self):
        self.assertEqual(prefix_function("abcabcd"),
                         [0, 0, 0, 1, 2, 3, 0])


class TestKmp(unittest.TestCase):
    def test_basic_match(self):
        self.assertEqual(kmp_search("ababcabcabababd", "ababd"), [10])

    def test_overlapping(self):
        self.assertEqual(kmp_search("aaaaa", "aa"), [0, 1, 2, 3])

    def test_issi(self):
        self.assertEqual(kmp_search("mississippi", "issi"), [1, 4])

    def test_no_match(self):
        self.assertEqual(kmp_search("abcdef", "xyz"), [])

    def test_pattern_longer(self):
        self.assertEqual(kmp_search("ab", "abc"), [])

    def test_empty_pattern(self):
        self.assertEqual(kmp_search("abc", ""), [])

    def test_single_char(self):
        self.assertEqual(kmp_search("banana", "a"), [1, 3, 5])


class TestAgreement(unittest.TestCase):
    def test_three_algorithms_agree(self):
        cases = [
            ("ababcabcabababd", "ababd"),
            ("aaaaa", "aa"),
            ("mississippi", "issi"),
            ("abcdef", "xyz"),
            ("pattern pattern", "pattern"),
        ]
        for text, pattern in cases:
            self.assertTrue(all_agree(text, pattern), (text, pattern))

    def test_naive_and_rk_known(self):
        self.assertEqual(naive_search("aaaaa", "aa"),
                         rabin_karp_search("aaaaa", "aa"))


class TestFileAndCli(unittest.TestCase):
    def test_find_in_lines_counts(self):
        lines = SAMPLE.read_text(encoding="utf-8").splitlines()
        hits = find_in_lines(lines, "pattern", False)
        self.assertEqual(hits[0][0], 3)
        self.assertEqual(hits[0][1], 3)

    def test_ignore_case(self):
        lines = SAMPLE.read_text(encoding="utf-8").splitlines()
        hits = find_in_lines(lines, "fox", True)
        self.assertEqual([h[0] for h in hits], [1, 5])

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "strmatch.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("AGREE", proc.stdout)

    def test_find_match(self):
        proc = self.run_cli("find", "pattern", str(SAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("matches: 3", proc.stdout)

    def test_find_no_match_exit_one(self):
        proc = self.run_cli("find", "zzzz", str(SAMPLE))
        self.assertEqual(proc.returncode, 1)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("find", "x", "no.txt")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
