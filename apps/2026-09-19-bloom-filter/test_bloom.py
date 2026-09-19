"""test_bloom.py -- bloom.py 的单元测试（标准库 unittest）。"""

import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import bloom
from bloom import BloomFilter, BloomError, fnv1a_64, optimal_bits, optimal_hashes

APP_DIR = Path(__file__).resolve().parent


class TestParameters(unittest.TestCase):
    def test_optimal_bits_classic_values(self):
        # 教科书结果：n=10000, p=0.01 -> m≈95851 bit, k=7
        m = optimal_bits(10000, 0.01)
        self.assertGreater(m, 95_000)
        self.assertLess(m, 97_000)
        self.assertEqual(optimal_hashes(m, 10000), 7)

    def test_smaller_fpp_needs_more_bits(self):
        self.assertGreater(optimal_bits(1000, 0.001), optimal_bits(1000, 0.05))

    def test_more_items_need_more_bits(self):
        self.assertGreater(optimal_bits(10000, 0.01), optimal_bits(100, 0.01))

    def test_invalid_params(self):
        with self.assertRaises(BloomError):
            BloomFilter(0)
        with self.assertRaises(BloomError):
            BloomFilter(100, 0.0)
        with self.assertRaises(BloomError):
            BloomFilter(100, 1.0)

    def test_hashes_at_least_one(self):
        bf = BloomFilter(1, 0.99)
        self.assertGreaterEqual(bf.k, 1)


class TestHash(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(fnv1a_64(b"abc"), fnv1a_64(b"abc"))

    def test_seed_changes_hash(self):
        self.assertNotEqual(fnv1a_64(b"abc", 0), fnv1a_64(b"abc", 123))

    def test_str_and_bytes_equivalent(self):
        self.assertEqual(fnv1a_64("abc".encode("utf-8")), fnv1a_64(b"abc"))

    def test_indices_in_range(self):
        bf = BloomFilter(100, 0.01)
        for idx in bf._indices("hello"):
            self.assertGreaterEqual(idx, 0)
            self.assertLess(idx, bf.m)
        self.assertEqual(len(list(bf._indices("hello"))), bf.k)

    def test_bad_item_type(self):
        bf = BloomFilter(10)
        with self.assertRaises(BloomError):
            123 in bf


class TestMembership(unittest.TestCase):
    def test_no_false_negatives(self):
        bf = BloomFilter(1000, 0.01)
        items = [f"item-{i}" for i in range(1000)]
        bf.add_many(items)
        for item in items:
            self.assertIn(item, bf)

    def test_bytes_items(self):
        bf = BloomFilter(100)
        bf.add(b"\x00\x01\x02")
        self.assertIn(b"\x00\x01\x02", bf)
        self.assertNotIn(b"\x00\x01\x03", bf)

    def test_empty_filter_denies_all(self):
        bf = BloomFilter(100)
        self.assertNotIn("anything", bf)
        self.assertEqual(bf.estimated_fpp(), 0.0)
        self.assertEqual(bf.bits_set(), 0)

    def test_duplicate_add_is_idempotent(self):
        bf = BloomFilter(100)
        bf.add("x")
        once = bf.bits_set()
        bf.add("x")
        self.assertEqual(bf.bits_set(), once)
        self.assertEqual(bf.count, 2)

    def test_empirical_false_positive_rate(self):
        # 确定性大样本探测：实测假阳性率应远低于宽松上界 5%
        bf = BloomFilter(2000, 0.01)
        bf.add_many(f"word-{i}" for i in range(2000))
        false_hits = sum(f"probe-{i}" in bf for i in range(20_000))
        rate = false_hits / 20_000
        self.assertLess(rate, 0.05, f"实测假阳性率 {rate:.3%} 超出预期")

    def test_estimated_fpp_near_target_at_capacity(self):
        bf = BloomFilter(10_000, 0.01)
        bf.add_many(f"w-{i}" for i in range(10_000))
        self.assertAlmostEqual(bf.estimated_fpp(), 0.01, delta=0.005)

    def test_fpp_grows_with_load(self):
        bf = BloomFilter(1000, 0.01)
        bf.add_many(f"a-{i}" for i in range(100))
        low = bf.estimated_fpp()
        bf.add_many(f"b-{i}" for i in range(900))
        self.assertGreater(bf.estimated_fpp(), low)


class TestSetOperations(unittest.TestCase):
    def test_union(self):
        a, b = BloomFilter(100), BloomFilter(100)
        a.add("alpha")
        b.add("beta")
        u = a.union(b)
        self.assertIn("alpha", u)
        self.assertIn("beta", u)

    def test_intersection(self):
        a, b = BloomFilter(100), BloomFilter(100)
        a.add_many(["common", "only-a"])
        b.add_many(["common", "only-b"])
        inter = a.intersection(b)
        self.assertIn("common", inter)
        self.assertLessEqual(inter.bits_set(), a.bits_set())
        self.assertLessEqual(inter.bits_set(), b.bits_set())

    def test_incompatible_raises(self):
        a = BloomFilter(100, 0.01)
        b = BloomFilter(1000, 0.01)
        with self.assertRaises(BloomError):
            a.union(b)
        with self.assertRaises(BloomError):
            a.intersection(b)

    def test_operation_with_non_filter_raises(self):
        a = BloomFilter(100)
        with self.assertRaises(BloomError):
            a.union(object())


class TestSerialization(unittest.TestCase):
    def test_roundtrip_bytes(self):
        bf = BloomFilter(500, 0.02)
        bf.add_many(["one", "two", "three"])
        raw = bf.to_bytes()
        restored = BloomFilter.from_bytes(raw)
        self.assertEqual((restored.m, restored.k, restored.count),
                         (bf.m, bf.k, bf.count))
        self.assertEqual(restored.to_bytes(), raw)
        for item in ("one", "two", "three"):
            self.assertIn(item, restored)

    def test_save_load_file(self):
        bf = BloomFilter(100)
        bf.add("persisted")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.bloom")
            bf.save(path)
            loaded = BloomFilter.load(path)
            self.assertIn("persisted", loaded)

    def test_corrupt_data_rejected(self):
        with self.assertRaises(BloomError):
            BloomFilter.from_bytes(b"short")
        with self.assertRaises(BloomError):
            BloomFilter.from_bytes(b"XXXX" + b"\x00" * 30)
        good = BloomFilter(10).to_bytes()
        with self.assertRaises(BloomError):
            BloomFilter.from_bytes(good[:-1])  # 截断位图


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "bloom.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_build_info_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "words.bloom")
            build = self.run_cli("build", str(APP_DIR / "sample_words.txt"),
                                 "-o", db, "--fpp", "0.01")
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertIn("items=41", build.stdout)
            self.assertIn("k=7", build.stdout)

            info = self.run_cli("info", db)
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertIn("哈希个数", info.stdout)

            hit = self.run_cli("query", db, "apple", "zebra")
            self.assertEqual(hit.returncode, 0, hit.stderr)
            self.assertIn("可能存在", hit.stdout)

            miss = self.run_cli("query", db, "definitely-not-a-word-xyz")
            self.assertEqual(miss.returncode, 1)
            self.assertIn("一定不存在", miss.stdout)

    def test_build_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "stdin.bloom")
            proc = subprocess.run(
                [sys.executable, str(APP_DIR / "bloom.py"), "build", "-", "-o", db],
                input="alpha\nbeta\n", capture_output=True, text=True,
                timeout=60, cwd=APP_DIR,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("items=2", proc.stdout)


if __name__ == "__main__":
    unittest.main()
