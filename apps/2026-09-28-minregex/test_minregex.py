"""test_minregex.py -- minregex.py 的单元测试（标准库 unittest）。

核心策略：对一批覆盖各特性的模式/文本，与标准库 re 的结果逐项比对
（search 位置、分组跨度、findall），保证语义一致。
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

import minregex
from minregex import Match, Pattern, RegexError, search

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample.txt"


# (pattern, text) —— 仅使用引擎支持的特性
CROSS_CASES = [
    ("abc", "xabcabcy"),
    ("a.c", "abc\naxc"),
    ("[0-9]+", "a12b345"),
    (r"\d{3}-\d{4}", "555-1234x"),
    (r"\w+@\w+\.\w+", "alice@example.com bob@x"),
    ("(cat|dog)s?", "cats and dog and fish"),
    ("a+?", "aaa"),
    (r"(?:ab)+", "ababx"),
    (r"\s+", "a b  c"),
    ("[^0-9]+", "a1b2"),
    ("colou?r", "color colour"),
    ("a{2,3}", "aaaaa"),
    ("ab|cd", "cdx"),
    (r"\D+", "12abc9"),
    (r"\W+", "ab---cd"),
    (r"\S+", "a  bb"),
    (r"(\w+):", "a: b: c"),
    ("<.*>", "<a><b>"),
    ("<.*?>", "<a><b>"),
    ("[A-Za-z_][A-Za-z0-9_]*", "var x1 = 2"),
    (r"a{2}", "aaaa"),
    (r"a{2,}", "aaaaa"),
    ("q[^x]*q", "qabcq"),
    ("https?://", "see https://x and http://y"),
]


class TestCrossValidateSearch(unittest.TestCase):
    def test_search_spans_match_re(self):
        for pat, text in CROSS_CASES:
            mine = Pattern(pat).search(text)
            ref = re.search(pat, text)
            self.assertIsNotNone(mine, msg=pat)
            self.assertIsNotNone(ref, msg=pat)
            self.assertEqual(mine.span(), ref.span(),
                             msg=f"{pat!r} on {text!r}")
            self.assertEqual(mine.group(0), ref.group(0), msg=pat)

    def test_findall_matches_re(self):
        for pat, text in CROSS_CASES:
            self.assertEqual(Pattern(pat).findall(text),
                             re.findall(pat, text),
                             msg=f"{pat!r} on {text!r}")

    def test_no_match(self):
        self.assertIsNone(Pattern("z+").search("abc"))
        self.assertEqual(Pattern("z+").findall("abc"), [])


class TestGroups(unittest.TestCase):
    def test_named_date_groups(self):
        pat = r"(\d{4})-(\d{2})-(\d{2})"
        text = "on 2026-09-28 today"
        mine = Pattern(pat).search(text)
        ref = re.search(pat, text)
        self.assertEqual(mine.span(), ref.span())
        for g in range(1, 4):
            self.assertEqual(mine.span(g), ref.span(g), msg=g)
            self.assertEqual(mine.group(g), ref.group(g))
        self.assertEqual(mine.groups(), ref.groups())

    def test_nested_groups(self):
        pat = "((a)(b))"
        mine = Pattern(pat).search("ab")
        ref = re.search(pat, "ab")
        for g in range(4):
            self.assertEqual(mine.span(g), ref.span(g), msg=g)

    def test_quantified_group_captures_last(self):
        pat = r"(\d)+"
        mine = Pattern(pat).search("123")
        ref = re.search(pat, "123")
        self.assertEqual(mine.span(1), ref.span(1))  # 最后一次迭代

    def test_non_capturing_not_counted(self):
        p = Pattern("(?:ab)(c)")
        self.assertEqual(p.ngroups, 1)
        m = p.search("abc")
        self.assertEqual(m.group(1), "c")


class TestAnchorsAndModes(unittest.TestCase):
    def test_caret_and_dollar(self):
        self.assertIsNotNone(Pattern("^$").search(""))
        self.assertIsNone(Pattern("^hello").search("oh hello"))
        m = Pattern("hello$").search("oh hello")
        self.assertEqual(m.span(), (3, 8))

    def test_match_and_fullmatch(self):
        p = Pattern(r"\d+")
        self.assertEqual(p.match("12a").span(), (0, 2))
        self.assertIsNotNone(p.fullmatch("123"))
        self.assertIsNone(p.fullmatch("12a"))

    def test_dot_excludes_newline(self):
        self.assertIsNone(Pattern("a.b").search("a\nb"))


class TestLazyQuantifiers(unittest.TestCase):
    def test_lazy_alternatives(self):
        self.assertEqual(Pattern("a+?").search("aaa").span(), (0, 1))
        self.assertEqual(Pattern("a??").search("aaa").span(), (0, 0))
        m = Pattern("<.*?>").search("<a><b>")
        self.assertEqual(m.group(0), "<a>")
        m2 = Pattern("<.*?>").search("<a><b>")
        self.assertEqual(m2.span(), (0, 3))

    def test_lazy_findall(self):
        pat = "<.*?>"
        self.assertEqual(Pattern(pat).findall("<a><b>"),
                         re.findall(pat, "<a><b>"))


class TestCharacterClasses(unittest.TestCase):
    def test_ranges_and_negate(self):
        self.assertEqual(Pattern("[a-c]+").findall("abcdc"),
                         ["abc", "c"])
        self.assertEqual(Pattern("[^a-c]+").findall("abcdc"),
                         ["d"])

    def test_builtin_classes(self):
        self.assertEqual(Pattern(r"\d+").findall("a12b3"), ["12", "3"])
        self.assertEqual(Pattern(r"\w+").findall("a b_c"),
                         ["a", "b_c"])
        self.assertEqual(Pattern(r"\s").findall("a b\tc"),
                         [" ", "\t"])

    def test_class_with_dash_at_edge(self):
        self.assertIsNotNone(Pattern("[-a]").search("-"))
        self.assertIsNotNone(Pattern("[a-]").search("-"))


class TestPatternErrors(unittest.TestCase):
    def test_bad_patterns(self):
        for bad in ["(", ")", "*abc", "a{2,1}", "a|", "(?", "[a",
                    "a\\", r"\q"]:
            with self.assertRaises(RegexError, msg=bad):
                Pattern(bad)


class TestFinditer(unittest.TestCase):
    def test_overlapping_zero_width(self):
        pat = r"a?"
        spans = [m.span() for m in Pattern(pat).finditer("aa")]
        self.assertEqual(spans, [(0, 1), (1, 2), (2, 2)])

    def test_finditer_advances(self):
        text = "12 and 34"
        pat = r"\d+"
        self.assertEqual([m.group(0) for m in Pattern(pat).finditer(text)],
                         ["12", "34"])


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "minregex.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_grep_file(self):
        pat = r"\w+@\w+\.\w+"
        proc = self.run_cli("grep", pat, str(SAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("alice", lines[0])

    def test_grep_no_match_exit_one(self):
        proc = self.run_cli("grep", "zzz", str(SAMPLE))
        self.assertEqual(proc.returncode, 1)

    def test_find_command(self):
        proc = self.run_cli("find", r"\d{4}-\d{2}-\d{2}", str(SAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1995-03-12", proc.stdout)
        self.assertIn("共 2 处匹配", proc.stdout)

    def test_grep_stdin(self):
        proc = self.run_cli("grep", "foo", "-",
                            input_text="foo bar\nbaz\nfoo2\n")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(proc.stdout.splitlines()), 2)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("grep", "x", "no-such.txt")
        self.assertEqual(proc.returncode, 2)

    def test_bad_pattern_exit_one(self):
        proc = self.run_cli("grep", "(", str(SAMPLE))
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
