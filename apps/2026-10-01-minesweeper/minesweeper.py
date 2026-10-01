"""minesweeper.py -- 零依赖扫雷游戏（可复现、首击安全）。

核心逻辑与渲染/交互分离：
  Board -- 棋盘状态：布雷（首击安全，排除首击 3x3）、数字计数、
           泛洪展开、插旗、和弦展开（chord）、胜负判定
  文本渲染 + CLI（交互式 play 与脚本化 demo）
随机布雷可用种子复现，测试中可直接注入雷位。
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple


class GameError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# 棋盘
# --------------------------------------------------------------------------- #
@dataclass
class Cell:
    mine: bool = False
    revealed: bool = False
    flagged: bool = False
    count: int = 0


class Board:
    def __init__(self, rows: int = 9, cols: int = 9, mines: int = 10,
                 seed: Optional[int] = None,
                 mine_positions: Optional[Set[Tuple[int, int]]] = None):
        if rows < 1 or cols < 1:
            raise GameError("棋盘尺寸必须为正")
        if mines < 0:
            raise GameError("雷数不能为负")
        if mines > rows * cols - 1:
            raise GameError("雷数过多，至少要留一个安全格")
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.seed = seed
        self.grid: List[List[Cell]] = [
            [Cell() for _ in range(cols)] for _ in range(rows)]
        self.status = "ready"          # ready / playing / won / lost
        self.started = False
        self.flags = 0
        if mine_positions is not None:
            if len(mine_positions) != mines:
                raise GameError("注入的雷位数量与 mines 不一致")
            for r, c in mine_positions:
                self._validate(r, c)
                self.grid[r][c].mine = True
            self._compute_counts()
            self.started = True
            self.status = "playing"

    # -- 工具 -- #
    def _validate(self, r: int, c: int) -> None:
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            raise GameError(f"坐标越界：({r},{c})")

    def neighbors(self, r: int, c: int):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    yield nr, nc

    def _place_mines(self, safe_r: int, safe_c: int) -> None:
        safe = {(safe_r + dr, safe_c + dc)
                for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                if 0 <= safe_r + dr < self.rows
                and 0 <= safe_c + dc < self.cols}
        candidates = [(r, c) for r in range(self.rows)
                      for c in range(self.cols) if (r, c) not in safe]
        rng = random.Random(self.seed)
        rng.shuffle(candidates)
        if len(candidates) < self.mines:
            # 小棋盘放不下 3x3 安全区时，退化为只保证首击格安全
            candidates = [(r, c) for r in range(self.rows)
                          for c in range(self.cols) if (r, c) != (safe_r, safe_c)]
            rng.shuffle(candidates)
        for r, c in candidates[:self.mines]:
            self.grid[r][c].mine = True
        self._compute_counts()
        self.started = True
        self.status = "playing"

    def _compute_counts(self) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if cell.mine:
                    continue
                cell.count = sum(1 for nr, nc in self.neighbors(r, c)
                                 if self.grid[nr][nc].mine)

    # -- 操作 -- #
    def reveal(self, r: int, c: int) -> int:
        """展开格子，返回本次新展开的格子数；踩雷时 status=lost。"""
        self._validate(r, c)
        if self.status in ("won", "lost"):
            return 0
        cell = self.grid[r][c]
        if not self.started:
            self._place_mines(r, c)
            cell = self.grid[r][c]
        if cell.flagged or cell.revealed:
            return 0
        if cell.mine:
            cell.revealed = True
            self.status = "lost"
            self._reveal_all_mines()
            return 1
        return self._flood(r, c)

    def _flood(self, r: int, c: int) -> int:
        stack = [(r, c)]
        opened = 0
        while stack:
            cr, cc = stack.pop()
            cell = self.grid[cr][cc]
            if cell.revealed or cell.flagged or cell.mine:
                continue
            cell.revealed = True
            opened += 1
            if cell.count == 0:
                for nr, nc in self.neighbors(cr, cc):
                    nxt = self.grid[nr][nc]
                    if not nxt.revealed and not nxt.flagged and not nxt.mine:
                        stack.append((nr, nc))
        self._check_win()
        return opened

    def toggle_flag(self, r: int, c: int) -> bool:
        self._validate(r, c)
        if self.status in ("won", "lost"):
            return False
        cell = self.grid[r][c]
        if cell.revealed:
            return False
        cell.flagged = not cell.flagged
        self.flags += 1 if cell.flagged else -1
        return cell.flagged

    def chord(self, r: int, c: int) -> int:
        """和弦：已展开数字周围旗数等于数字时，展开其余相邻格。

        若旗标位置错误（标在非雷格上），会在展开时踩雷判负。
        返回新展开格子数。
        """
        self._validate(r, c)
        cell = self.grid[r][c]
        if not cell.revealed or cell.count == 0:
            return 0
        flagged = sum(1 for nr, nc in self.neighbors(r, c)
                      if self.grid[nr][nc].flagged)
        if flagged != cell.count:
            return 0
        opened = 0
        for nr, nc in self.neighbors(r, c):
            nxt = self.grid[nr][nc]
            if not nxt.revealed and not nxt.flagged:
                if nxt.mine:
                    nxt.revealed = True
                    self.status = "lost"
                    self._reveal_all_mines()
                    return opened + 1
                opened += self._flood(nr, nc)
        return opened

    def _reveal_all_mines(self) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c].mine:
                    self.grid[r][c].revealed = True

    def _check_win(self) -> None:
        unopened_safe = sum(
            1 for r in range(self.rows) for c in range(self.cols)
            if not self.grid[r][c].mine and not self.grid[r][c].revealed)
        if unopened_safe == 0:
            self.status = "won"

    def unrevealed_safe(self) -> int:
        return sum(
            1 for r in range(self.rows) for c in range(self.cols)
            if not self.grid[r][c].mine and not self.grid[r][c].revealed)


# --------------------------------------------------------------------------- #
# 文本渲染
# --------------------------------------------------------------------------- #
def render(board: Board, reveal_all: bool = False) -> str:
    head = "    " + "".join(f"{c % 10:>3}" for c in range(board.cols))
    sep = "    " + "-" * (board.cols * 3)
    lines = [head, sep]
    for r in range(board.rows):
        row = [f"{r:>2} |"]
        for c in range(board.cols):
            cell = board.grid[r][c]
            if cell.flagged:
                ch = "F"
            elif not cell.revealed:
                ch = "." if reveal_all and cell.mine else "#"
            elif cell.mine:
                ch = "*"
            elif cell.count == 0:
                ch = " "
            else:
                ch = str(cell.count)
            row.append(f"{ch:>3}")
        lines.append("".join(row))
    lines.append(f"状态：{board.status}，旗 {board.flags}/{board.mines}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_rc(parts) -> Tuple[int, int]:
    if len(parts) != 3:
        raise GameError("用法：<r|f|c> <row> <col>")
    return int(parts[1]), int(parts[2])


def _cmd_demo(args: argparse.Namespace) -> int:
    board = Board(9, 9, 10, seed=args.seed)
    print("== 新棋盘（种子 %d），首击 (4,4) ==" % args.seed)
    board.reveal(4, 4)
    print(render(board))

    script = ["r 0 0", "f 0 1", "r 8 8", "r 4 3"]
    for raw in script:
        parts = raw.split()
        r, c = _parse_rc(parts)
        if parts[0] == "r":
            board.reveal(r, c)
        elif parts[0] == "f":
            board.toggle_flag(r, c)
        print(f"\n== {raw} ==")
        print(render(board))
        if board.status in ("won", "lost"):
            print("对局结束：", board.status)
            return 0
    return 0


def _cmd_play(args: argparse.Namespace) -> int:
    board = Board(args.rows, args.cols, args.mines, seed=args.seed)
    print(render(board))
    print("命令：r <row> <col> 展开 | f <row> <col> 插旗 | "
          "c <row> <col> 和弦 | q 退出")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            return 0
        if not line:
            continue
        if line == "q":
            return 0
        parts = line.split()
        try:
            r, c = _parse_rc(parts)
            if parts[0] == "r":
                board.reveal(r, c)
            elif parts[0] == "f":
                board.toggle_flag(r, c)
            elif parts[0] == "c":
                board.chord(r, c)
            else:
                print("未知命令")
                continue
        except (GameError, ValueError) as exc:
            print(f"error: {exc}")
            continue
        print(render(board))
        if board.status in ("won", "lost"):
            print("对局结束：", board.status)
            return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="扫雷（首击安全 / 种子可复现）")
    sub = p.add_subparsers(dest="command", required=True)

    pd = sub.add_parser("demo", help="脚本化对局演示")
    pd.add_argument("--seed", type=int, default=20261001)
    pd.set_defaults(func=_cmd_demo)

    pp = sub.add_parser("play", help="交互式对局")
    pp.add_argument("--rows", type=int, default=9)
    pp.add_argument("--cols", type=int, default=9)
    pp.add_argument("--mines", type=int, default=10)
    pp.add_argument("--seed", type=int, default=None)
    pp.set_defaults(func=_cmd_play)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
