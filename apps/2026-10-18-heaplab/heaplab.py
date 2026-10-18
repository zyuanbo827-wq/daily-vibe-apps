"""heaplab.py -- 零依赖二叉堆实验台。

实现：
- 二叉小顶堆 / 大顶堆（数组存储，上浮下沉）
- 堆排序 heapsort
- top-k：用定长堆在 O(n log k) 内求第 k 大/小
- 多路有序序列归并 merge_sorted
- 双堆维护数据流中位数 running_median
附带 CLI：sort / topk / median / demo。
"""

from __future__ import annotations

import argparse
import heapq
import sys
from typing import Iterable, List, Optional


# --------------------------------------------------------------------------- #
# 二叉堆（教学实现，不依赖 heapq）
# --------------------------------------------------------------------------- #
class BinaryHeap:
    """小顶堆：_better(a, b) 表示 a 应排在 b 前面。"""

    def __init__(self, key=None):
        self._h: List = []
        self._key = key

    def _better(self, a, b) -> bool:
        ka = self._key(a) if self._key else a
        kb = self._key(b) if self._key else b
        return ka < kb

    def __len__(self) -> int:
        return len(self._h)

    def is_empty(self) -> bool:
        return not self._h

    def peek(self):
        if not self._h:
            raise IndexError("peek from empty heap")
        return self._h[0]

    @staticmethod
    def _parent(i: int) -> int:
        return (i - 1) // 2

    @staticmethod
    def _children(i: int) -> tuple:
        return 2 * i + 1, 2 * i + 2

    def _swap(self, i: int, j: int) -> None:
        self._h[i], self._h[j] = self._h[j], self._h[i]

    def push(self, item) -> None:
        self._h.append(item)
        self._sift_up(len(self._h) - 1)

    def _sift_up(self, i: int) -> None:
        while i > 0:
            p = self._parent(i)
            if self._better(self._h[i], self._h[p]):
                self._swap(i, p)
                i = p
            else:
                break

    def pop(self):
        if not self._h:
            raise IndexError("pop from empty heap")
        top = self._h[0]
        last = self._h.pop()
        if self._h:
            self._h[0] = last
            self._sift_down(0)
        return top

    def _sift_down(self, i: int) -> None:
        n = len(self._h)
        while True:
            l, r = self._children(i)
            best = i
            if l < n and self._better(self._h[l], self._h[best]):
                best = l
            if r < n and self._better(self._h[r], self._h[best]):
                best = r
            if best == i:
                break
            self._swap(i, best)
            i = best

    @classmethod
    def heapify(cls, items: Iterable, key=None) -> "BinaryHeap":
        heap = cls(key=key)
        heap._h = list(items)
        for i in range(len(heap._h) // 2 - 1, -1, -1):
            heap._sift_down(i)
        return heap


# --------------------------------------------------------------------------- #
# 堆排序
# --------------------------------------------------------------------------- #
def heapsort(items: Iterable, key=None, reverse: bool = False) -> List:
    """自实现小顶堆堆排序；reverse=True 时逆序。"""
    heap = BinaryHeap.heapify(items, key=key)
    out = []
    while not heap.is_empty():
        out.append(heap.pop())
    if reverse:
        out.reverse()
    return out


# --------------------------------------------------------------------------- #
# top-k
# --------------------------------------------------------------------------- #
def _lt_key(heap: BinaryHeap, a, b) -> bool:
    """a 严格小于 b（考虑 key）。"""
    ka = heap._key(a) if heap._key else a
    kb = heap._key(b) if heap._key else b
    return ka < kb


def top_k_largest(items: Iterable, k: int, key=None) -> List:
    """小顶堆维护当前最大的 k 个元素，结果降序返回。"""
    if k < 0:
        raise ValueError("k 必须是非负整数")
    if k == 0:
        return []
    heap = BinaryHeap(key=key)
    for item in items:
        if len(heap) < k:
            heap.push(item)
        elif _lt_key(heap, heap.peek(), item):
            heap.pop()
            heap.push(item)
    return heapsort(heap._h, key=key, reverse=True)


def top_k_smallest(items: Iterable, k: int, key=None) -> List:
    """大顶堆维护当前最小的 k 个元素，结果升序返回。"""
    if k < 0:
        raise ValueError("k 必须是非负整数")
    if k == 0:
        return []
    heap = BinaryHeap(
        key=(lambda x: -key(x)) if key else (lambda x: -x)
    )
    for item in items:
        if len(heap) < k:
            heap.push(item)
        else:
            worst = heap.peek()
            kw = key(worst) if key else worst
            kv = key(item) if key else item
            if kv < kw:
                heap.pop()
                heap.push(item)
    return heapsort(heap._h, key=key)


# --------------------------------------------------------------------------- #
# 多路归并（用 heapq 做最小堆，避免重复造轮子于业务层）
# --------------------------------------------------------------------------- #
def merge_sorted(lists: Iterable[Iterable]) -> List:
    """归并多个已升序排列的序列，输出全局升序。"""
    iters = [iter(it) for it in lists]
    heap = []
    for idx, it in enumerate(iters):
        for first in it:
            heapq.heappush(heap, (first, idx))
            break
    out = []
    while heap:
        value, idx = heapq.heappop(heap)
        out.append(value)
        for nxt in iters[idx]:
            heapq.heappush(heap, (nxt, idx))
            break
    return out


# --------------------------------------------------------------------------- #
# 双堆维护数据流中位数
# --------------------------------------------------------------------------- #
class RunningMedian:
    """low 为大顶堆（存负值）、high 为小顶堆；O(log n) 插入、O(1) 中位数。"""

    def __init__(self):
        self.low: List[float] = []
        self.high: List[float] = []

    def add(self, x: float) -> None:
        heapq.heappush(self.low, -x)
        moved = -heapq.heappop(self.low)
        heapq.heappush(self.high, moved)
        if len(self.high) > len(self.low):
            heapq.heappush(self.low, -heapq.heappop(self.high))

    def median(self) -> Optional[float]:
        if not self.low:
            return None
        if len(self.low) > len(self.high):
            return -self.low[0]
        return (-self.low[0] + self.high[0]) / 2


def running_median(values: Iterable[float]) -> List[float]:
    rm = RunningMedian()
    medians = []
    for v in values:
        rm.add(v)
        medians.append(rm.median())
    return medians


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_numbers(file=None) -> List[float]:
    if file:
        text = open(file, "r", encoding="utf-8").read()
    else:
        text = sys.stdin.read()
    nums = []
    for token in text.replace(",", " ").split():
        if token.strip():
            nums.append(float(token))
    return nums


def cmd_sort(args) -> int:
    nums = _read_numbers(args.file)
    out = heapsort(nums, reverse=args.desc)
    print(" ".join(_fmt(x) for x in out))
    return 0


def cmd_topk(args) -> int:
    nums = _read_numbers(args.file)
    out = (top_k_largest(nums, args.k) if args.largest
           else top_k_smallest(nums, args.k))
    print(" ".join(_fmt(x) for x in out))
    return 0


def cmd_median(args) -> int:
    nums = _read_numbers(args.file)
    for m in running_median(nums):
        print(_fmt(m))
    return 0


def cmd_demo(args) -> int:
    data = [5, 1, 9, 3, 7, 2, 8, 4, 6, 0]
    print("data:       ", data)
    print("heapsort:   ", heapsort(data))
    print("top 3 large:", top_k_largest(data, 3))
    print("top 3 small:", top_k_smallest(data, 3))
    streams = [[1, 4, 7], [2, 5, 8], [3, 6, 9]]
    print("merged:     ", merge_sorted(streams))
    medians = running_median([2, 1, 5, 7, 2, 0, 5])
    print("medians:    ", [_fmt(x) for x in medians])

    words = ["banana", "apple", "fig", "cherry", "date"]
    print("top 2 by length:",
          top_k_largest(words, 2, key=len))
    return 0


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="二叉堆实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("sort", help="堆排序")
    ps.add_argument("file", nargs="?")
    ps.add_argument("--desc", action="store_true")
    ps.set_defaults(func=cmd_sort)

    pt = sub.add_parser("topk", help="取前 k 大/小")
    pt.add_argument("k", type=int)
    pt.add_argument("file", nargs="?")
    pt.add_argument("--largest", action="store_true", help="前 k 大（默认前 k 小）")
    pt.set_defaults(func=cmd_topk)

    pm = sub.add_parser("median", help="逐元素输出运行中位数")
    pm.add_argument("file", nargs="?")
    pm.set_defaults(func=cmd_median)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
