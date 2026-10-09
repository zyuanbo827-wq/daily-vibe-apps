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
| 2026-09-21 | [sudoku](./apps/2026-09-21-sudoku) | Python 标准库 | 数独求解/校验/生成：MRV 回溯、解计数判唯一、挖洞生成可复现题面 |
| 2026-09-22 | [jsonlite](./apps/2026-09-22-jsonlite) | Python 标准库 | 手写递归下降 JSON 解析器：严格文法/转义代理对、美化压缩、路径查询与 CLI |
| 2026-09-23 | [ratelimit](./apps/2026-09-23-ratelimit) | Python 标准库 | 四种限流算法实验台：令牌桶/固定窗口/滑动日志/滑动计数，含突发对比与回放 CLI |
| 2026-09-28 | [minregex](./apps/2026-09-28-minregex) | Python 标准库 | 回溯式迷你正则引擎：字符类/分组捕获/交替/贪婪惰性量词，含 grep/find CLI |
| 2026-09-29 | [consistent-hash](./apps/2026-09-29-consistent-hash) | Python 标准库 | 一致性哈希环：虚拟节点/增删迁移计划，验证单调性与负载均衡，含 demo/dist CLI |
| 2026-09-30 | [cache-lab](./apps/2026-09-30-cache-lab) | Python 标准库 | LRU/LFU 缓存实验台：手写链表 O(1) 淘汰、TTL、命中率统计，含 Zipf 负载对比 CLI |
| 2026-10-01 | [minesweeper](./apps/2026-10-01-minesweeper) | Python 标准库 | 扫雷：首击安全布雷、零区泛洪、插旗与和弦展开、自动胜负，含交互/演示 CLI |
| 2026-10-02 | [trie-autocomplete](./apps/2026-10-02-trie-autocomplete) | Python 标准库 | 前缀树自动补全：词频 top-k、'.' 通配匹配、删除剪枝、词表序列化，含查询 CLI |
| 2026-10-03 | [md2html](./apps/2026-10-03-md2html) | Python 标准库 | Markdown→HTML：标题/围栏代码/引用/列表/行内格式，转义原始 HTML 并拦截危险 URL |
| 2026-10-04 | [minisearch](./apps/2026-10-04-minisearch) | Python 标准库 | 倒排索引迷你搜索引擎：布尔 AND 交集、TF-IDF 排名、停用词、增删文档与 JSON 持久化 |
| 2026-10-05 | [csvkit-lite](./apps/2026-10-05-csvkit-lite) | Python 标准库 | 手写 RFC4180 CSV 解析与查询：选择/过滤/排序/limit、JSON 与 Markdown 导出、分组聚合 |
| 2026-10-07 | [fsm-lab](./apps/2026-10-07-fsm-lab) | Python 标准库 | 有限状态机实验台：DFA 模拟与轨迹、epsilon NFA 子集模拟、子集构造确定化与等价性核对 |
| 2026-10-08 | [merkle-tree](./apps/2026-10-08-merkle-tree) | Python 标准库 | Merkle 树：SHA-256 根哈希、对数级包含证明与验证、篡改检测、文件分块完整性校验 |
| 2026-10-09 | [graph-route](./apps/2026-10-09-graph-route) | Python 标准库 | 图最短路径实验台：Dijkstra、Bellman-Ford 负权与负环检测、Floyd-Warshall 全源对比 |

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
