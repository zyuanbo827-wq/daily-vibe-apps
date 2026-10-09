"""graph_route.py -- 零依赖图最短路径实验台。

加权有向/无向图，提供三种最短路径算法：
- Dijkstra（非负权，堆优化）+ 前驱表与路径重建
- Bellman-Ford（支持负权边，检测负权环）
- Floyd-Warshall（全源最短路径）
CLI 从 JSON 装载图并查询，demo 对比三种算法结果一致性。
"""

from __future__ import annotations

import argparse
import heapq
import json
import sys
from typing import Dict, List, Optional, Tuple

INF = float("inf")


class GraphError(ValueError):
    pass


class Graph:
    def __init__(self, directed: bool = True):
        self.directed = directed
        self.adj: Dict[str, Dict[str, float]] = {}

    def add_node(self, node: str) -> None:
        self.adj.setdefault(node, {})

    def add_edge(self, src: str, dst: str, weight: float) -> None:
        self.add_node(src)
        self.add_node(dst)
        self.adj[src][dst] = weight
        if not self.directed:
            self.adj[dst][src] = weight

    @property
    def nodes(self) -> List[str]:
        return list(self.adj)

    def edges(self) -> List[Tuple[str, str, float]]:
        out = []
        for u in self.adj:
            for v, w in self.adj[u].items():
                if not self.directed and u > v:
                    continue
                out.append((u, v, w))
        return out

    # ------------------------------------------------------------------ #
    # Dijkstra
    # ------------------------------------------------------------------ #
    def dijkstra(self, source: str):
        if source not in self.adj:
            raise GraphError(f"未知节点: {source}")
        if any(w < 0 for _, _, w in self.edges()):
            raise GraphError("Dijkstra 不支持负权边")
        dist = {n: INF for n in self.adj}
        prev: Dict[str, Optional[str]] = {n: None for n in self.adj}
        dist[source] = 0
        pq = [(0.0, source)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for v, w in self.adj[u].items():
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    # ------------------------------------------------------------------ #
    # Bellman-Ford
    # ------------------------------------------------------------------ #
    def bellman_ford(self, source: str):
        if source not in self.adj:
            raise GraphError(f"未知节点: {source}")
        dist = {n: INF for n in self.adj}
        prev: Dict[str, Optional[str]] = {n: None for n in self.adj}
        dist[source] = 0
        # 松弛集合是全部有方向的邻接边；无向图两个方向都要松弛，
        # 不能用去重后的 edges()（那只含一个方向）
        directed_edges = [(u, v, w) for u in self.adj
                          for v, w in self.adj[u].items()]
        for _ in range(len(self.adj) - 1):
            changed = False
            for u, v, w in directed_edges:
                if dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    prev[v] = u
                    changed = True
            if not changed:
                break
        for u, v, w in directed_edges:
            if dist[u] + w < dist[v]:
                raise GraphError("检测到负权环")
        return dist, prev

    # ------------------------------------------------------------------ #
    # Floyd-Warshall
    # ------------------------------------------------------------------ #
    def floyd_warshall(self) -> Dict[str, Dict[str, float]]:
        dist = {u: {v: INF for v in self.adj} for u in self.adj}
        for u in self.adj:
            dist[u][u] = 0
            for v, w in self.adj[u].items():
                dist[u][v] = w
        for k in self.adj:
            for i in self.adj:
                dik = dist[i][k]
                if dik == INF:
                    continue
                for j in self.adj:
                    nd = dik + dist[k][j]
                    if nd < dist[i][j]:
                        dist[i][j] = nd
        if any(dist[u][u] < 0 for u in self.adj):
            raise GraphError("检测到负权环")
        return dist

    # ------------------------------------------------------------------ #
    def shortest(self, source: str, target: str,
                 algorithm: str = "dijkstra") -> Tuple[float, List[str]]:
        solver = {"dijkstra": self.dijkstra,
                  "bellman": self.bellman_ford}[algorithm]
        dist, prev = solver(source)
        if dist[target] == INF:
            return INF, []
        path, node = [], target
        while node is not None:
            path.append(node)
            node = prev[node]
        return dist[target], path[::-1]


# --------------------------------------------------------------------------- #
# JSON 装载
# --------------------------------------------------------------------------- #
def from_dict(data: dict) -> Graph:
    g = Graph(directed=data.get("directed", True))
    for node in data.get("nodes", []):
        g.add_node(node)
    for edge in data.get("edges", []):
        if len(edge) == 2:
            u, v = edge
            w = 1
        else:
            u, v, w = edge
        g.add_edge(u, v, float(w))
    return g


def load_graph(path: str) -> Graph:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return from_dict(json.load(f))
    except FileNotFoundError:
        raise SystemExit(2)


# --------------------------------------------------------------------------- #
# 预置图
# --------------------------------------------------------------------------- #
def demo_graph() -> Graph:
    data = {
        "directed": False,
        "nodes": ["A", "B", "C", "D", "E", "F"],
        "edges": [
            ["A", "B", 4], ["A", "C", 2], ["B", "C", 1],
            ["B", "D", 5], ["C", "D", 8], ["C", "E", 10],
            ["D", "E", 2], ["D", "F", 6], ["E", "F", 3],
        ],
    }
    return from_dict(data)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_shortest(args) -> int:
    g = load_graph(args.file)
    dist, path = g.shortest(args.source, args.target, args.algorithm)
    if not path:
        print("unreachable")
        return 1
    print(f"distance: {dist:g}")
    print("path:", " -> ".join(path))
    return 0


def cmd_demo(args) -> int:
    g = demo_graph()
    d_dij, p_dij = g.dijkstra("A")
    d_bf, _ = g.bellman_ford("A")
    d_fw = g.floyd_warshall()

    print("distances from A:")
    for node in sorted(g.nodes):
        print(f"  {node}: dijkstra={d_dij[node]:g} bellman={d_bf[node]:g} "
              f"floyd={d_fw['A'][node]:g}")
    agree = all(d_dij[n] == d_bf[n] == d_fw["A"][n] for n in g.nodes)
    print("algorithms", "AGREE" if agree else "DIFFER")

    dist, path = g.shortest("A", "F")
    print(f"\nA -> F: {dist:g} via {' -> '.join(path)}")

    neg = Graph(directed=True)
    neg.add_edge("s", "a", 4)
    neg.add_edge("s", "b", 5)
    neg.add_edge("a", "b", -3)
    d, _ = neg.bellman_ford("s")
    print("negative edge s->... b =", f"{d['b']:g}", "(bellman-ford)")

    cyc = Graph(directed=True)
    cyc.add_edge("x", "y", 1)
    cyc.add_edge("y", "x", -2)
    try:
        cyc.bellman_ford("x")
    except GraphError:
        print("negative cycle x<->y: detected")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="图最短路径实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("shortest", help="查询两点最短路径")
    ps.add_argument("file")
    ps.add_argument("source")
    ps.add_argument("target")
    ps.add_argument("--algorithm", choices=("dijkstra", "bellman"),
                    default="dijkstra")
    ps.set_defaults(func=cmd_shortest)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except GraphError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
