"""test_trie_autocomplete.py -- trie_autocomplete.py 的单元测试。"""

import subprocess
import sys
import unittest
from pathlib import Path

from trie_autocomplete import DEMO_WORDS, Trie, TrieError

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "search_log.tsv"


def demo_trie():
    return Trie.from_lines(DEMO_WORDS)


class TestInsertSearch(unittest.TestCase):
    def test_basic(self):
        t = Trie()
        t.insert("abc")
        self.assertTrue(t.contains("abc"))
        self.assertFalse(t.contains("ab"))
        self.assertTrue(t.startswith("ab"))
        self.assertFalse(t.startswith("abd"))
        self.assertEqual(t.size, 1)

    def test_shared_prefix(self):
        t = Trie()
        t.insert("app")
        t.insert("apple")
        self.assertEqual(t.size, 2)
        self.assertTrue(t.contains("app"))
        self.assertTrue(t.contains("apple"))

    def test_insert_accumulates_freq(self):
        t = Trie()
        t.insert("x", 2)
        t.insert("x", 3)
        self.assertEqual(t.size, 1)
        self.assertEqual(t._find("x").freq, 5)

    def test_node_count(self):
        t = Trie()
        t.insert("a")
        t.insert("ab")
        self.assertEqual(t.node_count, 3)

    def test_bad_insert(self):
        t = Trie()
        with self.assertRaises(TrieError):
            t.insert("")
        with self.assertRaises(TrieError):
            t.insert("q", -1)


class TestComplete(unittest.TestCase):
    def setUp(self):
        self.t = demo_trie()

    def test_ranking_by_freq(self):
        rows = self.t.complete("ap", 3)
        self.assertEqual([w for w, _ in rows],
                         ["apple", "app", "application"])

    def test_ca_branch(self):
        rows = self.t.complete("ca", 5)
        self.assertEqual([w for w, _ in rows],
                         ["cat", "car", "card", "care", "carry"])

    def test_missing_prefix(self):
        self.assertEqual(self.t.complete("zzz"), [])

    def test_empty_prefix_returns_all(self):
        rows = self.t.complete("", 100)
        self.assertEqual(len(rows), self.t.size)
        self.assertEqual(rows[0][0], "apple")     # 全局最高频

    def test_tie_lexical(self):
        t = Trie()
        t.insert("b", 5)
        t.insert("a", 5)
        self.assertEqual([w for w, _ in t.complete("")], ["a", "b"])


class TestWildcard(unittest.TestCase):
    def setUp(self):
        self.t = demo_trie()

    def test_three_char_ending_t(self):
        self.assertEqual(self.t.wildcard("..t"), ["cat", "dot"])

    def test_c_any_r(self):
        self.assertEqual(self.t.wildcard("c.r"), ["car"])

    def test_no_match(self):
        self.assertEqual(self.t.wildcard("............"), [])

    def test_trailing_wildcard(self):
        self.assertEqual(sorted(self.t.wildcard("do.")), ["dog", "dot"])


class TestDelete(unittest.TestCase):
    def test_delete_keeps_shared_words(self):
        t = demo_trie()
        self.assertTrue(t.delete("apple"))
        self.assertFalse(t.contains("apple"))
        self.assertTrue(t.contains("app"))
        self.assertTrue(t.contains("application"))

    def test_delete_missing(self):
        t = demo_trie()
        self.assertFalse(t.delete("nope"))

    def test_delete_all_prunes_to_root(self):
        t = demo_trie()
        for line in DEMO_WORDS:
            word = line.split("\t")[0]
            self.assertTrue(t.delete(word))
        self.assertEqual(t.size, 0)
        self.assertEqual(t.node_count, 1)


class TestSerialization(unittest.TestCase):
    def test_roundtrip(self):
        t = demo_trie()
        again = Trie.from_lines(t.to_lines())
        self.assertEqual(sorted(t.to_lines()), sorted(again.to_lines()))
        self.assertEqual(t.size, again.size)

    def test_comments_and_plain_lines(self):
        t = Trie.from_lines(["# c", "", "hello", "world\t4"])
        self.assertEqual(t.size, 2)
        self.assertEqual(t._find("world").freq, 4)

    def test_bad_freq(self):
        with self.assertRaises(TrieError):
            Trie.from_lines(["word\tx"])


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "trie_autocomplete.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_complete_file(self):
        proc = self.run_cli("complete", str(SAMPLE), "--prefix", "ap",
                            "--limit", "3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("apple", proc.stdout)
        self.assertEqual(len(proc.stdout.splitlines()), 3)

    def test_wildcard_cli(self):
        proc = self.run_cli("wildcard", str(SAMPLE), "--pattern", "..t")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.split(), ["cat", "dot"])

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("词表", proc.stdout)

    def test_repl(self):
        proc = self.run_cli("repl", str(SAMPLE),
                            input_text="c ap\nw c.r\ns cat\ns nope\nq\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("yes", proc.stdout)
        self.assertIn("no", proc.stdout)

    def test_stdin(self):
        proc = self.run_cli("complete", "-", "--prefix", "a",
                            input_text="alpha\t9\nbeta\t3\n")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("alpha", proc.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("complete", "no-such.tsv")
        self.assertEqual(proc.returncode, 2)

    def test_bad_freq_exit_one(self):
        bad = APP_DIR / "_bad.tsv"
        bad.write_text("word\tx\n", encoding="utf-8")
        proc = self.run_cli("complete", str(bad))
        bad.unlink()
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
