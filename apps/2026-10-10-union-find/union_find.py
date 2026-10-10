"""union_find.py -- 零依赖并查集实验台。

加权 Quick-Union + 路径压缩的并查集（Disjoint Set Union），
并基于它实现：
- 无向图连通分量计数与成环检测
- Kruskal 最小生成树（森林）
CLI 从文件读取边并分析，demo 演示全过程。
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Optional, Tuple


class UnionFind:
    """带权 quick-union + 路径压缩。"""

    def __init__(self, items=()):
        self.parent: Dict = {}
        self.weight: Dict = {}
        for item in items:
            self.add(item)

    def add(self, item) -> None:
        if item not in self.parent:
            self.parent[item] = item
            self.weight[item] = 1

    # ------------------------------------------------------------------ #
    def find(self, item):
        if item not in self.parent:
            raise KeyError(f"未知元素: {item}")
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        # 路径压缩：把路径上所有节点直接挂到根
        node = item
        while self.parent[node] != node:
            nxt = self.parent[node]
            self.parent[node] = root
            node = nxt
        return root

    def union(self, a, b) -> bool:
        """合并；返回是否真的发生了合并（原本不同集合）。"""
        self.add(a)
        self.add(b)
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        # 小集合挂到大集合下面
        if self.weight[ra] < self.weight[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.weight[ra] += self.weight[rb]
        return True

    def connected(self, a, b) -> bool:
        return self.find(a) == self.find(b)

    def size(self, item) -> int:
        return self.weight[self.find(item)]

    @property
    def components(self) -> int:
        return sum(1 for x in self.parent if self.parent[x] == x)


# --------------------------------------------------------------------------- #
# 图分析
# --------------------------------------------------------------------------- #
Edge = Tuple[str, str, float]


def parse_edges(lines) -> Tuple[List[Edge], List[str]]:
    edges: List[Edge] = []
    nodes: List[str] = []

    def note(node: str) -> None:
        if node not in nodes:
            nodes.append(node)

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 2:
            u, v, w = parts[0], parts[1], 1.0
        elif len(parts) == 3:
            u, v = parts[0], parts[1]
            w = float(parts[2])
        else:
            raise ValueError(f"无法解析的边: {raw!r}")
        edges.append((u, v, w))
        note(u)
        note(v)
    return edges, nodes


def analyze(edges: List[Edge], nodes: List[str]):
    """返回 (连通分量数, 是否含环)。"""
    uf = UnionFind(nodes)
    has_cycle = False
    for u, v, _ in edges:
        if not uf.union(u, v):
            has_cycle = True
    return uf.components, has_cycle


def kruskal(edges: List[Edge], nodes: List[str]) -> List[Edge]:
    """Kruskal 最小生成树（图不连通时返回最小生成森林）。"""
    uf = UnionFind(nodes)
    mst: List[Edge] = []
    for u, v, w in sorted(edges, key=lambda e: e[2]):
        if uf.union(u, v):
            mst.append((u, v, w))
    return mst


def total_weight(edges: List[Edge]) -> float:
    return sum(w for _, _, w in edges)


# --------------------------------------------------------------------------- #
# 文件读取
# --------------------------------------------------------------------------- #
def load_edges(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return parse_edges(f)
    except FileNotFoundError:
        raise SystemExit(2)


# --------------------------------------------------------------------------- #
# 预置数据
# --------------------------------------------------------------------------- #
DEMO_LINES = [
    "# 城市与建设成本",
    "Beijing Tianjin 120",
    "Beijing Shijiazhuang 290",
    "Tianjin Jinan 270",
    "Shijiazhuang Jinan 310",
    "Jinan Xuzhou 320",
    "Xuzhou Nanjing 330",
    "Jinan Nanjing 640",
]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_analyze(args) -> int:
    edges, nodes = load_edges(args.file)
    comps, cycle = analyze(edges, nodes)
    print(f"nodes: {len(nodes)}  edges: {len(edges)}")
    print(f"connected components: {comps}")
    print("cycle:", "yes" if cycle else "no")
    if args.mst:
        mst = kruskal(edges, nodes)
        print(f"mst edges: {len(mst)}  total weight: {total_weight(mst):g}")
        for u, v, w in mst:
            print(f"  {u} -- {v}  {w:g}")
    return 0


def cmd_demo(args) -> int:
    edges, nodes = parse_edges(DEMO_LINES)
    print("union-find basics:")
    uf = UnionFind(range(6))
    uf.union(0, 1)
    uf.union(2, 3)
    uf.union(1, 3)
    print(f"  find(0)==find(3): {uf.connected(0, 3)}  components: {uf.components}")

    comps, cycle = analyze(edges, nodes)
    print(f"\ncity graph: components={comps} cycle={'yes' if cycle else 'no'}")
    mst = kruskal(edges, nodes)
    print(f"kruskal mst ({len(mst)} edges, weight {total_weight(mst):g}):")
    for u, v, w in mst:
        print(f"  {u} -- {v}  {w:g}")

    # 成环检测小例
    cyc_edges, cyc_nodes = parse_edges(["a b 1", "b c 1", "c a 1"])
    _, has_cycle = analyze(cyc_edges, cyc_nodes)
    print("triangle cycle:", "detected" if has_cycle else "none")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="并查集实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("analyze", help="分析边表文件")
    pa.add_argument("file")
    pa.add_argument("--mst", action="store_true", help="同时求 Kruskal 最小生成树")
    pa.set_defaults(func=cmd_analyze)

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
