"""maze-solver：零依赖迷宫生成与最短路求解（仅 Python 标准库）。

- 用迭代版随机深度优先搜索（randomized DFS）生成"完美迷宫"：任意两格间有且仅有一条路径；
- 用广度优先搜索（BFS）求左上角到右下角的最短路；
- 提供 ASCII 渲染，可叠加路径。固定随机种子时结果完全可复现。

命令行：
    python maze.py --width 15 --height 8 --seed 42
    python maze.py 15 8 --seed 7 --no-path
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import deque
from typing import Dict, List, Optional, Tuple

# 方向位：上/右/下/左；carve 时同时清掉相邻格的反向墙
N, E, S, W = 1, 2, 4, 8
ALL_WALLS = 15
OPPOSITE = {N: S, E: W, S: N, W: E}
STEP = {N: (0, -1), E: (1, 0), S: (0, 1), W: (-1, 0)}
Point = Tuple[int, int]


class Maze:
    def __init__(self, width: int, height: int, seed: Optional[int] = None):
        if width < 2 or height < 2:
            raise ValueError("maze dimensions must both be at least 2")
        self.width = width
        self.height = height
        self.rng = random.Random(seed)
        # walls[y][x] 为该格四面墙的位掩码，初始全封闭
        self.walls: List[List[int]] = [
            [ALL_WALLS for _ in range(width)] for _ in range(height)
        ]
        self._carve()

    def _inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _carve(self) -> None:
        """迭代式随机 DFS 凿墙，生成完美迷宫。"""
        start = (0, 0)
        visited = {start}
        stack: List[Point] = [start]
        while stack:
            x, y = stack[-1]
            directions = [N, E, S, W]
            self.rng.shuffle(directions)
            moved = False
            for direction in directions:
                dx, dy = STEP[direction]
                nx, ny = x + dx, y + dy
                if not self._inside(nx, ny) or (nx, ny) in visited:
                    continue
                self.walls[y][x] &= ~direction
                self.walls[ny][nx] &= ~OPPOSITE[direction]
                visited.add((nx, ny))
                stack.append((nx, ny))
                moved = True
                break
            if not moved:
                stack.pop()

    def open_neighbors(self, x: int, y: int) -> List[Point]:
        """返回与 (x,y) 之间没有墙的相邻格。"""
        if not self._inside(x, y):
            raise ValueError(f"cell ({x},{y}) is out of bounds")
        result: List[Point] = []
        bits = self.walls[y][x]
        for direction, (dx, dy) in STEP.items():
            if bits & direction:
                continue
            nx, ny = x + dx, y + dy
            if self._inside(nx, ny):
                result.append((nx, ny))
        return result

    def bfs(self, start: Point = (0, 0), goal: Optional[Point] = None) -> Dict[Point, Point]:
        """返回 parent 表；goal 默认右下角。"""
        if goal is None:
            goal = (self.width - 1, self.height - 1)
        for px, py in (start, goal):
            if not self._inside(px, py):
                raise ValueError("start/goal out of bounds")
        parent: Dict[Point, Point] = {start: start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in self.open_neighbors(*current):
                if nxt not in parent:
                    parent[nxt] = current
                    queue.append(nxt)
        if goal not in parent:
            raise RuntimeError("goal unreachable (maze is not connected)")
        return parent

    def shortest_path(
        self, start: Point = (0, 0), goal: Optional[Point] = None
    ) -> List[Point]:
        """从 start 到 goal 的最短路径（含两端），长度以格数计。"""
        if goal is None:
            goal = (self.width - 1, self.height - 1)
        parent = self.bfs(start, goal)
        path = [goal]
        while path[-1] != start:
            path.append(parent[path[-1]])
        path.reverse()
        return path

    def render(self, path: Optional[List[Point]] = None,
               start: Point = (0, 0), goal: Optional[Point] = None) -> str:
        if goal is None:
            goal = (self.width - 1, self.height - 1)
        on_path = set(path or [])
        lines: List[str] = []
        for y in range(self.height):
            top = "#"
            mid = ""
            for x in range(self.width):
                top += "--" if self.walls[y][x] & N else "  "
                top += "#"
                mid += "|" if self.walls[y][x] & W else " "
                if (x, y) == start:
                    mid += " S"
                elif (x, y) == goal:
                    mid += " G"
                elif (x, y) in on_path:
                    mid += " *"
                else:
                    mid += "  "
            mid += "|"
            lines.append(top)
            lines.append(mid)
        bottom = "#" + "--#" * self.width
        lines.append(bottom)
        return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a perfect maze and solve it with BFS (stdlib only)."
    )
    parser.add_argument("width", nargs="?", type=int, default=15)
    parser.add_argument("height", nargs="?", type=int, default=8)
    parser.add_argument("--seed", type=int, default=None, help="deterministic seed")
    parser.add_argument("--no-path", action="store_true", help="hide the solution overlay")
    args = parser.parse_args(argv)

    try:
        maze = Maze(args.width, args.height, seed=args.seed)
        path = None if args.no_path else maze.shortest_path()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(maze.render(path=path))
    if path is not None:
        print(f"shortest path: {len(path)} cells, {len(path) - 1} steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
