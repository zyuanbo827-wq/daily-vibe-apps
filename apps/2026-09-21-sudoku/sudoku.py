"""sudoku.py -- 零依赖数独工具：求解 / 校验 / 生成。

求解器：回溯 + MRV（最少候选数格子优先）+ 候选位运算；
唯一性判定：带上限的解计数（生成挖洞时保证唯一解）；
生成器：随机化回溯填满 9x9，再按种子随机顺序挖洞，
每挖一格都重新验证解唯一，不唯一则回填。

附带 solve / check / generate 三个 CLI 子命令。仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import random
import sys
from copy import deepcopy
from typing import List, Optional, Sequence, Tuple

Grid = List[List[int]]
EMPTY = 0
DIGITS = frozenset(range(1, 10))


class SudokuError(ValueError):
    """输入数据错误。"""


# --------------------------------------------------------------------------- #
# 解析与渲染
# --------------------------------------------------------------------------- #
def parse(text: str) -> Grid:
    """从宽松文本解析 9x9 数独：1-9 为已知，0/. /_ 为空，其余字符忽略。"""
    cells: List[int] = []
    for ch in text:
        if ch in "123456789":
            cells.append(int(ch))
        elif ch in "0._":
            cells.append(0)
        # 空白、|、-、+、换行等一律忽略
    if len(cells) != 81:
        raise SudokuError(f"需要恰好 81 个格子，实际解析到 {len(cells)} 个")
    return [cells[i * 9:(i + 1) * 9] for i in range(9)]


def format_grid(grid: Grid) -> str:
    lines = []
    for r in range(9):
        row = []
        for c in range(9):
            row.append(str(grid[r][c]) if grid[r][c] else ".")
            if c in (2, 5):
                row.append("|")
        line = " ".join(row)
        lines.append(line)
        if r in (2, 5):
            lines.append("------+-------+------")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 合法性
# --------------------------------------------------------------------------- #
def _unit_conflicts(values: Sequence[int]) -> bool:
    seen = set()
    for v in values:
        if v == 0:
            continue
        if v in seen:
            return True
        seen.add(v)
    return False


def is_legal(grid: Grid) -> bool:
    """部分棋盘是否无冲突（行、列、3x3 宫内无重复）。"""
    for r in range(9):
        if _unit_conflicts(grid[r]):
            return False
    for c in range(9):
        if _unit_conflicts([grid[r][c] for r in range(9)]):
            return False
    for br in range(0, 9, 3):
        for bc in range(0, 9, 3):
            box = [grid[r][c] for r in range(br, br + 3)
                   for c in range(bc, bc + 3)]
            if _unit_conflicts(box):
                return False
    return True


def is_solved(grid: Grid) -> bool:
    if not is_legal(grid):
        return False
    return all(grid[r][c] != 0 for r in range(9) for c in range(9))


def candidates(grid: Grid, r: int, c: int) -> set:
    """返回 (r,c) 空格可填数字集合。"""
    if grid[r][c] != 0:
        return set()
    used = set(grid[r])
    used.update(grid[i][c] for i in range(9))
    br, bc = (r // 3) * 3, (c // 3) * 3
    used.update(grid[i][j] for i in range(br, br + 3)
                for j in range(bc, bc + 3))
    return DIGITS - used


# --------------------------------------------------------------------------- #
# 求解
# --------------------------------------------------------------------------- #
def _mrv_cell(grid: Grid) -> Optional[Tuple[int, int, set]]:
    best: Optional[Tuple[int, int, set]] = None
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                cand = candidates(grid, r, c)
                if not cand:
                    return (r, c, set())  # 死路
                if best is None or len(cand) < len(best[2]):
                    best = (r, c, cand)
                    if len(cand) == 1:
                        return best
    return best


def solve(grid: Grid) -> Optional[Grid]:
    """返回一个解（新棋盘）；无解返回 None。"""
    if not is_legal(grid):
        return None
    work = deepcopy(grid)
    if _backtrack(work):
        return work
    return None


def _backtrack(grid: Grid) -> bool:
    cell = _mrv_cell(grid)
    if cell is None:
        return True
    r, c, cand = cell
    if not cand:
        return False
    for n in sorted(cand):
        grid[r][c] = n
        if _backtrack(grid):
            return True
        grid[r][c] = 0
    return False


def count_solutions(grid: Grid, limit: int = 2) -> int:
    """统计解的数量，达到 limit 即提前返回（用于唯一性判定）。"""
    if not is_legal(grid):
        return 0
    work = deepcopy(grid)
    counter = 0

    def dfs() -> bool:
        nonlocal counter
        cell = _mrv_cell(work)
        if cell is None:
            counter += 1
            return counter >= limit
        r, c, cand = cell
        if not cand:
            return False
        for n in sorted(cand):
            work[r][c] = n
            if dfs():
                return True
            work[r][c] = 0
        return False

    dfs()
    return counter


# --------------------------------------------------------------------------- #
# 生成
# --------------------------------------------------------------------------- #
def _fill_random(grid: Grid, rng: random.Random) -> bool:
    cell = _mrv_cell(grid)
    if cell is None:
        return True
    r, c, cand = cell
    if not cand:
        return False
    order = sorted(cand)
    rng.shuffle(order)
    for n in order:
        grid[r][c] = n
        if _fill_random(grid, rng):
            return True
        grid[r][c] = 0
    return False


def generate(seed: int = 0, clues: int = 40) -> Grid:
    """生成有唯一解的数独题，clues 为保留的已知格数（17~81）。"""
    if not 17 <= clues <= 81:
        raise SudokuError("clues 必须在 17 到 81 之间（17 是唯一解的理论下限）")
    rng = random.Random(seed)
    board = [[0] * 9 for _ in range(9)]
    if not _fill_random(board, rng):
        raise SudokuError("生成完整棋盘失败")  # 理论上不会发生

    positions = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(positions)
    current = 81
    for r, c in positions:
        if current <= clues:
            break
        saved = board[r][c]
        board[r][c] = 0
        if count_solutions(board, limit=2) != 1:
            board[r][c] = saved  # 挖掉后解不唯一，回填
        else:
            current -= 1
    return board


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()


def _cmd_solve(args: argparse.Namespace) -> int:
    try:
        grid = parse(_read_input(args.input))
    except (SudokuError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    solution = solve(grid)
    if solution is None:
        print("无解：该数独存在冲突或无法完成。")
        return 1
    print(format_grid(solution))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        grid = parse(_read_input(args.input))
    except (SudokuError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not is_legal(grid):
        print("非法：行、列或 3x3 宫内存在重复数字。")
        return 1
    blanks = sum(1 for r in range(9) for c in range(9) if grid[r][c] == 0)
    if blanks:
        print(f"合法但未完成：还有 {blanks} 个空格。")
        return 1
    print("合法且已完成。")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    try:
        puzzle = generate(seed=args.seed, clues=args.clues)
    except SudokuError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_grid(puzzle))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="数独求解器 / 校验器 / 生成器")
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("solve", help="求解数独（- 表示从标准输入读）")
    ps.add_argument("input", help="数独文本文件，- 表示标准输入")
    ps.set_defaults(func=_cmd_solve)

    pc = sub.add_parser("check", help="检查数独是否合法 / 完成")
    pc.add_argument("input", help="数独文本文件，- 表示标准输入")
    pc.set_defaults(func=_cmd_check)

    pg = sub.add_parser("generate", help="生成唯一解数独题")
    pg.add_argument("--seed", type=int, default=0, help="随机种子（可复现）")
    pg.add_argument("--clues", type=int, default=40, help="保留已知格数，默认 40")
    pg.set_defaults(func=_cmd_generate)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
