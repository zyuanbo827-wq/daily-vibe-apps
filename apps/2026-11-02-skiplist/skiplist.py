"""skiplist.py -- 零依赖跳表（Skip List）实现。

跳表是一种概率平衡的有序数据结构：在普通链表之上建立多层
"索引"，查找时从最高层快速跳过大量节点，期望 O(log n)。
Redis 有序集合（zset）的底层结构之一就是跳表。

支持：插入、删除、查找、排名、范围查询、有序遍历，附带 CLI。
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import List, Optional, Sequence


class SkipList:
    def __init__(self, max_level: int = 16, p: float = 0.5,
                 seed: Optional[int] = None) -> None:
        if max_level < 1:
            raise ValueError("max_level 至少为 1")
        if not 0.0 < p < 1.0:
            raise ValueError("p 必须在 (0, 1) 之间")
        self.max_level = max_level
        self.p = p
        self._rng = random.Random(seed)
        self._level = 1
        self._size = 0
        # 头哨兵：forward 长度为 max_level，初始全为 None
        self._head = _Node(None, [None] * max_level)

    # ------------------------------------------------------------------ #
    def _random_level(self) -> int:
        """按概率 p 逐层"抛硬币"，返回 1~max_level 的随机层数。"""
        level = 1
        while self._rng.random() < self.p and level < self.max_level:
            level += 1
        return level

    def _find_predecessors(self, value) -> List["_Node"]:
        """返回每层最接近且不大于 value 的前驱节点（update 数组）。"""
        update = [self._head] * self.max_level
        node = self._head
        for lev in range(self._level - 1, -1, -1):
            nxt = node.forward[lev]
            while nxt is not None and nxt.value < value:
                node = nxt
                nxt = node.forward[lev]
            update[lev] = node
        return update

    # ------------------------------------------------------------------ #
    def insert(self, value) -> bool:
        """插入一个值，重复值忽略；返回是否真正插入。"""
        update = self._find_predecessors(value)
        target = update[0].forward[0]
        if target is not None and target.value == value:
            return False

        level = self._random_level()
        if level > self._level:
            # 新出现的高层，前驱就是头哨兵
            for lev in range(self._level, level):
                update[lev] = self._head
            self._level = level

        node = _Node(value, [None] * level)
        for lev in range(level):
            node.forward[lev] = update[lev].forward[lev]
            update[lev].forward[lev] = node
        self._size += 1
        return True

    def delete(self, value) -> bool:
        """删除一个值，不存在返回 False。"""
        update = self._find_predecessors(value)
        target = update[0].forward[0]
        if target is None or target.value != value:
            return False
        for lev in range(self._level):
            if update[lev].forward[lev] is not target:
                break
            update[lev].forward[lev] = target.forward[lev]
        # 收缩当前最高层
        while self._level > 1 and self._head.forward[self._level - 1] is None:
            self._level -= 1
        self._size -= 1
        return True

    def __contains__(self, value) -> bool:
        node = self._head
        for lev in range(self._level - 1, -1, -1):
            nxt = node.forward[lev]
            while nxt is not None and nxt.value < value:
                node = nxt
                nxt = node.forward[lev]
        nxt = node.forward[0]
        return nxt is not None and nxt.value == value

    def rank(self, value) -> int:
        """返回 value 的排名（从 0 开始），不存在返回 -1。"""
        node = self._head
        idx = -1  # 头哨兵不算
        while True:
            node = node.forward[0]
            if node is None:
                return -1
            idx += 1
            if node.value == value:
                return idx
            if node.value > value:
                return -1

    def range_query(self, low, high) -> list:
        """返回 [low, high] 闭区间内的所有值。"""
        if low > high:
            return []
        node = self._head
        for lev in range(self._level - 1, -1, -1):
            nxt = node.forward[lev]
            while nxt is not None and nxt.value < low:
                node = nxt
                nxt = node.forward[lev]
        out = []
        node = node.forward[0]
        while node is not None and node.value <= high:
            out.append(node.value)
            node = node.forward[0]
        return out

    def to_list(self) -> list:
        out = []
        node = self._head.forward[0]
        while node is not None:
            out.append(node.value)
            node = node.forward[0]
        return out

    def level_counts(self) -> List[int]:
        """统计每层（含该层的）节点数，主要用于教学观察。"""
        counts = [0] * self._level
        node = self._head.forward[0]
        while node is not None:
            for lev in range(len(node.forward)):
                counts[lev] += 1
            node = node.forward[0]
        return counts

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        return f"SkipList(level={self._level}, size={self._size})"


class _Node:
    __slots__ = ("value", "forward")

    def __init__(self, value, forward: List[Optional["_Node"]]) -> None:
        self.value = value
        self.forward = forward


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_from(values: Sequence, seed: Optional[int] = None) -> SkipList:
    sl = SkipList(seed=seed)
    for v in values:
        sl.insert(v)
    return sl


def parse_values(text: str) -> list:
    values = []
    for token in text.split():
        try:
            values.append(int(token))
        except ValueError:
            values.append(token)
    return values


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="跳表（Skip List）零依赖实现")
    p.add_argument("file", nargs="?", help="输入文件，每行/空格分隔的值；缺省读标准输入")
    p.add_argument("--seed", type=int, help="随机层数种子（可复现）")
    p.add_argument("--search", help="查找某个值")
    p.add_argument("--range", nargs=2, metavar=("LOW", "HIGH"), help="范围查询")
    p.add_argument("--dump", action="store_true", help="打印有序列表与各层节点数")
    args = p.parse_args(argv)

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    sl = build_from(parse_values(text), seed=args.seed)

    if args.search is not None:
        needle = parse_values(args.search)[0]
        print("found" if needle in sl else "missing")
        print("rank:", sl.rank(needle))
    if args.range:
        low, high = parse_values(args.range[0])[0], parse_values(args.range[1])[0]
        print("range:", sl.range_query(low, high))
    if args.dump or (args.search is None and not args.range):
        print("list:", sl.to_list())
        print("size:", len(sl), "top level:", sl._level)
        print("level counts:", sl.level_counts())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
