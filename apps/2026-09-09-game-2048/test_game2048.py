import io
import random
import unittest
from contextlib import redirect_stdout

from game2048 import (
    DIRECTIONS,
    Game,
    available_moves,
    empty_cells,
    is_game_over,
    max_tile,
    move,
    render,
    slide_row_left,
    spawn_tile,
)


def zeros():
    return [[0] * 4 for _ in range(4)]


class TestSlide(unittest.TestCase):
    def test_pair_merge(self):
        self.assertEqual(slide_row_left([2, 2, 0, 0]), ([4, 0, 0, 0], 4, True))

    def test_four_equal_merge_once(self):
        self.assertEqual(slide_row_left([2, 2, 2, 2]), ([4, 4, 0, 0], 8, True))

    def test_compress_then_merge(self):
        self.assertEqual(slide_row_left([0, 2, 2, 4]), ([4, 4, 0, 0], 4, True))
        self.assertEqual(slide_row_left([2, 0, 0, 2]), ([4, 0, 0, 0], 4, True))

    def test_no_merge_no_move(self):
        self.assertEqual(slide_row_left([2, 4, 2, 4]), ([2, 4, 2, 4], 0, False))

    def test_two_pairs_score(self):
        self.assertEqual(slide_row_left([4, 4, 8, 8]), ([8, 16, 0, 0], 24, True))

    def test_three_same_merge_leftmost_pair(self):
        self.assertEqual(slide_row_left([2, 2, 2, 0]), ([4, 2, 0, 0], 4, True))


class TestMove(unittest.TestCase):
    def test_move_right_is_mirror(self):
        board = zeros()
        board[0] = [2, 2, 0, 0]
        new_board, gained, moved = move(board, "right")
        self.assertEqual(new_board[0], [0, 0, 0, 4])
        self.assertEqual(gained, 4)
        self.assertTrue(moved)

    def test_move_up_merges_column(self):
        board = zeros()
        board[0][0] = 2
        board[1][0] = 2
        new_board, _, moved = move(board, "up")
        self.assertEqual(new_board[0][0], 4)
        self.assertTrue(moved)

    def test_move_down_merges_to_bottom(self):
        board = zeros()
        board[0][0] = 2
        board[1][0] = 2
        new_board, _, _ = move(board, "down")
        self.assertEqual(new_board[3][0], 4)
        self.assertEqual(new_board[0][0], 0)

    def test_blocked_direction_not_moved(self):
        board = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]
        new_board, gained, moved = move(board, "left")
        self.assertFalse(moved)
        self.assertEqual(gained, 0)
        self.assertEqual(new_board, board)

    def test_unknown_direction_raises(self):
        with self.assertRaises(ValueError):
            move(zeros(), "sideways")

    def test_move_does_not_mutate_input(self):
        board = zeros()
        board[0] = [2, 2, 0, 0]
        snapshot = [list(r) for r in board]
        move(board, "left")
        self.assertEqual(board, snapshot)


class TestSpawn(unittest.TestCase):
    def test_new_game_two_tiles(self):
        game = Game.new_game(seed=1)
        nonzeros = [v for r in game.board for v in r if v]
        self.assertEqual(len(nonzeros), 2)
        self.assertTrue(all(v in (2, 4) for v in nonzeros))

    def test_seed_is_deterministic(self):
        self.assertEqual(Game.new_game(seed=123).board, Game.new_game(seed=123).board)

    def test_valid_step_spawns_one_tile(self):
        game = Game(rng=random.Random(1))
        game.board = zeros()
        game.board[0][1] = 2
        valid, gained = game.step("left")
        self.assertTrue(valid)
        self.assertEqual(gained, 0)
        self.assertEqual(len([v for r in game.board for v in r if v]), 2)
        self.assertEqual(game.moves, 1)

    def test_blocked_step_spawns_nothing(self):
        game = Game(rng=random.Random(1))
        game.board = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]
        before = [list(r) for r in game.board]
        valid, gained = game.step("left")
        self.assertFalse(valid)
        self.assertEqual(gained, 0)
        self.assertEqual(game.board, before)
        self.assertEqual(game.moves, 0)

    def test_spawn_full_board_false(self):
        full = [[2] * 4 for _ in range(4)]
        self.assertFalse(spawn_tile(full, random.Random(0)))

    def test_empty_cells(self):
        board = zeros()
        self.assertEqual(len(empty_cells(board)), 16)


class TestGameOver(unittest.TestCase):
    def test_checkerboard_full_is_over(self):
        board = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]
        self.assertTrue(is_game_over(board))
        self.assertEqual(available_moves(board), [])

    def test_full_with_adjacent_equal_not_over(self):
        board = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 4]]
        self.assertFalse(is_game_over(board))
        self.assertIn("right", available_moves(board))

    def test_empty_board_not_over(self):
        # 空盘没有块可滑动，但语义上不是终局
        self.assertFalse(is_game_over(zeros()))
        one = zeros()
        one[0][0] = 2
        # 左上角的块只有向右/向下才会移动，左/上贴边无变化
        self.assertEqual(set(available_moves(one)), {"right", "down"})


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_script_same_result(self):
        def play():
            g = Game.new_game(seed=2026)
            for d in ("left", "up", "left", "right", "down", "left"):
                g.step(d)
            return g
        a, b = play(), play()
        self.assertEqual(a.board, b.board)
        self.assertEqual(a.score, b.score)
        self.assertEqual(a.moves, b.moves)


class TestRenderAndCli(unittest.TestCase):
    def test_render_contains_score_and_grid(self):
        board = zeros()
        board[0][0] = 2048
        text = render(board, score=2048)
        self.assertIn("score: 2048", text)
        self.assertIn("2048", text)
        self.assertEqual(max_tile(board), 2048)

    def test_cli_scripted(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = __import__("game2048").main(["--seed", "7", "--script", "l,l,u,r"])
        self.assertEqual(rc, 0)
        self.assertIn("score:", buf.getvalue())
        self.assertIn("moves:", buf.getvalue())

    def test_cli_bad_direction_returns_2(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = __import__("game2048").main(["--seed", "7", "--script", "zzz"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
