"""test_astar.py -- astar.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

from astar import (Grid, astar, chebyshev, dijkstra, manhattan, parse_grid,
                    path_cost, render)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample_grid.txt"


class TestHeuristics(unittest.TestCase):
    def test_manhattan(self):
        self.assertEqual(manhattan((0, 0), (2, 3)), 5)

    def test_chebyshev(self):
        self.assertEqual(chebyshev((0, 0), (2, 3)), 3)


class TestSearch(unittest.TestCase):
    def test_open_grid_four_dir(self):
        g = Grid(5, 5)
        path, _ = astar(g, (0, 0), (4, 4))
        self.assertEqual(len(path), 9)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (4, 4))

    def test_open_grid_eight_dir(self):
        g = Grid(5, 5)
        path, _ = astar(g, (0, 0), (4, 4), diagonal=True)
        self.assertEqual(len(path), 5)

    def test_start_equals_goal(self):
        g = Grid(3, 3)
        path, _ = astar(g, (1, 1), (1, 1))
        self.assertEqual(path, [(1, 1)])

    def test_obstacle_detour(self):
        grid, start, goal = parse_grid(
            SAMPLE.read_text(encoding="utf-8").splitlines())
        path, _ = astar(grid, start, goal)
        self.assertEqual(len(path), 9)

    def test_unreachable(self):
        g = Grid(3, 3, {(1, 1), (1, 2), (2, 1)})
        path, expanded = astar(g, (0, 0), (2, 2))
        self.assertIsNone(path)
        self.assertGreater(expanded, 0)

    def test_blocked_endpoint_raises(self):
        g = Grid(3, 3, {(0, 0)})
        with self.assertRaises(ValueError):
            astar(g, (0, 0), (2, 2))

    def test_astar_matches_dijkstra(self):
        layout = [
            "S...#....", ".#..#..#.", ".#..#..#.",
            ".#.....#.", ".####..#.", ".....#..G",
        ]
        grid, start, goal = parse_grid(layout)
        pa, ea = astar(grid, start, goal)
        pd, ed = dijkstra(grid, start, goal)
        self.assertIsNotNone(pa)
        self.assertEqual(len(pa), len(pd))
        self.assertLessEqual(ea, ed)

    def test_diagonal_corner_cutting_blocked(self):
        g = Grid(3, 3, {(0, 1)})
        path, _ = astar(g, (0, 0), (1, 1), diagonal=True)
        self.assertEqual(len(path), 3)
        self.assertEqual(path[1], (1, 0))

    def test_diagonal_path_cost(self):
        g = Grid(5, 5)
        path, _ = astar(g, (0, 0), (4, 4), diagonal=True)
        self.assertAlmostEqual(path_cost(g, path, True),
                               4 * 1.4142135623730951)


class TestRenderAndCli(unittest.TestCase):
    def test_render_marks(self):
        g = Grid(3, 3)
        path = [(0, 0), (0, 1), (0, 2)]
        out = render(g, path, (0, 0), (0, 2))
        self.assertIn("S", out.splitlines()[0])
        self.assertIn("*", out)
        self.assertIn("G", out)

    def test_parse_missing_endpoint(self):
        with self.assertRaises(ValueError):
            parse_grid(["...", ".#."])

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "astar.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no path", proc.stdout)
        self.assertIn("diagonal", proc.stdout)

    def test_solve_sample(self):
        proc = self.run_cli("solve", str(SAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("optimal: yes", proc.stdout)

    def test_solve_no_path_exit_one(self):
        grid = "S..\n..#\n.#G"
        p = APP_DIR / "_blocked.txt"
        p.write_text(grid, encoding="utf-8")
        try:
            proc = self.run_cli("solve", str(p))
        finally:
            p.unlink()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no path", proc.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("solve", "no.txt")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
