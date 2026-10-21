"""test_btree.py -- btree.py 的单元测试（标准库 unittest）。"""

import random
import subprocess
import sys
import unittest
from pathlib import Path

from btree import BTree

APP_DIR = Path(__file__).resolve().parent


def fill(n: int, t: int = 2, seed: int = 0) -> BTree:
    rng = random.Random(seed)
    keys = list(range(n))
    rng.shuffle(keys)
    tree = BTree(t=t)
    for k in keys:
        tree.insert(k)
    return tree


class TestInsert(unittest.TestCase):
    def test_basic_search(self):
        tree = BTree(t=2)
        for k in [10, 20, 5, 6, 12]:
            tree.insert(k)
        self.assertTrue(tree.contains(10))
        self.assertTrue(tree.contains(5))
        self.assertFalse(tree.contains(99))
        self.assertFalse(tree.contains(1))

    def test_root_split_height(self):
        tree = BTree(t=2)
        for k in [1, 2, 3]:
            tree.insert(k)
        self.assertEqual(tree.height(), 1)
        tree.insert(4)  # 触发根分裂
        self.assertEqual(tree.height(), 2)
        self.assertEqual(tree.inorder(), [1, 2, 3, 4])

    def test_many_inserts(self):
        for n in (10, 50, 200):
            tree = fill(n, seed=n)
            for k in range(n):
                self.assertTrue(tree.contains(k))
            self.assertEqual(tree.inorder(), list(range(n)))

    def test_duplicate_insert_ignored(self):
        tree = BTree(t=2)
        for _ in range(3):
            tree.insert(7)
        self.assertEqual(tree.inorder(), [7])

    def test_degree_three(self):
        tree = fill(100, t=3, seed=5)
        self.assertEqual(tree.inorder(), list(range(100)))
        self.assertLess(tree.height(), fill(100, t=2, seed=5).height())

    def test_invalid_degree(self):
        with self.assertRaises(ValueError):
            BTree(t=1)


class TestDelete(unittest.TestCase):
    def test_delete_leaf(self):
        tree = fill(20, seed=1)
        self.assertTrue(tree.delete(5))
        self.assertFalse(tree.contains(5))
        self.assertEqual(tree.inorder(), [k for k in range(20) if k != 5])

    def test_delete_missing(self):
        tree = fill(20, seed=1)
        self.assertFalse(tree.delete(999))

    def test_delete_all_sequentially(self):
        tree = fill(60, seed=7)
        rng = random.Random(11)
        keys = list(range(60))
        rng.shuffle(keys)
        remaining = set(keys)
        for k in keys:
            self.assertTrue(tree.delete(k))
            remaining.discard(k)
            self.assertEqual(tree.inorder(), sorted(remaining))
        self.assertEqual(tree.inorder(), [])

    def test_delete_height_decreases(self):
        tree = fill(40, t=2, seed=3)
        h0 = tree.height()
        for k in range(40):
            tree.delete(k)
        self.assertLessEqual(tree.height(), h0)
        self.assertEqual(tree.height(), 1)

    def test_random_mixed_operations(self):
        rng = random.Random(2026)
        tree = BTree(t=2)
        reference = set()
        for _ in range(3000):
            op = rng.random()
            k = rng.randint(0, 99)
            if op < 0.6:
                tree.insert(k)
                reference.add(k)
            else:
                tree.delete(k)
                reference.discard(k)
        self.assertEqual(tree.inorder(), sorted(reference))


class TestRange(unittest.TestCase):
    def test_range_query(self):
        tree = fill(50, seed=9)
        self.assertEqual(tree.range_query(10, 20), list(range(10, 21)))
        self.assertEqual(tree.range_query(0, 0), [0])
        self.assertEqual(tree.range_query(60, 100), [])
        self.assertEqual(tree.range_query(-5, 50), list(range(50)))


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "btree.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("inorder:", proc.stdout)
        self.assertIn("range [6,20]:", proc.stdout)

    def test_build_search(self):
        proc = self.run_cli("build", "--search", "7", "--dump",
                            input_text="3 1 4 1 5 9 2 6 7")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("contains 7: True", proc.stdout)
        self.assertIn("loaded 8 keys", proc.stdout)


if __name__ == "__main__":
    unittest.main()
