"""astar.py -- 零依赖网格寻路实验台。

在带障碍的二维网格上实现：
- A*（4 邻域 Manhattan 启发式 / 8 邻域 Chebyshev 启发式）
- Dijkstra（均匀代价下等价 BFS，用作最优性对照）
输出路径、扩展节点数，并用 ASCII 渲染网格与路径。
"""

from __future__ import annotations

import argparse
import heapq
import sys
from typing import Callable, Dict, List, Optional, Tuple

Pos = Tuple[int, int]

FOUR_DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]
EIGHT_DIRS = FOUR_DIRS + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


class Grid:
    def __init__(self, width: int, height: int,
                 blocked: Optional[set] = None):
        self.width = width
        self.height = height
        self.blocked = set(blocked or [])

    def inside(self, p: Pos) -> bool:
        r, c = p
        return 0 <= r < self.height and 0 <= c < self.width

    def passable(self, p: Pos) -> bool:
        return self.inside(p) and p not in self.blocked

    def neighbors(self, p: Pos, diagonal: bool) -> List[Tuple[Pos, float]]:
        dirs = EIGHT_DIRS if diagonal else FOUR_DIRS
        out = []
        r, c = p
        for dr, dc in dirs:
            q = (r + dr, c + dc)
            if not self.passable(q):
                continue
            # 对角移动时禁止穿墙（两个正交相邻格也必须可通行）
            if dr != 0 and dc != 0:
                if not self.passable((r + dr, c)) or \
                   not self.passable((r, c + dc)):
                    continue
            cost = 1.4142135623730951 if dr != 0 and dc != 0 else 1.0
            out.append((q, cost))
        return out


# --------------------------------------------------------------------------- #
# 启发式
# --------------------------------------------------------------------------- #
def manhattan(a: Pos, b: Pos) -> float:
    return float(abs(a[0] - b[0]) + abs(a[1] - b[1]))


def chebyshev(a: Pos, b: Pos) -> float:
    return float(max(abs(a[0] - b[0]), abs(a[1] - b[1])))


# --------------------------------------------------------------------------- #
# 搜索
# --------------------------------------------------------------------------- #
def _search(grid: Grid, start: Pos, goal: Pos,
            diagonal: bool, heuristic: Optional[Callable]
            ) -> Tuple[Optional[List[Pos]], int]:
    if not grid.passable(start) or not grid.passable(goal):
        raise ValueError("起点或终点不可通行")
    h = (lambda a, b: 0.0) if heuristic is None else heuristic
    frontier = [(h(start, goal), 0.0, start)]
    came_from: Dict[Pos, Optional[Pos]] = {start: None}
    g_score = {start: 0.0}
    expanded = 0

    while frontier:
        _, g, current = heapq.heappop(frontier)
        if g > g_score[current]:
            continue
        expanded += 1
        if current == goal:
            path, node = [], current
            while node is not None:
                path.append(node)
                node = came_from[node]
            return path[::-1], expanded
        for nxt, step in grid.neighbors(current, diagonal):
            ng = g + step
            if ng < g_score.get(nxt, float("inf")):
                g_score[nxt] = ng
                came_from[nxt] = current
                heapq.heappush(frontier, (ng + h(nxt, goal), ng, nxt))
    return None, expanded


def astar(grid: Grid, start: Pos, goal: Pos, diagonal: bool = False
          ) -> Tuple[Optional[List[Pos]], int]:
    h = chebyshev if diagonal else manhattan
    return _search(grid, start, goal, diagonal, h)


def dijkstra(grid: Grid, start: Pos, goal: Pos, diagonal: bool = False
             ) -> Tuple[Optional[List[Pos]], int]:
    return _search(grid, start, goal, diagonal, None)


def path_cost(grid: Grid, path: List[Pos], diagonal: bool) -> float:
    total = 0.0
    for a, b in zip(path, path[1:]):
        dr, dc = abs(a[0] - b[0]), abs(a[1] - b[1])
        total += 1.4142135623730951 if dr and dc else 1.0
    return total


# --------------------------------------------------------------------------- #
# 网格文件与渲染
# --------------------------------------------------------------------------- #
def parse_grid(lines: List[str]) -> Tuple[Grid, Pos, Pos]:
    rows = [ln.rstrip("\n") for ln in lines if ln.strip()]
    height = len(rows)
    width = max(len(r) for r in rows)
    blocked = set()
    start = goal = None
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "#":
                blocked.add((r, c))
            elif ch == "S":
                start = (r, c)
            elif ch == "G":
                goal = (r, c)
    if start is None or goal is None:
        raise ValueError("网格需要 S 和 G")
    return Grid(width, height, blocked), start, goal


def render(grid: Grid, path: Optional[List[Pos]],
           start: Pos, goal: Pos) -> str:
    on_path = set(path or [])
    rows = []
    for r in range(grid.height):
        line = []
        for c in range(grid.width):
            p = (r, c)
            if p == start:
                line.append("S")
            elif p == goal:
                line.append("G")
            elif p in grid.blocked:
                line.append("#")
            elif p in on_path:
                line.append("*")
            else:
                line.append(".")
        rows.append("".join(line))
    return "\n".join(rows)


def load_grid(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return parse_grid(f.readlines())
    except FileNotFoundError:
        raise SystemExit(2)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_solve(args) -> int:
    grid, start, goal = load_grid(args.file)
    path, expanded = astar(grid, start, goal, args.diagonal)
    if path is None:
        print("no path")
        return 1
    dpath, dexp = dijkstra(grid, start, goal, args.diagonal)
    print(render(grid, path, start, goal))
    print(f"path length: {len(path)}  expanded: {expanded}")
    print(f"dijkstra expanded: {dexp}")
    print("optimal:", "yes" if len(path) == len(dpath) else "no")
    return 0


def cmd_demo(args) -> int:
    layout = [
        "S...#....",
        ".#..#..#.",
        ".#..#..#.",
        ".#.....#.",
        ".####..#.",
        ".....#..G",
    ]
    grid, start, goal = parse_grid(layout)
    path, expanded = astar(grid, start, goal)
    _, dexp = dijkstra(grid, start, goal)
    print("4-direction grid:")
    print(render(grid, path, start, goal))
    print(f"astar expanded {expanded} nodes, dijkstra {dexp}")

    open_grid = Grid(5, 5)
    p8, _ = astar(open_grid, (0, 0), (4, 4), diagonal=True)
    p4, _ = astar(open_grid, (0, 0), (4, 4), diagonal=False)
    print(f"\nopen 5x5: 8-dir steps={len(p8)} (diagonal), "
          f"4-dir steps={len(p4)}")

    wall = Grid(3, 3, {(1, 1), (1, 2), (2, 1)})
    none_path, _ = astar(wall, (0, 0), (2, 2))
    print("enclosed goal:", "no path" if none_path is None else "path")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="网格寻路实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("solve", help="求解网格文件")
    ps.add_argument("file")
    ps.add_argument("--diagonal", action="store_true")
    ps.set_defaults(func=cmd_solve)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
