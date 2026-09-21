"""test_sudoku.py -- sudoku.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

import sudoku
from sudoku import (
    SudokuError, candidates, count_solutions, format_grid, generate,
    is_legal, is_solved, parse, solve,
)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample_puzzle.txt"

PUZZLE = """
530070000
600195000
098000060
800060003
400803001
700020006
060000280
000419005
000080079
"""

SOLUTION = """
534678912
672195348
198342567
859761423
426853791
713924856
961537284
287419635
345286179
"""


class TestParseFormat(unittest.TestCase):
    def test_compact_parse(self):
        grid = parse(PUZZLE)
        self.assertEqual(len(grid), 9)
        self.assertEqual(grid[0], [5, 3, 0, 0, 7, 0, 0, 0, 0])
        self.assertEqual(sum(row.count(0) for row in grid), 51)

    def test_pretty_matches_compact(self):
        pretty = SAMPLE.read_text(encoding="utf-8")
        self.assertEqual(parse(pretty), parse(PUZZLE))

    def test_alternative_empty_marks(self):
        self.assertEqual(parse(PUZZLE.replace("0", ".")), parse(PUZZLE))
        self.assertEqual(parse(PUZZLE.replace("0", "_")), parse(PUZZLE))

    def test_wrong_cell_count(self):
        with self.assertRaises(SudokuError):
            parse("123456789")
        with self.assertRaises(SudokuError):
            parse("9" * 82)

    def test_format_contains_separators(self):
        text = format_grid(parse(SOLUTION))
        self.assertIn("|", text)
        self.assertIn("------+-------+------", text)
        self.assertEqual(len(text.splitlines()), 11)  # 9 行 + 2 分隔行


class TestLegality(unittest.TestCase):
    def test_solved_is_legal_and_complete(self):
        g = parse(SOLUTION)
        self.assertTrue(is_legal(g))
        self.assertTrue(is_solved(g))

    def test_puzzle_legal_but_incomplete(self):
        g = parse(PUZZLE)
        self.assertTrue(is_legal(g))
        self.assertFalse(is_solved(g))

    def test_row_column_box_conflicts(self):
        g = parse(PUZZLE)
        g[0][2] = 3  # 与同行 5 3 . 不冲突？r0 已有 3? 没有；放 r0c2=3 与 r1? 列 c2 有 8
        # r0c2 列 c2: r2c2=8，无 3；宫 (0,0) 内 r1c0=6 r2c1=9 r2c2=8 r0c0=5 r0c1=3
        # 宫内已有 3 (r0c1=3) -> 宫冲突
        self.assertFalse(is_legal(g))

        g2 = parse(PUZZLE)
        g2[3][1] = 4  # r3 行已有 4? r3: 8 0 0 0 6 0 0 0 3，无 4；c1 列 r4c0=4 不同列
        # c1 列：r2c1=9, r6c1=6；宫(3,0): r4c0=4 -> 宫冲突
        self.assertFalse(is_legal(g2))

    def test_candidates(self):
        g = parse(PUZZLE)
        cand = candidates(g, 0, 2)
        self.assertEqual(cand, {1, 2, 4})  # 经典题 r0c2 只能是 4? 实际解为 4
        # 解中 r0c2=4；候选集合包含 4
        self.assertIn(4, cand)


class TestSolve(unittest.TestCase):
    def test_solves_known_puzzle(self):
        self.assertEqual(solve(parse(PUZZLE)), parse(SOLUTION))

    def test_solve_does_not_mutate_input(self):
        original = parse(PUZZLE)
        snapshot = [row[:] for row in original]
        solve(original)
        self.assertEqual(original, snapshot)

    def test_already_solved(self):
        g = parse(SOLUTION)
        self.assertEqual(solve(g), parse(SOLUTION))

    def test_conflicting_grid_no_solution(self):
        g = parse(PUZZLE)
        g[0][3] = 5  # r0 已有 5，行冲突
        self.assertIsNone(solve(g))

    def test_legal_but_unsatisfiable_puzzle(self):
        # 首行 1..8，最后一格只能是 9；但右上宫内 r1c8 已放 9，导致无解。
        g = [[0] * 9 for _ in range(9)]
        g[0] = [1, 2, 3, 4, 5, 6, 7, 8, 0]
        g[1][8] = 9
        self.assertTrue(is_legal(g))
        self.assertIsNone(solve(g))


class TestSolutionCount(unittest.TestCase):
    def test_unique_puzzle(self):
        self.assertEqual(count_solutions(parse(PUZZLE), limit=2), 1)

    def test_ambiguous_puzzle_multiple(self):
        g = [[0] * 9 for _ in range(9)]
        g[0] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        g[1] = [7, 8, 9, 1, 2, 3, 4, 5, 6]  # 行/列/宫均无冲突，解不唯一
        self.assertTrue(is_legal(g))
        self.assertEqual(count_solutions(g, limit=2), 2)

    def test_illegal_grid_zero(self):
        g = parse(PUZZLE)
        g[0][0] = 6  # 与 r1c0=6 同列冲突
        self.assertEqual(count_solutions(g), 0)


class TestGenerate(unittest.TestCase):
    def test_reproducible_with_seed(self):
        self.assertEqual(generate(seed=7, clues=40),
                         generate(seed=7, clues=40))
        self.assertNotEqual(generate(seed=1, clues=40),
                            generate(seed=2, clues=40))

    def test_generated_puzzle_quality(self):
        puzzle = generate(seed=42, clues=40)
        given = sum(1 for r in range(9) for c in range(9) if puzzle[r][c])
        self.assertEqual(given, 40)
        self.assertTrue(is_legal(puzzle))
        self.assertEqual(count_solutions(puzzle, limit=2), 1)
        solution = solve(puzzle)
        self.assertIsNotNone(solution)
        # 已知格在解中保持不变
        for r in range(9):
            for c in range(9):
                if puzzle[r][c]:
                    self.assertEqual(puzzle[r][c], solution[r][c])

    def test_clues_bounds(self):
        with self.assertRaises(SudokuError):
            generate(seed=0, clues=16)
        with self.assertRaises(SudokuError):
            generate(seed=0, clues=82)


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "sudoku.py"), *args],
            capture_output=True, text=True, timeout=120, cwd=APP_DIR,
            input=input_text,
        )

    def test_solve_file(self):
        proc = self.run_cli("solve", str(SAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("5 3 4", proc.stdout)
        self.assertIn("3 4 5", proc.stdout)

    def test_check_incomplete(self):
        proc = self.run_cli("check", str(SAMPLE))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("合法但未完成", proc.stdout)

    def test_generate_and_stdin_solve(self):
        gen = self.run_cli("generate", "--seed", "3", "--clues", "45")
        self.assertEqual(gen.returncode, 0, gen.stderr)
        solved = self.run_cli("solve", "-", input_text=gen.stdout)
        self.assertEqual(solved.returncode, 0, solved.stderr)
        check = self.run_cli("check", "-", input_text=solved.stdout)
        self.assertEqual(check.returncode, 0)
        self.assertIn("合法且已完成", check.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("solve", "no-such-puzzle.txt")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stderr)


if __name__ == "__main__":
    unittest.main()
