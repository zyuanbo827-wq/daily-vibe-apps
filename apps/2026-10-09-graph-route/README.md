# 2026-10-09 · graph-route —— 图最短路径实验台

加权有向/无向图上的三种最短路径算法对比实验台：堆优化的
Dijkstra、支持负权边与负权环检测的 Bellman-Ford、以及全源
Floyd-Warshall。图用 JSON 定义，CLI 可查询两点路径，demo
自动核对三种算法结果一致性。零三方依赖。

## 功能

- **图模型**：有向/无向加权图；无向边自动添加反向邻接；
  节点与边的增删、边表列举（无向边去重）
- **Dijkstra**：`heapq` 堆优化，O((V+E)log V)；输出距离表与
  前驱表，支持路径重建；负权边直接报错
- **Bellman-Ford**：逐轮松弛全部有向邻接边，支持负权边；
  提前收敛即停止；再松弛一轮仍能改进则判定负权环
- **Floyd-Warshall**：动态规划求全源最短距离，对角线为 0，
  对角线变负即存在负权环
- **路径查询**：不可达返回空路径（CLI 退出码 1）；未知节点、
  负权环等以 GraphError 报错（CLI 退出码 2）

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置演示：三算法距离对比、负权边、负权环检测
python graph_route.py demo

# 查询 JSON 图中两点最短路径（可选 dijkstra / bellman）
python graph_route.py shortest sample_graph.json Beijing Nanjing
python graph_route.py shortest sample_graph.json Beijing Nanjing \
  --algorithm bellman
```

作为库使用：

```python
from graph_route import Graph
g = Graph(directed=False)
g.add_edge("A", "B", 4)
dist, path = g.shortest("A", "B")
g.floyd_warshall()
```

## 实现要点

1. **松弛集合必须是全部有方向的邻接边**：无向图在邻接表里有
  两个方向，但 `edges()` 为展示做了去重。Bellman-Ford 若误用
  去重边表，就只松弛一个方向——这是开发中实际踩到的 bug：
  无向图上 Bellman 结果整体偏大一圈。修复方式是直接遍历
  `adj` 构造 `(u,v,w)`，与 Dijkstra 的松弛面保持一致。
2. **Dijkstra 的惰性删除堆**：堆中允许同一节点的旧条目，
  弹出时用 `d > dist[u]` 跳过；不必显式 decrease-key。
3. **前驱表与路径重建**：只有真正收紧距离时才记录前驱，
  从目标沿前驱回溯再反转即得路径；不可达时距离为 INF。
4. **Bellman-Ford 的两个边界**：连续一轮无改进可提前结束；
  V-1 轮之后再扫描，仍能收紧说明存在负权环（最短路径无定义）。
5. **Floyd-Warshall 的中转点在外层**：`dist[i][j]` 经 k 中转，
  k 必须是最外层循环；`dist[i][k]` 为 INF 时直接跳过，
  避免 INF 参与加法。

## 测试

```bash
python -m unittest test_graph_route -v
```

共 16 个用例：有向/无向邻接与边去重；Dijkstra 六节点距离
（手工核对 A0/B3/C2/D8/E10/F13）、A→F 路径、未知节点、
负权拒绝、不可达；Bellman 与 Dijkstra 一致、负权边 b=1、
负权环、Floyd 一致与对角线；样例图北京→南京 1030 路径；
以及 demo（AGREE + detected）、两种算法 CLI、不可达退出码 1、
缺文件退出码 2 的子进程冒烟。

开发中修复了一个真实缺陷：Bellman-Ford 误用去重 `edges()`，
在无向图上只松弛单向边导致结果错误（B 由 3 变 4 等），
改为遍历全部有向邻接边后三算法完全一致。
