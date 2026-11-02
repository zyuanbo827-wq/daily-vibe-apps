"""test_skiplist.py -- skiplist.py 的单元测试（标准库 unittest）。"""

import random
import subprocess
import sys
import unittest
from pathlib import Path

from skiplist import SkipList, build_from, parse_values

APP_DIR = Path(__file__).resolve().parent


class TestConstruction(unittest.TestCase):
    def test_empty(self):
        sl = SkipList()
        self.assertEqual(len(sl), 0)
        self.assertEqual(sl.to_list(), [])
        self.assertEqual(sl.level_counts(), [0])
        self.assertNotIn(1, sl)

    def test_invalid_params(self):
        with self.assertRaises(ValueError):
            SkipList(max_level=0)
        with self.assertRaises(ValueError):
            SkipList(p=1.0)

    def test_insert_basic(self):
        sl = SkipList(seed=1)
        self.assertTrue(sl.insert(3))
        self.assertTrue(sl.insert(1))
        self.assertTrue(sl.insert(2))
        self.assertEqual(sl.to_list(), [1, 2, 3])
        self.assertEqual(len(sl), 3)

    def test_duplicate_insert_ignored(self):
        sl = SkipList(seed=1)
        sl.insert(5)
        self.assertFalse(sl.insert(5))
        self.assertEqual(len(sl), 1)
        self.assertEqual(sl.to_list(), [5])

    def test_strings_supported(self):
        sl = build_from(["banana", "apple", "cherry"], seed=2)
        self.assertEqual(sl.to_list(), ["apple", "banana", "cherry"])
        self.assertIn("apple", sl)


class TestContainsAndRank(unittest.TestCase):
    def setUp(self):
        self.sl = build_from(range(100), seed=7)

    def test_contains(self):
        for i in range(100):
            self.assertIn(i, self.sl)
        for i in (100, -1, 1000):
            self.assertNotIn(i, self.sl)

    def test_rank(self):
        for i in range(100):
            self.assertEqual(self.sl.rank(i), i)
        self.assertEqual(self.sl.rank(100), -1)
        self.assertEqual(self.sl.rank(-5), -1)

    def test_level_counts_sum_invariant(self):
        counts = self.sl.level_counts()
        # 第 0 层包含全部节点；上层节点数不超过下层
        self.assertEqual(counts[0], 100)
        for upper, lower in zip(counts[1:], counts[:-1]):
            self.assertLessEqual(upper, lower)


class TestDelete(unittest.TestCase):
    def test_delete_existing(self):
        sl = build_from([1, 2, 3], seed=3)
        self.assertTrue(sl.delete(2))
        self.assertEqual(sl.to_list(), [1, 3])
        self.assertNotIn(2, sl)
        self.assertEqual(len(sl), 2)

    def test_delete_missing(self):
        sl = build_from([1, 2], seed=3)
        self.assertFalse(sl.delete(99))
        self.assertEqual(sl.to_list(), [1, 2])

    def test_delete_all(self):
        values = list(range(50))
        sl = build_from(values, seed=11)
        random.Random(4).shuffle(values)
        remaining = set(range(50))
        for v in values:
            self.assertTrue(sl.delete(v))
            remaining.remove(v)
            self.assertEqual(sl.to_list(), sorted(remaining))
        self.assertEqual(len(sl), 0)
        self.assertEqual(sl.to_list(), [])

    def test_reinsert_after_delete(self):
        sl = build_from([1, 2, 3], seed=3)
        sl.delete(2)
        sl.insert(2)
        self.assertEqual(sl.to_list(), [1, 2, 3])


class TestRange(unittest.TestCase):
    def setUp(self):
        self.sl = build_from(range(0, 100, 2), seed=5)  # 偶数 0..98

    def test_range(self):
        self.assertEqual(self.sl.range_query(10, 20), [10, 12, 14, 16, 18, 20])
        self.assertEqual(self.sl.range_query(0, 0), [0])
        self.assertEqual(self.sl.range_query(99, 200), [])
        self.assertEqual(self.sl.range_query(-10, 4), [0, 2, 4])

    def test_invalid_range(self):
        self.assertEqual(self.sl.range_query(20, 10), [])


class TestRandomized(unittest.TestCase):
    def test_mixed_ops_against_set(self):
        sl = SkipList(max_level=12, seed=123)
        oracle = set()
        rng = random.Random(99)
        for _ in range(3000):
            op = rng.random()
            value = rng.randrange(200)
            if op < 0.55:
                self.assertEqual(sl.insert(value), value not in oracle)
                oracle.add(value)
            elif op < 0.85:
                self.assertEqual(value in sl, value in oracle)
            else:
                self.assertEqual(sl.delete(value), value in oracle)
                oracle.discard(value)
            self.assertEqual(sl.to_list(), sorted(oracle))
            self.assertEqual(len(sl), len(oracle))
        self.assertEqual(sl.to_list(), sorted(oracle))


class TestHelpersAndCli(unittest.TestCase):
    def test_parse_values(self):
        self.assertEqual(parse_values("1 2 3"), [1, 2, 3])
        self.assertEqual(parse_values("a b"), ["a", "b"])

    def run_cli(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "skiplist.py"), *args],
            input=stdin, capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_cli_stdin_dump(self):
        proc = self.run_cli("--seed", "1", stdin="5 1 3 2 4")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("list: [1, 2, 3, 4, 5]", proc.stdout)
        self.assertIn("level counts:", proc.stdout)

    def test_cli_search_and_range(self):
        proc = self.run_cli("--seed", "1", "--search", "3", stdin="1 2 3 4 5")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("found", proc.stdout)
        self.assertIn("rank: 2", proc.stdout)

        proc = self.run_cli("--range", "2", "4", stdin="1 2 3 4 5")
        self.assertIn("range: [2, 3, 4]", proc.stdout)

    def test_cli_missing(self):
        proc = self.run_cli("--search", "9", stdin="1 2 3")
        self.assertIn("missing", proc.stdout)


if __name__ == "__main__":
    unittest.main()
