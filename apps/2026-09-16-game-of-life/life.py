"""game-of-life：零依赖的康威生命游戏（仅 Python 标准库）。

- B3/S23 规则：死细胞恰有 3 个邻居则诞生；活细胞有 2 或 3 个邻居则存活；
- 支持有界平面与环面（上下左右环绕）两种边界；
- 内置滑翔机、闪烁器、方块、信标等经典图案，可从文本读入自定义盘面；
- 纯函数核心 + 文本 CLI，可演化任意代数并用 ASCII 渲染。

命令行：
    python life.py run glider --gens 20
    python life.py run blinker --gens 2 --all
    python life.py from-file seed.txt --gens 10 --wrap
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Tuple

ALIVE = "O"
DEAD = "."

PATTERNS = {
    # 标准滑翔机：4 代后整体向右下平移一格
    "glider": [
        ".O.",
        "..O",
        "OOO",
    ],
    "blinker": [
        "OOO",
    ],
    "block": [
        "OO",
        "OO",
    ],
    "beacon": [
        "OO..",
        "OO..",
        "..OO",
        "..OO",
    ],
    "toad": [
        ".OOO",
        "OOO.",
    ],
}


def parse_grid(text: str) -> List[List[int]]:
    """把 O/1 视为活、./0 视为死；要求行列整齐。"""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(ch not in "O1.0" for ch in line):
            raise ValueError(f"invalid character in grid row: {line!r}")
        rows.append([1 if ch in "O1" else 0 for ch in line])
    if rows and len({len(r) for r in rows}) != 1:
        raise ValueError("grid rows must all have the same length")
    return rows


def pad_grid(grid: List[List[int]], top: int, bottom: int,
             left: int, right: int) -> List[List[int]]:
    """在四周补空白，便于把小图案放进更大的演化场。"""
    width = len(grid[0]) if grid else 0
    padded = []
    blank_row = [0] * (left + width + right)
    for _ in range(top):
        padded.append(blank_row[:])
    for row in grid:
        padded.append([0] * left + list(row) + [0] * right)
    for _ in range(bottom):
        padded.append(blank_row[:])
    return padded


def dimensions(grid: List[List[int]]) -> Tuple[int, int]:
    if not grid:
        return 0, 0
    return len(grid), len(grid[0])


def neighbor_count(grid: List[List[int]], r: int, c: int,
                   toroidal: bool = False) -> int:
    rows, cols = dimensions(grid)
    total = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if toroidal:
                nr %= rows
                nc %= cols
                total += grid[nr][nc]
            elif 0 <= nr < rows and 0 <= nc < cols:
                total += grid[nr][nc]
    return total


def step(grid: List[List[int]], toroidal: bool = False) -> List[List[int]]:
    """演化一代（B3/S23）。"""
    rows, cols = dimensions(grid)
    nxt = [[0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            n = neighbor_count(grid, r, c, toroidal=toroidal)
            if grid[r][c]:
                nxt[r][c] = 1 if n in (2, 3) else 0
            else:
                nxt[r][c] = 1 if n == 3 else 0
    return nxt


def run(grid: List[List[int]], generations: int,
        toroidal: bool = False) -> List[List[int]]:
    cur = [list(r) for r in grid]
    for _ in range(generations):
        cur = step(cur, toroidal=toroidal)
    return cur


def population(grid: List[List[int]]) -> int:
    return sum(sum(row) for row in grid)


def render(grid: List[List[int]]) -> str:
    return "\n".join("".join(ALIVE if v else DEAD for v in row) for row in grid)


def load_pattern(name: str, field: int = 8) -> List[List[int]]:
    """取内置图案并放在 field x field 的空白场中央偏左上。"""
    if name not in PATTERNS:
        raise KeyError(name)
    small = parse_grid("\n".join(PATTERNS[name]))
    if field:
        h, w = dimensions(small)
        return pad_grid(small, 1, max(0, field - h - 1), 1, max(0, field - w - 1))
    return small


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zero-dependency Conway's Game of Life (stdlib only)."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="evolve a built-in pattern")
    p_run.add_argument("pattern", choices=sorted(PATTERNS))
    p_run.add_argument("--gens", type=int, default=10)
    p_run.add_argument("--field", type=int, default=8)
    p_run.add_argument("--wrap", action="store_true")
    p_run.add_argument("--all", action="store_true", help="print every generation")
    p_file = sub.add_parser("from-file", help="evolve a grid from a text file")
    p_file.add_argument("path")
    p_file.add_argument("--gens", type=int, default=10)
    p_file.add_argument("--wrap", action="store_true")
    p_file.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            grid = load_pattern(args.pattern, field=args.field)
        else:
            with open(args.path, encoding="utf-8") as f:
                grid = parse_grid(f.read())
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    gens = max(0, args.gens)
    cur = grid
    if args.all:
        for g in range(gens + 1):
            print(f"Gen {g}  pop={population(cur)}")
            print(render(cur))
            if g < gens:
                cur = step(cur, toroidal=args.wrap)
    else:
        cur = run(grid, gens, toroidal=args.wrap)
        print(f"Gen {gens}  pop={population(cur)}")
        print(render(cur))
    return 0


if __name__ == "__main__":
    sys.exit(main())
