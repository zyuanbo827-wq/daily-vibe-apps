"""test_graph_route.py -- graph_route.py 的单元测试（标准库 unittest）。"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from graph_route import Graph, GraphError, demo_graph, from_dict, load_graph

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample_graph.json"


class TestGraph(unittest.TestCase):
    def test_directed_vs_undirected(self):
        d = Graph(directed=True)
        d.add_edge("a", "b", 3)
        self.assertIn("b", d.adj["a"])
        self.assertNotIn("a", d.adj["b"])
        u = Graph(directed=False)
        u.add_edge("a", "b", 3)
        self.assertIn("a", u.adj["b"])

    def test_edge_listing_dedup(self):
        u = Graph(directed=False)
        u.add_edge("a", "b", 1)
        self.assertEqual(len(u.edges()), 1)


class TestDijkstra(unittest.TestCase):
    def setUp(self):
        self.g = demo_graph()

    def test_distances(self):
        dist, _ = self.g.dijkstra("A")
        expected = {"A": 0, "B": 3, "C": 2, "D": 8, "E": 10, "F": 13}
        for node, value in expected.items():
            self.assertEqual(dist[node], value, node)

    def test_path_reconstruction(self):
        dist, path = self.g.shortest("A", "F")
        self.assertEqual(dist, 13)
        self.assertEqual(path, ["A", "C", "B", "D", "E", "F"])

    def test_unknown_node(self):
        with self.assertRaises(GraphError):
            self.g.dijkstra("Z")

    def test_negative_rejected(self):
        g = Graph()
        g.add_edge("s", "a", -1)
        with self.assertRaises(GraphError):
            g.dijkstra("s")

    def test_unreachable(self):
        g = Graph(directed=True)
        g.add_edge("a", "b", 1)
        g.add_node("c")
        dist, path = g.shortest("a", "c")
        self.assertEqual(dist, float("inf"))
        self.assertEqual(path, [])


class TestBellmanFloyd(unittest.TestCase):
    def setUp(self):
        self.g = demo_graph()

    def test_bellman_agrees(self):
        d, _ = self.g.dijkstra("A")
        b, _ = self.g.bellman_ford("A")
        for node in self.g.nodes:
            self.assertEqual(d[node], b[node])

    def test_negative_edge(self):
        g = Graph(directed=True)
        g.add_edge("s", "a", 4)
        g.add_edge("s", "b", 5)
        g.add_edge("a", "b", -3)
        dist, _ = g.bellman_ford("s")
        self.assertEqual(dist["b"], 1)

    def test_negative_cycle(self):
        g = Graph(directed=True)
        g.add_edge("x", "y", 1)
        g.add_edge("y", "x", -2)
        with self.assertRaises(GraphError):
            g.bellman_ford("x")
        with self.assertRaises(GraphError):
            g.floyd_warshall()

    def test_floyd_agrees(self):
        single, _ = self.g.dijkstra("A")
        allpairs = self.g.floyd_warshall()
        for node in self.g.nodes:
            self.assertEqual(single[node], allpairs["A"][node])
        self.assertEqual(allpairs["A"]["A"], 0)


class TestJsonAndCli(unittest.TestCase):
    def test_sample_route(self):
        g = from_dict(json.loads(SAMPLE.read_text(encoding="utf-8")))
        dist, path = g.shortest("Beijing", "Nanjing")
        self.assertEqual(dist, 1030)
        self.assertEqual(path,
                         ["Beijing", "Tianjin", "Jinan", "Nanjing"])

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "graph_route.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("AGREE", proc.stdout)
        self.assertIn("detected", proc.stdout)

    def test_shortest_both_algorithms(self):
        for algo in ("dijkstra", "bellman"):
            proc = self.run_cli("shortest", str(SAMPLE),
                                "Beijing", "Nanjing",
                                "--algorithm", algo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("1030", proc.stdout)

    def test_unreachable_exit_one(self):
        g = Graph(directed=True)
        g.add_edge("a", "b", 1)
        g.add_node("c")
        import tempfile
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"directed": True,
                       "edges": [["a", "b", 1]], "nodes": ["c"]}, f)
            path = f.name
        proc = self.run_cli("shortest", path, "a", "c")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("unreachable", proc.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("shortest", "no.json", "a", "b")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
