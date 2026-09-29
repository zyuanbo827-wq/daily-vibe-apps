"""test_consistent_hash.py -- consistent_hash.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

from consistent_hash import (
    ConsistentHash, RingError, distribution_table, make_ring, md5_hash,
)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample_keys.txt"
KEYS = [f"key-{i}" for i in range(2000)]


def fnv1a(text: str) -> int:
    h = 2166136261
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


class TestRingBasics(unittest.TestCase):
    def test_empty_ring(self):
        ring = ConsistentHash()
        self.assertIsNone(ring.get_node("x"))
        self.assertEqual(ring.nodes, [])

    def test_invalid_replicas(self):
        with self.assertRaises(RingError):
            ConsistentHash(replicas=0)

    def test_add_remove_ring_size(self):
        ring = ConsistentHash(replicas=50)
        ring.add_node("A")
        ring.add_node("B")
        self.assertEqual(ring.ring_size(), 100)
        self.assertEqual(ring.nodes, ["A", "B"])
        ring.remove_node("A")
        self.assertEqual(ring.ring_size(), 50)
        self.assertEqual(ring.nodes, ["B"])

    def test_duplicate_and_missing(self):
        ring = ConsistentHash(replicas=10)
        ring.add_node("A")
        with self.assertRaises(RingError):
            ring.add_node("A")
        with self.assertRaises(RingError):
            ring.remove_node("X")

    def test_single_node_owns_all(self):
        ring = make_ring(["only"], replicas=20)
        for k in KEYS[:50]:
            self.assertEqual(ring.get_node(k), "only")

    def test_deterministic(self):
        r1 = make_ring(["A", "B", "C"], replicas=100)
        r2 = make_ring(["A", "B", "C"], replicas=100)
        for k in KEYS[:100]:
            self.assertEqual(r1.get_node(k), r2.get_node(k))

    def test_custom_hash_func(self):
        ring = make_ring(["A", "B"], replicas=8, hash_func=fnv1a)
        self.assertEqual(ring.ring_size(), 16)
        owners = {ring.get_node(k) for k in KEYS}
        self.assertTrue(owners.issubset({"A", "B"}))


class TestAssignmentAndDistribution(unittest.TestCase):
    def setUp(self):
        self.ring = make_ring(["A", "B", "C", "D"], replicas=120)

    def test_every_key_assigned_once(self):
        assigned = self.ring.assign(KEYS)
        total = sum(len(v) for v in assigned.values())
        self.assertEqual(total, len(KEYS))
        flat = [k for v in assigned.values() for k in v]
        self.assertEqual(sorted(flat), sorted(KEYS))

    def test_distribution_counts_sum(self):
        table = distribution_table(self.ring, KEYS)
        self.assertEqual(sum(row[1] for row in table), len(KEYS))
        self.assertAlmostEqual(sum(row[2] for row in table), 100.0, places=1)

    def test_reasonable_balance(self):
        # 120 虚拟节点下，每节点占比应落在 10%~40%
        table = distribution_table(self.ring, KEYS)
        for _, _, pct in table:
            self.assertGreater(pct, 10.0)
            self.assertLess(pct, 40.0)


class TestMonotonicity(unittest.TestCase):
    def test_add_node_monotonic(self):
        ring = make_ring(["A", "B", "C"], replicas=120)
        before = {k: ring.get_node(k) for k in KEYS}
        moved, _ = ring.plan_add_node("D", KEYS)
        for key, old, new in moved:
            self.assertEqual(before[key], old)
            self.assertEqual(new, "D")          # 只迁入新节点
        for key, old in before.items():
            new = ring.get_node(key)
            self.assertTrue(new == old or new == "D")
        # 老节点之间不发生迁移
        self.assertTrue(all(new == "D" for _, _, new in moved))

    def test_remove_node_local_effect(self):
        ring = make_ring(["A", "B", "C"], replicas=120)
        before = {k: ring.get_node(k) for k in KEYS}
        moved, _ = ring.plan_remove_node("B", KEYS)
        affected = {k for k, _, _ in moved}
        self.assertEqual(affected, {k for k, n in before.items() if n == "B"})
        for key, old, new in moved:
            self.assertEqual(old, "B")
            self.assertIn(new, ["A", "C"])
        for key, old in before.items():
            if old != "B":
                self.assertEqual(ring.get_node(key), old)

    def test_add_then_remove_restores(self):
        ring = make_ring(["A", "B", "C"], replicas=120)
        snapshot = {k: ring.get_node(k) for k in KEYS}
        ring.plan_add_node("D", KEYS)
        ring.remove_node("D")
        restored = {k: ring.get_node(k) for k in KEYS}
        self.assertEqual(snapshot, restored)

    def test_plan_matches_ring_state(self):
        ring = make_ring(["A", "B"], replicas=80)
        _, assignment = ring.plan_add_node("C", KEYS)
        for node, node_keys in assignment.items():
            for key in node_keys:
                self.assertEqual(ring.get_node(key), node)


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "consistent_hash.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_demo(self):
        proc = self.run_cli("demo", "--keys", "3000")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("初始三节点分布", proc.stdout)
        self.assertIn("node-D", proc.stdout)
        self.assertIn("下线 node-B", proc.stdout)
        self.assertIn("接收", proc.stdout)
        # 加节点时老节点间迁移必须为 0
        line = [ln for ln in proc.stdout.splitlines() if "其余节点间迁移" in ln][0]
        self.assertIn("迁移 0 个", line)

    def test_dist_sample(self):
        proc = self.run_cli("dist", str(SAMPLE),
                            "--nodes", "cache-1,cache-2,cache-3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("cache-1", proc.stdout)
        self.assertIn("20 个", proc.stdout)
        self.assertIn("%", proc.stdout)

    def test_dist_stdin(self):
        proc = self.run_cli("dist", "-", "--nodes", "x,y",
                            input_text="a\nb\nc\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("3 个", proc.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("dist", "no-such.txt", "--nodes", "a,b")
        self.assertEqual(proc.returncode, 2)

    def test_bad_replicas_exit_one(self):
        proc = self.run_cli("dist", str(SAMPLE), "--nodes", "a,b",
                            "--replicas", "0")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
