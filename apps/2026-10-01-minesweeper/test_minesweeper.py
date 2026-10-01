"""test_minesweeper.py -- minesweeper.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

from minesweeper import Board, GameError, render

APP_DIR = Path(__file__).resolve().parent


def board(rows, cols, mines_positions):
    return Board(rows, cols, len(mines_positions),
                 mine_positions=set(mines_positions))


class TestConstruction(unittest.TestCase):
    def test_valid_init(self):
        b = Board(9, 9, 10, seed=1)
        self.assertEqual(b.status, "ready")
        self.assertFalse(b.started)

    def test_bad_dimensions(self):
        with self.assertRaises(GameError):
            Board(0, 9, 1)
        with self.assertRaises(GameError):
            Board(9, 9, -1)
        with self.assertRaises(GameError):
            Board(2, 2, 4)  # 无安全格

    def test_injected_positions_mismatch(self):
        with self.assertRaises(GameError):
            Board(3, 3, 2, mine_positions={(0, 0)})


class TestCounts(unittest.TestCase):
    def test_counts_match_neighbor_formula(self):
        mines = {(1, 1), (3, 3), (0, 4)}
        b = board(5, 5, mines)
        for r in range(5):
            for c in range(5):
                if (r, c) in mines:
                    continue
                expected = sum(1 for nr, nc in b.neighbors(r, c)
                               if (nr, nc) in mines)
                self.assertEqual(b.grid[r][c].count, expected,
                                 msg=(r, c))


class TestFirstClickSafety(unittest.TestCase):
    def test_first_click_and_neighbors_safe(self):
        b = Board(9, 9, 10, seed=20261001)
        b.reveal(4, 4)
        for r, c in [(4, 4), *list(b.neighbors(4, 4))]:
            self.assertFalse(b.grid[r][c].mine, msg=(r, c))
        total = sum(1 for row in b.grid for cell in row if cell.mine)
        self.assertEqual(total, 10)
        self.assertEqual(b.status, "playing")

    def test_deterministic_seed(self):
        b1 = Board(9, 9, 10, seed=7)
        b2 = Board(9, 9, 10, seed=7)
        b1.reveal(2, 3)
        b2.reveal(2, 3)
        self.assertEqual(render(b1), render(b2))


class TestFloodReveal(unittest.TestCase):
    def test_flood_opens_zero_region(self):
        b = board(5, 5, {(0, 0)})
        opened = b.reveal(4, 4)
        # 21 个零格 + 3 个相邻数字格 (0,1)(1,0)(1,1) 一并展开 = 24
        self.assertEqual(opened, 24)
        self.assertTrue(b.grid[4][4].revealed)
        self.assertTrue(b.grid[0][1].revealed)
        self.assertFalse(b.grid[0][0].revealed)

    def test_reveal_number_opens_one(self):
        b = board(5, 5, {(0, 0)})
        self.assertEqual(b.reveal(0, 1), 1)

    def test_revealed_cell_idempotent(self):
        b = board(3, 3, {(0, 0)})
        first = b.reveal(2, 2)
        self.assertEqual(b.reveal(2, 2), 0)
        self.assertGreater(first, 0)


class TestFlags(unittest.TestCase):
    def test_flag_blocks_reveal(self):
        b = board(3, 3, {(0, 0)})
        self.assertTrue(b.toggle_flag(2, 2))
        self.assertEqual(b.flags, 1)
        self.assertEqual(b.reveal(2, 2), 0)
        self.assertFalse(b.grid[2][2].revealed)
        self.assertFalse(b.toggle_flag(2, 2))
        self.assertGreater(b.reveal(2, 2), 0)

    def test_flag_revealed_cell_rejected(self):
        b = board(3, 3, {(0, 0)})
        b.reveal(2, 2)
        self.assertFalse(b.toggle_flag(2, 2))


class TestLose(unittest.TestCase):
    def test_step_on_mine(self):
        b = board(4, 4, {(0, 0), (3, 3)})
        b.reveal(0, 0)
        self.assertEqual(b.status, "lost")
        self.assertTrue(b.grid[0][0].revealed)
        # 失败后操作无效
        self.assertEqual(b.reveal(2, 2), 0)
        self.assertFalse(b.toggle_flag(1, 1))

    def test_out_of_bounds(self):
        b = board(3, 3, {(0, 0)})
        with self.assertRaises(GameError):
            b.reveal(3, 0)
        with self.assertRaises(GameError):
            b.toggle_flag(0, -1)


class TestWin(unittest.TestCase):
    def test_win_2x2(self):
        b = board(2, 2, {(0, 0)})
        b.reveal(1, 1)
        b.reveal(0, 1)
        self.assertEqual(b.status, "playing")
        b.reveal(1, 0)
        self.assertEqual(b.status, "won")
        self.assertEqual(b.unrevealed_safe(), 0)


class TestChord(unittest.TestCase):
    def test_chord_correct_flags(self):
        b = board(3, 3, {(0, 0)})
        b.reveal(1, 1)
        b.toggle_flag(0, 0)
        opened = b.chord(1, 1)
        self.assertGreater(opened, 0)
        self.assertEqual(b.status, "won")

    def test_chord_wrong_flag_loses(self):
        b = board(3, 3, {(0, 0)})
        b.reveal(1, 1)
        b.toggle_flag(0, 1)          # 旗标在安全格上
        b.chord(1, 1)
        self.assertEqual(b.status, "lost")

    def test_chord_guards(self):
        b = board(3, 3, {(0, 0)})
        self.assertEqual(b.chord(1, 1), 0)       # 未展开
        b.reveal(1, 1)
        self.assertEqual(b.chord(1, 1), 0)       # 旗数不匹配
        b.reveal(2, 2)
        self.assertEqual(b.chord(2, 2), 0)       # 数字为 0 不触发


class TestRender(unittest.TestCase):
    def test_render_symbols(self):
        b = board(3, 3, {(0, 0)})
        b.toggle_flag(2, 2)
        text = render(b)
        self.assertIn("F", text)
        self.assertIn("#", text)
        b.reveal(0, 0)
        self.assertIn("*", render(b))


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "minesweeper.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("首击", proc.stdout)
        self.assertIn("状态：", proc.stdout)

    def test_play_then_quit(self):
        proc = self.run_cli("play", "--seed", "5",
                            input_text="r 4 4\nf 0 0\nq\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(">", proc.stdout)

    def test_play_bad_command_recovered(self):
        proc = self.run_cli("play", "--seed", "5",
                            input_text="r\nr 99 0\nr 4 4\nq\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("error:", proc.stdout)

    def test_play_lose(self):
        # 极小棋盘：2x2 一雷，反复展开直到踩雷或结束
        script = "r 0 0\nr 0 1\nr 1 0\n"
        proc = self.run_cli("play", "--rows", "2", "--cols", "2",
                            "--mines", "1", input_text=script)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("对局结束", proc.stdout)


if __name__ == "__main__":
    unittest.main()
