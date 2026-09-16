import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from life import (
    dimensions,
    load_pattern,
    main,
    neighbor_count,
    pad_grid,
    parse_grid,
    population,
    render,
    run,
    step,
)


def full(rows, cols):
    return [[1] * cols for _ in range(rows)]


class TestNeighbors(unittest.TestCase):
    def test_center_has_eight(self):
        g = full(3, 3)
        self.assertEqual(neighbor_count(g, 1, 1), 8)

    def test_bounded_corner_has_three(self):
        g = full(3, 3)
        self.assertEqual(neighbor_count(g, 0, 0), 3)
        self.assertEqual(neighbor_count(g, 2, 2), 3)

    def test_toroidal_corner_wraps(self):
        g = full(3, 3)
        self.assertEqual(neighbor_count(g, 0, 0, toroidal=True), 8)

    def test_toroidal_edges_connect(self):
        # 3x3 场中只有 (0,2) 活；环面下它跨过右边界成为 (0,0) 的邻居
        g = [[0, 0, 1], [0, 0, 0], [0, 0, 0]]
        self.assertEqual(neighbor_count(g, 0, 0, toroidal=True), 1)
        self.assertEqual(neighbor_count(g, 0, 0, toroidal=False), 0)


class TestRules(unittest.TestCase):
    def test_lonely_cell_dies(self):
        self.assertEqual(step([[1]]), [[0]])

    def test_block_is_still_life(self):
        block = parse_grid("OO\nOO")
        self.assertEqual(run(block, 5), block)

    def test_birth_on_three_neighbors(self):
        # 中心死细胞，上排三个活邻居 -> 诞生
        g = parse_grid("OOO\n...\n...")
        self.assertEqual(step(g)[1][1], 1)

    def test_overpopulation_kills(self):
        # 十字：中心有 4 个邻居，应死亡
        g = parse_grid(".O.\nOOO\n.O.")
        self.assertEqual(step(g)[1][1], 0)

    def test_empty_stays_empty(self):
        self.assertEqual(step([[0] * 4 for _ in range(4)]),
                         [[0] * 4 for _ in range(4)])


class TestPatterns(unittest.TestCase):
    def test_blinker_oscillates(self):
        horizontal = pad_grid(parse_grid("OOO"), 1, 1, 0, 0)  # 3x3 场
        vertical = step(horizontal)
        self.assertEqual(population(vertical), 3)
        self.assertEqual(vertical[0][1], 1)
        self.assertEqual(vertical[2][1], 1)
        self.assertEqual(step(vertical), horizontal)  # 周期 2

    def test_beacon_period_two(self):
        g = load_pattern("beacon", field=0)
        self.assertNotEqual(step(g), g)
        self.assertEqual(run(g, 2), g)

    def test_toad_period_two(self):
        # 蟾蜍振荡时会向上下各扩一行，需要留白
        g = pad_grid(load_pattern("toad", field=0), 1, 1, 0, 0)
        self.assertNotEqual(step(g), g)
        self.assertEqual(run(g, 2), g)

    def test_glider_moves_diagonally_after_four(self):
        base = load_pattern("glider", field=0)
        start = pad_grid(base, 1, 2, 1, 2)          # 6x6 场
        shifted = pad_grid(base, 2, 1, 2, 1)        # 整体右下平移一格
        self.assertEqual(run(start, 4), shifted)
        self.assertEqual(population(run(start, 4)), 5)

    def test_toroidal_glider_survives_on_wrap_field(self):
        g = load_pattern("glider", field=8)         # 8x8 环面，滑翔机持续绕行
        after = run(g, 40, toroidal=True)
        self.assertEqual(population(after), 5)      # 滑翔机永不消亡


class TestParseRender(unittest.TestCase):
    def test_parse_alive_dead_variants(self):
        self.assertEqual(parse_grid("O.1\n0.O"),
                         [[1, 0, 1], [0, 0, 1]])

    def test_ragged_rows_raise(self):
        with self.assertRaises(ValueError):
            parse_grid("OOO\nOO")

    def test_invalid_char_raises(self):
        with self.assertRaises(ValueError):
            parse_grid("OX.\n...")

    def test_empty_text(self):
        self.assertEqual(parse_grid(""), [])
        self.assertEqual(dimensions([]), (0, 0))

    def test_render_roundtrip(self):
        g = parse_grid("O..\n.O.\n..O")
        self.assertEqual(parse_grid(render(g)), g)


class TestCli(unittest.TestCase):
    def test_run_glider(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["run", "glider", "--gens", "4", "--field", "8"])
        self.assertEqual(rc, 0)
        self.assertIn("Gen 4", buf.getvalue())

    def test_all_prints_every_generation(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["run", "blinker", "--gens", "2", "--field", "5", "--all"])
        self.assertEqual(rc, 0)
        self.assertIn("Gen 0", buf.getvalue())
        self.assertIn("Gen 2", buf.getvalue())

    def test_from_file(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write("OO\nOO\n")
        tmp.close()
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["from-file", tmp.name, "--gens", "3"])
        self.assertEqual(rc, 0)
        self.assertIn("pop=4", buf.getvalue())

    def test_bad_pattern_rejected(self):
        with self.assertRaises(SystemExit):
            main(["run", "nope"])


if __name__ == "__main__":
    unittest.main()
