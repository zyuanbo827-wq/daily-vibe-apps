"""test_heaplab.py -- heaplab.py 的单元测试（标准库 unittest）。"""

import random
import subprocess
import sys
import unittest
from pathlib import Path

from heaplab import (BinaryHeap, RunningMedian, heapsort, merge_sorted,
                    running_median, top_k_largest, top_k_smallest)

APP_DIR = Path(__file__).resolve().parent


class TestBinaryHeap(unittest.TestCase):
    def test_push_pop_order(self):
        h = BinaryHeap()
        for x in [5, 1, 9, 3, 7]:
            h.push(x)
        self.assertEqual(h.peek(), 1)
        self.assertEqual([h.pop() for _ in range(5)], [1, 3, 5, 7, 9])

    def test_heapify(self):
        h = BinaryHeap.heapify([9, 4, 7, 1, 2, 8, 3, 6, 5])
        self.assertEqual(h.peek(), 1)
        out = []
        while not h.is_empty():
            out.append(h.pop())
        self.assertEqual(out, [1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_max_heap_via_key(self):
        h = BinaryHeap(key=lambda x: -x)
        for x in [5, 1, 9, 3]:
            h.push(x)
        self.assertEqual(h.peek(), 9)
        self.assertEqual([h.pop() for _ in range(4)], [9, 5, 3, 1])

    def test_key_heap_words(self):
        h = BinaryHeap.heapify(["banana", "fig", "apple", "date"], key=len)
        self.assertEqual(h.peek(), "fig")

    def test_empty_raises(self):
        h = BinaryHeap()
        self.assertTrue(h.is_empty())
        with self.assertRaises(IndexError):
            h.peek()
        with self.assertRaises(IndexError):
            h.pop()


class TestHeapsort(unittest.TestCase):
    def test_ascending(self):
        data = [5, 1, 9, 3, 7, 2, 8]
        self.assertEqual(heapsort(data), sorted(data))

    def test_descending(self):
        data = [5, 1, 9, 3, 7]
        self.assertEqual(heapsort(data, reverse=True), sorted(data, reverse=True))

    def test_empty_and_duplicates(self):
        self.assertEqual(heapsort([]), [])
        self.assertEqual(heapsort([3, 1, 3, 2, 1]), [1, 1, 2, 3, 3])

    def test_matches_builtin_random(self):
        rng = random.Random(42)
        for _ in range(20):
            data = [rng.randint(-100, 100) for _ in range(rng.randint(0, 50))]
            self.assertEqual(heapsort(data), sorted(data))


class TestTopK(unittest.TestCase):
    def test_largest(self):
        data = [5, 1, 9, 3, 7, 2, 8]
        self.assertEqual(top_k_largest(data, 3), [9, 8, 7])

    def test_smallest(self):
        data = [5, 1, 9, 3, 7, 2, 8]
        self.assertEqual(top_k_smallest(data, 3), [1, 2, 3])

    def test_k_zero(self):
        self.assertEqual(top_k_largest([1, 2], 0), [])
        self.assertEqual(top_k_smallest([1, 2], 0), [])

    def test_k_beyond_length(self):
        data = [4, 1, 3]
        self.assertEqual(top_k_largest(data, 10), [4, 3, 1])
        self.assertEqual(top_k_smallest(data, 10), [1, 3, 4])

    def test_negative_k(self):
        with self.assertRaises(ValueError):
            top_k_largest([1], -1)
        with self.assertRaises(ValueError):
            top_k_smallest([1], -1)

    def test_with_key(self):
        words = ["a", "bb", "ccc", "dddd", "ee"]
        self.assertEqual(top_k_largest(words, 2, key=len), ["dddd", "ccc"])
        self.assertEqual(top_k_smallest(words, 2, key=len), ["a", "bb"])


class TestMergeAndMedian(unittest.TestCase):
    def test_merge_sorted(self):
        streams = [[1, 4, 7], [2, 5, 8], [3, 6, 9]]
        self.assertEqual(merge_sorted(streams), list(range(1, 10)))

    def test_merge_with_empty(self):
        self.assertEqual(merge_sorted([[], [1, 3], [], [2]]), [1, 2, 3])
        self.assertEqual(merge_sorted([]), [])

    def test_running_median_known(self):
        medians = running_median([2, 1, 5, 7, 2, 0, 5])
        self.assertEqual(medians, [2, 1.5, 2, 3.5, 2, 2.0, 2.0])

    def test_empty_median(self):
        self.assertIsNone(RunningMedian().median())


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "heaplab.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("heapsort:", proc.stdout)
        self.assertIn("top 3 large: [9, 8, 7]", proc.stdout)

    def test_sort_cli(self):
        proc = self.run_cli("sort", input_text="3 1 2\n")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "1 2 3")

    def test_topk_cli(self):
        proc = self.run_cli("topk", "2", "--largest", input_text="5 1 9 3")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "9 5")

    def test_median_cli(self):
        proc = self.run_cli("median", input_text="2 1 5")
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(lines, ["2", "1.5", "2"])


if __name__ == "__main__":
    unittest.main()
