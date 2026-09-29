"""consistent_hash.py -- 零依赖一致性哈希（Consistent Hashing）实现。

用标准库 hashlib + bisect 实现带虚拟节点的哈希环，支持节点增删、
键归属查询、键分布统计，以及增删节点时的键迁移计划（monotonic
property：加节点只会把键迁到新节点，删节点只影响该节点上的键）。

附带 CLI：内置 demo（分布 + 加/删节点迁移报告）与 keys 文件分布统计。
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


class RingError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# 哈希函数
# --------------------------------------------------------------------------- #
def md5_hash(text: str) -> int:
    """默认哈希：md5 摘要取整数（128 bit 空间）。"""
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest, 16)


HashFunc = Callable[[str], int]


# --------------------------------------------------------------------------- #
# 哈希环
# --------------------------------------------------------------------------- #
class ConsistentHash:
    def __init__(self, replicas: int = 150, hash_func: HashFunc = md5_hash):
        if replicas < 1:
            raise RingError("虚拟节点数 replicas 必须 >= 1")
        self.replicas = replicas
        self._hash = hash_func
        self._ring: List[int] = []              # 有序的虚拟节点哈希
        self._owners: Dict[int, str] = {}       # 虚拟节点哈希 -> 物理节点
        self._nodes: set = set()

    # -- 基础维护 -- #
    def _vnode_key(self, node: str, i: int) -> str:
        return f"{node}#{i}"

    def add_node(self, node: str) -> None:
        if node in self._nodes:
            raise RingError(f"节点已存在：{node}")
        self._nodes.add(node)
        for i in range(self.replicas):
            h = self._hash(self._vnode_key(node, i))
            if h in self._owners:
                raise RingError("虚拟节点哈希冲突，请增加哈希位数或更换函数")
            bisect.insort(self._ring, h)
            self._owners[h] = node

    def remove_node(self, node: str) -> None:
        if node not in self._nodes:
            raise RingError(f"节点不存在：{node}")
        for i in range(self.replicas):
            h = self._hash(self._vnode_key(node, i))
            pos = bisect.bisect_left(self._ring, h)
            if pos < len(self._ring) and self._ring[pos] == h:
                self._ring.pop(pos)
                del self._owners[h]
        self._nodes.remove(node)

    @property
    def nodes(self) -> List[str]:
        return sorted(self._nodes)

    def ring_size(self) -> int:
        return len(self._ring)

    # -- 查询 -- #
    def get_node(self, key: str) -> Optional[str]:
        if not self._ring:
            return None
        h = self._hash(key)
        pos = bisect.bisect_right(self._ring, h)
        if pos == len(self._ring):
            pos = 0
        return self._owners[self._ring[pos]]

    def assign(self, keys) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {n: [] for n in self.nodes}
        for key in keys:
            node = self.get_node(key)
            out[node].append(key)
        return out

    def distribution(self, keys) -> Dict[str, int]:
        counts = Counter()
        total = 0
        for key in keys:
            counts[self.get_node(key)] += 1
            total += 1
        return dict(counts)

    # -- 迁移计划 -- #
    def plan_add_node(self, node: str, keys) -> Tuple[List[Tuple[str, str, str]],
                                                      Dict[str, List[str]]]:
        """返回 (moved, new_assignment)；moved 元素为 (key, old, new)。"""
        before = {key: self.get_node(key) for key in keys}
        self.add_node(node)
        moved = []
        for key, old in before.items():
            new = self.get_node(key)
            if new != old:
                moved.append((key, old, new))
        return moved, self.assign(before.keys())

    def plan_remove_node(self, node: str, keys
                         ) -> Tuple[List[Tuple[str, str, str]], Dict[str, List[str]]]:
        before = {key: self.get_node(key) for key in keys}
        self.remove_node(node)
        moved = []
        for key, old in before.items():
            new = self.get_node(key)
            if new != old:
                moved.append((key, old, new))
        return moved, self.assign(before.keys())


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def make_ring(nodes: List[str], replicas: int = 150,
              hash_func: HashFunc = md5_hash) -> ConsistentHash:
    ring = ConsistentHash(replicas=replicas, hash_func=hash_func)
    for node in nodes:
        ring.add_node(node)
    return ring


def distribution_table(ring: ConsistentHash, keys) -> List[Tuple[str, int, float]]:
    total = len(keys)
    counts = Counter(ring.get_node(k) for k in keys)
    rows = []
    for node in ring.nodes:
        n = counts.get(node, 0)
        pct = 100.0 * n / total if total else 0.0
        rows.append((node, n, pct))
    return rows


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_keys(path: str) -> List[str]:
    if path == "-":
        text = sys.stdin.read()
    else:
        with open(path, "r", encoding="utf-8") as fp:
            text = fp.read()
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def _print_distribution(ring: ConsistentHash, keys) -> None:
    print(f"节点 {len(ring.nodes)} 个 / 虚拟节点 {ring.ring_size()} 个 / "
          f"键 {len(keys)} 个")
    print(f"{'节点':<10}{'键数':>8}{'占比':>10}")
    for node, n, pct in distribution_table(ring, keys):
        print(f"{node:<10}{n:>8}{pct:>9.2f}%")


def _cmd_demo(args: argparse.Namespace) -> int:
    keys = [f"key-{i}" for i in range(args.keys)]
    ring = make_ring(["node-A", "node-B", "node-C"], replicas=args.replicas)

    print("== 初始三节点分布 ==")
    _print_distribution(ring, keys)

    print("\n== 新增 node-D（单调性质：只有键迁入 D）==")
    moved, _ = ring.plan_add_node("node-D", keys)
    onto_d = [m for m in moved if m[2] == "node-D"]
    print(f"迁移键 {len(moved)} 个，其中迁入 node-D {len(onto_d)} 个，"
          f"其余节点间迁移 {len(moved) - len(onto_d)} 个")
    _print_distribution(ring, keys)

    print("\n== 下线 node-B（仅 B 上的键重分配）==")
    before_counts = Counter(ring.get_node(k) for k in keys)
    b_keys = before_counts.get("node-B", 0)
    moved_b, _ = ring.plan_remove_node("node-B", keys)
    print(f"node-B 原有 {b_keys} 个键，实际迁移 {len(moved_b)} 个")
    recv = Counter(m[2] for m in moved_b)
    for node, n in sorted(recv.items()):
        print(f"  -> {node} 接收 {n} 个")
    _print_distribution(ring, keys)
    return 0


def _cmd_dist(args: argparse.Namespace) -> int:
    try:
        keys = _read_keys(args.keys_file)
        ring = make_ring(args.nodes.split(","), replicas=args.replicas)
    except (RingError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, OSError) else 1
    _print_distribution(ring, keys)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="一致性哈希环（虚拟节点 + 迁移计划）")
    sub = p.add_subparsers(dest="command", required=True)

    pd = sub.add_parser("demo", help="内置分布与增删节点迁移演示")
    pd.add_argument("--keys", type=int, default=10000, help="演示键数量")
    pd.add_argument("--replicas", type=int, default=150)
    pd.set_defaults(func=_cmd_demo)

    pc = sub.add_parser("dist", help="统计 keys 文件在节点间的分布")
    pc.add_argument("keys_file", help="每行一个键，- 表示标准输入")
    pc.add_argument("--nodes", required=True, help="逗号分隔的节点名")
    pc.add_argument("--replicas", type=int, default=150)
    pc.set_defaults(func=_cmd_dist)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
