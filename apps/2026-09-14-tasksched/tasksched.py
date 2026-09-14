"""tasksched：零依赖的 DAG 任务调度器（仅 Python 标准库）。

- Kahn 拓扑排序（用最小堆打破并列，结果确定）；
- 环检测与未知依赖检查，报错给出涉及节点；
- 分层（同一层任务互不依赖，可并行）；
- 给定每任务工期，计算最早开始/完成时间、项目工期与关键路径。

任务用 JSON 描述：
    {"A": {"deps": [], "duration": 3},
     "B": {"deps": ["A"], "duration": 2}}

命令行：
    python tasksched.py order tasks.json
    python tasksched.py levels tasks.json
    python tasksched.py schedule tasks.json
"""
from __future__ import annotations

import argparse
import heapq
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


class CycleError(ValueError):
    """图中存在环时抛出，携带无法排入拓扑序的节点。"""


class UnknownDependencyError(ValueError):
    """任务依赖了一个未定义的节点时抛出。"""


TaskMap = Dict[str, Dict]


def normalize(graph: TaskMap) -> Dict[str, Tuple[List[str], int]]:
    """校验并归一化为 name -> (排序后的依赖列表, 工期)。"""
    result: Dict[str, Tuple[List[str], int]] = {}
    for name, spec in graph.items():
        spec = spec or {}
        deps = list(spec.get("deps", []))
        unknown = [d for d in deps if d not in graph]
        if unknown:
            raise UnknownDependencyError(
                f"task {name!r} depends on undefined task(s): {', '.join(unknown)}"
            )
        duration = spec.get("duration", 1)
        if not isinstance(duration, (int, float)) or duration < 0:
            raise ValueError(f"task {name!r} has invalid duration: {duration!r}")
        result[name] = (sorted(deps), duration)
    return result


def topo_sort(graph: TaskMap) -> List[str]:
    """确定性 Kahn 拓扑排序：并列就绪节点按名字升序。"""
    g = normalize(graph)
    indegree = {name: len(deps) for name, (deps, _) in g.items()}
    dependents: Dict[str, List[str]] = {name: [] for name in g}
    for name, (deps, _) in g.items():
        for d in deps:
            dependents[d].append(name)

    ready = [name for name, deg in indegree.items() if deg == 0]
    heapq.heapify(ready)
    order: List[str] = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for child in dependents[name]:
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)

    if len(order) != len(g):
        stuck = sorted(n for n, deg in indegree.items() if deg > 0)
        raise CycleError(f"cycle detected; tasks left unresolved: {', '.join(stuck)}")
    return order


def levels(graph: TaskMap) -> List[List[str]]:
    """按依赖深度分层，同层任务无依赖关系，可并行；每层内部名字升序。"""
    g = normalize(graph)
    order = topo_sort(graph)
    level_of: Dict[str, int] = {}
    for name in order:
        deps, _ = g[name]
        level_of[name] = 0 if not deps else 1 + max(level_of[d] for d in deps)
    buckets: Dict[int, List[str]] = {}
    for name, lv in level_of.items():
        buckets.setdefault(lv, []).append(name)
    return [sorted(buckets[lv]) for lv in sorted(buckets)]


@dataclass
class ScheduleItem:
    name: str
    start: float
    finish: float
    predecessors: List[str]


@dataclass
class Schedule:
    items: Dict[str, ScheduleItem]
    total_duration: float
    critical_path: List[str]

    def ordered(self) -> List[ScheduleItem]:
        return [self.items[n] for n in topo_order_from_items(self.items)]


def topo_order_from_items(items: Dict[str, ScheduleItem]) -> List[str]:
    return sorted(items, key=lambda n: (items[n].start, n))


def schedule(graph: TaskMap) -> Schedule:
    """ASAP 调度：ES = max(依赖 EF)，并回溯关键路径。"""
    g = normalize(graph)
    order = topo_sort(graph)
    items: Dict[str, ScheduleItem] = {}
    for name in order:
        deps, duration = g[name]
        start = max((items[d].finish for d in deps), default=0)
        items[name] = ScheduleItem(name, start, start + duration, deps)

    if not items:
        return Schedule({}, 0, [])
    total = max(it.finish for it in items.values())
    ends = [n for n, it in items.items() if it.finish == total]
    end = sorted(ends)[0]

    # 从终点沿"决定其开始时间"的依赖回溯，即关键路径
    path = [end]
    cur = end
    while items[cur].predecessors:
        preds = items[cur].predecessors
        need = items[cur].start
        critical_preds = sorted(d for d in preds if items[d].finish == need)
        cur = critical_preds[0]
        path.append(cur)
    path.reverse()
    return Schedule(items, total, path)


def load_graph(path: str) -> TaskMap:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("task file must be a JSON object mapping name -> spec")
    return data


def format_schedule(sched: Schedule) -> str:
    lines = ["task            start  finish  deps"]
    for it in sched.ordered():
        deps = ",".join(it.predecessors) if it.predecessors else "-"
        lines.append(f"{it.name:<15} {it.start:>5}  {it.finish:>6}  {deps}")
    lines.append(f"total duration: {sched.total_duration}")
    lines.append("critical path: " + " -> ".join(sched.critical_path))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zero-dependency DAG task scheduler (stdlib only)."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("order", "levels", "schedule"):
        p = sub.add_parser(name)
        p.add_argument("taskfile")
    args = parser.parse_args(argv)

    try:
        graph = load_graph(args.taskfile)
        if args.command == "order":
            print("\n".join(topo_sort(graph)))
        elif args.command == "levels":
            for i, batch in enumerate(levels(graph)):
                print(f"L{i}: " + ", ".join(batch))
        else:
            print(format_schedule(schedule(graph)))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
