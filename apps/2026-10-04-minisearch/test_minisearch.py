"""test_minisearch.py -- minisearch.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from minisearch import InvertedIndex, tokenize

APP_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = APP_DIR / "sample_docs"


class TestTokenize(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(tokenize("Hello, World!"), ["hello", "world"])
        self.assertEqual(tokenize("a1 b2"), ["a1", "b2"])

    def test_underscore_split(self):
        self.assertEqual(tokenize("hello_world"), ["hello", "world"])

    def test_stopwords(self):
        self.assertEqual(tokenize("the cat and dog", ("the", "and")),
                         ["cat", "dog"])


def build_index(**kw):
    idx = InvertedIndex(**kw)
    idx.add("d1", "the cat sat on the mat")
    idx.add("d2", "the dog ran in the park")
    idx.add("d3", "the cat and the dog play together")
    return idx


class TestIndexing(unittest.TestCase):
    def test_add_and_postings(self):
        idx = InvertedIndex()
        idx.add("x", "a b a")
        self.assertEqual(idx.doc_count, 1)
        self.assertEqual(idx.df("a"), 1)
        self.assertEqual(idx._postings["a"]["x"], 2)

    def test_duplicate_add_replaces(self):
        idx = InvertedIndex()
        idx.add("x", "a b")
        idx.add("x", "a c")
        self.assertEqual(idx.df("b"), 0)
        self.assertEqual(idx.df("a"), 1)
        self.assertNotIn("b", idx.vocabulary())

    def test_remove(self):
        idx = build_index()
        idx.remove("d2")
        self.assertEqual(idx.doc_count, 2)
        self.assertEqual(idx.df("park"), 0)
        with self.assertRaises(KeyError):
            idx.remove("missing")

    def test_vocabulary(self):
        idx = build_index()
        voc = idx.vocabulary()
        self.assertEqual(voc, sorted(voc))
        self.assertIn("cat", voc)


class TestBoolean(unittest.TestCase):
    def test_intersection(self):
        idx = build_index()
        self.assertEqual(idx.search_and("cat dog"), ["d3"])

    def test_missing_term(self):
        idx = build_index()
        self.assertEqual(idx.search_and("cat elephant"), [])

    def test_empty_query(self):
        idx = build_index()
        self.assertEqual(idx.search_and("???"), [])


class TestRanking(unittest.TestCase):
    def test_rare_term_higher_idf(self):
        idx = build_index()
        self.assertGreater(idx.idf("cat"), idx.idf("the"))

    def test_tf_boost(self):
        idx = InvertedIndex()
        idx.add("hi", "a a b")
        idx.add("lo", "a b")
        ranked = idx.search_rank("a")
        self.assertEqual([d for d, _ in ranked], ["hi", "lo"])

    def test_ranked_order_and_tiebreak(self):
        idx = build_index()
        ranked = idx.search_rank("cat")
        ids = [d for d, _ in ranked]
        self.assertEqual(ids, ["d1", "d3"])          # 同分按 id 升序
        self.assertTrue(all(s > 0 for _, s in ranked))

    def test_top_k(self):
        idx = build_index()
        self.assertEqual(len(idx.search_rank("the", top_k=2)), 2)

    def test_stopwords_in_query(self):
        idx = InvertedIndex(stopwords=("the",))
        idx.add("a", "the cat")
        idx.add("b", "the dog")
        self.assertEqual([d for d, _ in idx.search_rank("the cat")], ["a"])


class TestSerialization(unittest.TestCase):
    def test_roundtrip(self):
        idx = build_index(stopwords=("the",))
        restored = InvertedIndex.loads(idx.dumps())
        self.assertEqual(restored.doc_count, idx.doc_count)
        self.assertEqual(restored.vocabulary(), idx.vocabulary())
        self.assertEqual(restored.search_rank("cat dog"),
                         idx.search_rank("cat dog"))
        self.assertEqual(restored.stopwords, idx.stopwords)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "minisearch.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("boolean AND", proc.stdout)
        self.assertIn("d1", proc.stdout)

    def test_query_rank(self):
        proc = self.run_cli("query", "inverted index documents",
                            "--dir", str(SAMPLE_DIR))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("index", proc.stdout)

    def test_query_and(self):
        proc = self.run_cli("query", "inverted index",
                            "--dir", str(SAMPLE_DIR), "--mode", "and")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
        self.assertEqual(lines, ["index"])

    def test_empty_dir_exit_two(self):
        with tempfile.TemporaryDirectory() as d:
            proc = self.run_cli("query", "x", "--dir", d)
            self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
