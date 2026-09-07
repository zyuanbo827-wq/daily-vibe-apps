import io
import sys
import unittest
from contextlib import redirect_stdout

from maze import E, N, S, W, Maze, main


class TestGeneration(unittest.TestCase):
    def test_dimensions(self):
        m = Maze(5, 3, seed=1)
        self.assertEqual(len(m.walls), 3)
        self.assertEqual(len(m.walls[0]), 5)

    def test_seed_is_deterministic(self):
        a = Maze(8, 6, seed=42)
        b = Maze(8, 6, seed=42)
        self.assertEqual(a.walls, b.walls)

    def test_different_seeds_differ(self):
        a = Maze(6, 6, seed=1)
        b = Maze(6, 6, seed=2)
        self.assertNotEqual(a.walls, b.walls)

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            Maze(1, 5)
        with self.assertRaises(ValueError):
            Maze(5, 0)

    def test_outer_boundary_walls_intact(self):
        m = Maze(6, 4, seed=3)
        for x in range(6):
            self.assertTrue(m.walls[0][x] & N)          # 顶边
            self.assertTrue(m.walls[3][x] & S)          # 底边
        for y in range(4):
            self.assertTrue(m.walls[y][0] & W)          # 左边
            self.assertTrue(m.walls[y][5] & E)          # 右边

    def test_walls_are_symmetric_between_neighbors(self):
        m = Maze(7, 5, seed=9)
        for y in range(5):
            for x in range(7):
                if x + 1 < 7:
                    east_open = not bool(m.walls[y][x] & E)
                    west_open = not bool(m.walls[y][x + 1] & W)
                    self.assertEqual(east_open, west_open)
                if y + 1 < 5:
                    south_open = not bool(m.walls[y][x] & S)
                    north_open = not bool(m.walls[y + 1][x] & N)
                    self.assertEqual(south_open, north_open)


class TestConnectivityAndPath(unittest.TestCase):
    def test_every_cell_reachable(self):
        m = Maze(10, 8, seed=11)
        parent = m.bfs((0, 0), (9, 7))
        self.assertEqual(len(parent), 10 * 8)  # 完美迷宫：全连通

    def test_path_endpoints_and_adjacency(self):
        m = Maze(10, 8, seed=11)
        path = m.shortest_path()
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (9, 7))
        for a, b in zip(path, path[1:]):
            self.assertIn(b, m.open_neighbors(*a))  # 相邻且无墙

    def test_path_is_shortest(self):
        m = Maze(12, 9, seed=5)
        parent = m.bfs()
        path = m.shortest_path()
        # 用 parent 反推 BFS 层数，应与路径步数一致
        goal = (11, 8)
        depth = 0
        cur = goal
        while cur != (0, 0):
            cur = parent[cur]
            depth += 1
        self.assertEqual(depth, len(path) - 1)

    def test_start_equals_goal(self):
        m = Maze(4, 4, seed=1)
        self.assertEqual(m.shortest_path((2, 2), (2, 2)), [(2, 2)])

    def test_open_neighbors_out_of_bounds(self):
        m = Maze(3, 3, seed=1)
        with self.assertRaises(ValueError):
            m.open_neighbors(5, 5)


class TestRender(unittest.TestCase):
    def test_render_grid_size_and_markers(self):
        w, h = 6, 4
        m = Maze(w, h, seed=2)
        text = m.render()
        lines = text.splitlines()
        self.assertEqual(len(lines), 2 * h + 1)
        self.assertTrue(all(len(line) == 3 * w + 1 for line in lines))
        self.assertIn("S", text)
        self.assertIn("G", text)

    def test_render_with_path_overlay(self):
        m = Maze(6, 4, seed=2)
        plain = m.render()
        overlay = m.render(path=m.shortest_path())
        self.assertNotIn("*", plain)
        self.assertIn("*", overlay)


class TestCli(unittest.TestCase):
    def test_cli_success(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["8", "5", "--seed", "42"])
        self.assertEqual(code, 0)
        self.assertIn("shortest path", buf.getvalue())

    def test_cli_no_path_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["4", "4", "--seed", "1", "--no-path"])
        self.assertEqual(code, 0)
        self.assertNotIn("shortest path", buf.getvalue())

    def test_cli_invalid_dimensions(self):
        self.assertEqual(main(["1", "4"]), 2)


if __name__ == "__main__":
    unittest.main()
