"""game-2048：零依赖的 2048 游戏核心（仅 Python 标准库）。

只实现与界面无关的纯逻辑：行滑动合并、四向移动、按种子生成新块、
得分与终局判定。同一种子 + 同一串操作必然得到同一结果，便于测试复现。

命令行：
    python game2048.py --seed 42 --script "l l u r"   # 脚本化跑一串方向
    python game2048.py --seed 42                      # 交互模式（w/a/s/d + q 退出）
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

SIZE = 4
DIRECTIONS = ("left", "right", "up", "down")
# 交互模式下的按键映射
KEY_MAP = {"a": "left", "d": "right", "w": "up", "s": "down",
           "l": "left", "r": "right", "u": "up"}


def slide_row_left(row: List[int]) -> Tuple[List[int], int, bool]:
    """一行向左压缩并合并一次。返回 (新行, 本步得分, 是否发生变化)。"""
    compact = [v for v in row if v != 0]
    merged: List[int] = []
    gained = 0
    i = 0
    while i < len(compact):
        if i + 1 < len(compact) and compact[i] == compact[i + 1]:
            value = compact[i] * 2
            merged.append(value)
            gained += value
            i += 2
        else:
            merged.append(compact[i])
            i += 1
    merged.extend([0] * (SIZE - len(merged)))
    return merged, gained, merged != list(row)


def _reverse(row: List[int]) -> List[int]:
    return list(reversed(row))


def _transpose(board: List[List[int]]) -> List[List[int]]:
    return [list(col) for col in zip(*board)]


def move(board: List[List[int]], direction: str) -> Tuple[List[List[int]], int, bool]:
    """朝指定方向移动整盘。返回 (新棋盘, 得分增量, 是否可移动)。"""
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction: {direction!r}")

    work = [list(r) for r in board]
    if direction in ("up", "down"):
        work = _transpose(work)
    if direction in ("right", "down"):
        work = [_reverse(r) for r in work]

    new_rows: List[List[int]] = []
    total = 0
    moved = False
    for r in work:
        nr, gain, changed = slide_row_left(r)
        new_rows.append(nr)
        total += gain
        moved = moved or changed

    if direction in ("right", "down"):
        new_rows = [_reverse(r) for r in new_rows]
    if direction in ("up", "down"):
        new_rows = _transpose(new_rows)
    return new_rows, total, moved


def empty_cells(board: List[List[int]]) -> List[Tuple[int, int]]:
    return [(r, c) for r in range(SIZE) for c in range(SIZE) if board[r][c] == 0]


def spawn_tile(board: List[List[int]], rng: random.Random) -> bool:
    """在随机空格放一个新块（90% 为 2，10% 为 4）。无空格返回 False。"""
    cells = empty_cells(board)
    if not cells:
        return False
    r, c = rng.choice(cells)
    board[r][c] = 2 if rng.random() < 0.9 else 4
    return True


def available_moves(board: List[List[int]]) -> List[str]:
    return [d for d in DIRECTIONS if move(board, d)[2]]


def is_game_over(board: List[List[int]]) -> bool:
    # 全空棋盘没有块可移动，但语义上并非终局（真实对局中仅瞬态出现）
    has_tile = any(any(row) for row in board)
    return has_tile and not available_moves(board)


def max_tile(board: List[List[int]]) -> int:
    return max(max(r) for r in board)


@dataclass
class Game:
    board: List[List[int]] = field(default_factory=lambda: [[0] * SIZE for _ in range(SIZE)])
    score: int = 0
    moves: int = 0
    rng: random.Random = field(default_factory=lambda: random.Random())

    @classmethod
    def new_game(cls, seed: Optional[int] = None) -> "Game":
        game = cls(rng=random.Random(seed))
        spawn_tile(game.board, game.rng)
        spawn_tile(game.board, game.rng)
        return game

    def step(self, direction: str) -> Tuple[bool, int]:
        """执行一步；有效移动后自动生成新块。返回 (是否有效, 得分增量)。"""
        new_board, gained, moved = move(self.board, direction)
        if not moved:
            return False, 0
        self.board = new_board
        self.score += gained
        self.moves += 1
        spawn_tile(self.board, self.rng)
        return True, gained

    @property
    def over(self) -> bool:
        return is_game_over(self.board)


def render(board: List[List[int]], score: Optional[int] = None) -> str:
    width = max((len(str(v)) for r in board for v in r), default=1)
    width = max(width, 4)
    line = "+" + "+".join(["-" * (width + 2)] * SIZE) + "+"
    out = [] if score is None else [f"score: {score}"]
    out.append(line)
    for r in board:
        cells = "|" + "|".join(f" {str(v).center(width)} " if v else f" {'·'.center(width)} " for v in r) + "|"
        out.append(cells)
        out.append(line)
    return "\n".join(out)


def run_scripted(seed: Optional[int], directions: List[str]) -> Game:
    game = Game.new_game(seed)
    for d in directions:
        game.step(d)
    return game


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Zero-dependency 2048 game core (stdlib only).")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducibility")
    parser.add_argument("--script", type=str, default=None,
                        help="comma/space separated directions (l/r/u/d or names), then exit")
    args = parser.parse_args(argv)

    game = Game.new_game(args.seed)

    if args.script is not None:
        tokens = [t for t in args.script.replace(",", " ").split() if t]
        for t in tokens:
            direction = KEY_MAP.get(t.lower(), t.lower())
            if direction not in DIRECTIONS:
                print(f"error: unknown direction {t!r}", file=sys.stderr)
                return 2
            game.step(direction)
        print(render(game.board, game.score))
        print(f"moves: {game.moves} | best: {max_tile(game.board)} | over: {game.over}")
        return 0

    print(render(game.board, game.score))
    while not game.over:
        try:
            key = input("move [w/a/s/d, q quit]> ").strip().lower()
        except EOFError:
            break
        if key == "q":
            break
        direction = KEY_MAP.get(key, key)
        if direction not in DIRECTIONS:
            print("unknown key, use w/a/s/d or q")
            continue
        valid, gained = game.step(direction)
        if not valid:
            print("that direction changes nothing")
            continue
        print(render(game.board, game.score))
        if gained:
            print(f"+{gained}")
    print(f"game over: {game.over} | final score: {game.score} | best: {max_tile(game.board)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
