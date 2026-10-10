"""test_union_find.py -- union_find.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

from union_find import (UnionFind, analyze, kruskal, parse_edges,
                        total_weight)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample_edges.txt"


class TestUnionFind(unittest.TestCase):
    def test_initial_state(self):
        uf = UnionFind(range(4))
        self.assertEqual(uf.components, 4)
        self.assertEqual(uf.size(0), 1)

    def test_union_basic(self):
        uf = UnionFind(range(4))
        self.assertTrue(uf.union(0, 1))
        self.assertEqual(uf.components, 3)
        self.assertEqual(uf.size(0), 2)
        self.assertTrue(uf.connected(0, 1))

    def test_union_idempotent(self):
        uf = UnionFind(range(3))
        uf.union(0, 1)
        self.assertFalse(uf.union(1, 0))
        self.assertEqual(uf.components, 2)

    def test_transitive_connected(self):
        uf = UnionFind(range(5))
        uf.union(0, 1)
        uf.union(1, 2)
        uf.union(2, 3)
        self.assertTrue(uf.connected(0, 3))
        self.assertFalse(uf.connected(0, 4))

    def test_unknown_raises(self):
        uf = UnionFind([1])
        with self.assertRaises(KeyError):
            uf.find(9)

    def test_path_compression(self):
        uf = UnionFind(range(4))
        uf.union(0, 1)
        uf.union(2, 3)
        uf.union(1, 3)
        root = uf.find(0)
        uf.find(2)
        self.assertEqual(uf.parent[2], root)
        self.assertEqual(uf.parent[0], root)

    def test_weighted_attach(self):
        uf = UnionFind(range(5))
        uf.union(0, 1)
        uf.union(0, 2)   # {0,1,2} size 3
        uf.union(3, 4)   # {3,4} size 2
        uf.union(4, 2)   # small attaches under big
        self.assertEqual(uf.weight[uf.find(0)], 5)
        self.assertEqual(uf.components, 1)


class TestGraphAnalysis(unittest.TestCase):
    def test_sample_connected_with_cycle(self):
        edges, nodes = parse_edges(SAMPLE.read_text(encoding="utf-8").splitlines())
        comps, cycle = analyze(edges, nodes)
        self.assertEqual(comps, 1)
        self.assertTrue(cycle)

    def test_disconnected_forest(self):
        edges, nodes = parse_edges(["a b 1", "c d 2"])
        comps, cycle = analyze(edges, nodes)
        self.assertEqual(comps, 2)
        self.assertFalse(cycle)

    def test_triangle_cycle(self):
        edges, nodes = parse_edges(["a b 1", "b c 1", "c a 1"])
        _, cycle = analyze(edges, nodes)
        self.assertTrue(cycle)

    def test_kruskal_sample(self):
        edges, nodes = parse_edges(SAMPLE.read_text(encoding="utf-8").splitlines())
        mst = kruskal(edges, nodes)
        self.assertEqual(len(mst), len(nodes) - 1)
        self.assertEqual(total_weight(mst), 1330)

    def test_kruskal_forest(self):
        edges, nodes = parse_edges(["a b 3", "a c 1", "d e 2"])
        mst = kruskal(edges, nodes)
        comps, _ = analyze(edges, nodes)
        self.assertEqual(len(mst), len(nodes) - comps)
        self.assertEqual(total_weight(mst), 1 + 3 + 2)


class TestParseAndCli(unittest.TestCase):
    def test_parse_comments_and_default_weight(self):
        edges, nodes = parse_edges(["# comment", "", "a b", "b c 5"])
        self.assertEqual(len(edges), 2)
        self.assertEqual(edges[0][2], 1.0)
        self.assertEqual(nodes, ["a", "b", "c"])

    def test_malformed_raises(self):
        with self.assertRaises(ValueError):
            parse_edges(["a b c d"])

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "union_find.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("detected", proc.stdout)
        self.assertIn("1330", proc.stdout)

    def test_analyze_mst(self):
        proc = self.run_cli("analyze", str(SAMPLE), "--mst")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("components: 1", proc.stdout)
        self.assertIn("1330", proc.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("analyze", "no.txt")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
