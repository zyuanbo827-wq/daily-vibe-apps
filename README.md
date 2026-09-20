# daily-vibe-apps

> 每天一个小应用（Daily Vibe Coding Challenge）：由定时任务每天自动生成一个
> **可独立运行、经过验证**的小工具 / 小游戏 / 小可视化，按日期归档到 `apps/`。

## 规则（每日任务遵循）

1. 每个应用位于 `apps/YYYY-MM-DD-<slug>/`，自带 README，可独立运行；
2. 技术选型优先**零依赖**：Python 标准库（附 `unittest`）或单文件 HTML/CSS/JS；
   确需前端框架时使用 Vite，且必须 `npm run build` 通过；
3. Python 应用必须跑通单元测试；所有 commit 使用真实当前时间，不回改日期；
4. 每天分 2~4 个有意义的 conventional commits 提交，并更新下方索引表。

## 应用索引

| 日期 | 应用 | 技术 | 简介 |
|---|---|---|---|
| 2026-09-03 | [text-stats](./apps/2026-09-03-text-stats) | Python 标准库 | 文本统计：词数/句数/阅读时长/高频词，含 CLI 与单测 |
| 2026-09-04 | [cron-next](./apps/2026-09-04-cron-next) | Python 标准库 | cron 表达式解析与下 N 次执行时间计算，含 CLI 与单测 |
| 2026-09-05 | [huffman-codec](./apps/2026-09-05-huffman-codec) | Python 标准库 | 哈夫曼压缩编解码器：前缀码/比特打包/自描述码表头，含 CLI 与单测 |
| 2026-09-06 | [bf-interpreter](./apps/2026-09-06-bf-interpreter) | Python 标准库 | Brainfuck 解释器：括号跳转表/纸带回绕/字节 IO，含 CLI 与示例 |
| 2026-09-07 | [maze-solver](./apps/2026-09-07-maze-solver) | Python 标准库 | 随机 DFS 生成完美迷宫 + BFS 最短路 + ASCII 可视化，含 CLI |
| 2026-09-08 | [line-diff](./apps/2026-09-08-line-diff) | Python 标准库 | 基于 LCS 的 unified diff，支持补丁应用与反向回滚，含 CLI |
| 2026-09-09 | [game-2048](./apps/2026-09-09-game-2048) | Python 标准库 | 种子可复现的 2048 游戏核心：滑动合并、四向移动、终局判定与文本 CLI |
| 2026-09-14 | [tasksched](./apps/2026-09-14-tasksched) | Python 标准库 | DAG 任务调度器：确定性拓扑排序、分层并行、ASAP 排程与关键路径分析 |
| 2026-09-15 | [markov-text](./apps/2026-09-15-markov-text) | Python 标准库 | 1/2 阶马尔可夫链文本生成器，种子可复现，含 CLI 与示例语料 |
| 2026-09-16 | [game-of-life](./apps/2026-09-16-game-of-life) | Python 标准库 | 康威生命游戏 B3/S23，有界/环面边界、经典图案库与 ASCII CLI |
| 2026-09-17 | [expr-eval](./apps/2026-09-17-expr-eval) | Python 标准库 | 调度场表达式求值器：优先级/一元符号/函数/变量，含 RPN 调试与 REPL CLI |
| 2026-09-18 | [lsystem](./apps/2026-09-18-lsystem) | Python 标准库 | L-system 分形生成器：字符串重写+海龟绘图，输出 SVG/ASCII，内置 6 种预设 |
| 2026-09-19 | [bloom-filter](./apps/2026-09-19-bloom-filter) | Python 标准库 | 布隆过滤器：最优参数设计/双哈希/并交集/序列化，含建库查询 CLI 与单测 |
| 2026-09-20 | [spellcheck](./apps/2026-09-20-spellcheck) | Python 标准库 | 拼写检查器：Levenshtein 编辑距离 + BK-tree 剪枝最近邻，含建议/文本检查 CLI |

## 本地结构

```
daily-vibe-apps/
  apps/
    YYYY-MM-DD-slug/
      README.md
      ...源码与测试
```

## License

MIT
