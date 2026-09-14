# tasksched · 2026-09-14

零依赖的 **DAG 任务调度器**（Python 标准库）：拓扑排序、分层并行、ASAP 最早时间排程与关键路径分析。

## 功能

- **拓扑排序**：Kahn 算法 + 最小堆打破并列，同一张图无论声明顺序如何，结果唯一确定；
- **校验**：自环/多节点环抛出 `CycleError` 并列出卡住的任务，依赖未定义、工期非法也会明确报错；
- **分层**：按依赖深度把任务分成可并行的批次（同层无依赖关系）；
- **排程**：给定工期计算每个任务的最早开始/完成时间（ES = 各前置 EF 的最大值）、项目总工期；
- **关键路径**：从终点沿"决定其开始时间"的前置回溯，找出决定工期的最长链；
- CLI 支持 `order` / `levels` / `schedule` 三个子命令，任务用 JSON 描述。

## 运行

```bash
# 单元测试（21 个用例）
python -m unittest test_tasksched -v

# 拓扑顺序 / 并行分层 / 排程与关键路径
python tasksched.py order sample_project.json
python tasksched.py levels sample_project.json
python tasksched.py schedule sample_project.json
```

任务文件格式：

```json
{ "A": {"deps": [], "duration": 3},
  "B": {"deps": ["A"], "duration": 2} }
```

## 实现要点

- `normalize` 统一做依赖存在性与工期校验，后续算法只处理干净的内部结构；
- 就绪集合用 `heapq` 而非 set，保证并列节点按名字升序，输出可复现、可测试；
- 关键路径回溯时取 finish 恰好等于本任务 start 的前置；多条等长关键链时按名字取第一条，保持确定性；
- 纯函数核心与 CLI/JSON 加载分离，便于嵌入更大的规划工具。
