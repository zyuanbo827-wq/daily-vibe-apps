# 2026-10-02 · trie-autocomplete —— 前缀树与自动补全

零依赖的 Trie（前缀树）实现与自动补全工具：按字符分叉存储词表，
支持带词频插入、精确查询、前缀存在性、**top-k 自动补全**（词频降序、
同频词形升序）、**'.' 通配匹配**、删除并递归剪枝，以及词频文件的
序列化往返；CLI 可直接从搜索日志词频文件构建并查询。

## 功能

- **Trie 结构**：每个节点持有 `字符 -> 子节点` 映射、是否为词尾、
  词频；公共前缀只存一份，节点数与词数独立统计
- **插入**：`insert(word, freq)`，重复插入同一词时词频累加、词数不重复
- **查询**：`contains(word)` 精确匹配（必须到词尾）、
  `startswith(prefix)` 前缀存在性
- **自动补全**：`complete(prefix, limit)` 定位前缀节点后 DFS 收集全部
  候选，按 `(-freq, word)` 排序取 top-k；空前缀即全词表排序
- **通配匹配**：`wildcard(pattern)` 中 '.' 匹配任意单个字符（严格一个），
  递归 DFS，结果按词形排序
- **删除**：`delete(word)` 递归删除词尾标记并向上剪枝无词尾、无子节点
  的分支；共享前缀上的其他词不受影响
- **序列化**：`to_lines()` / `from_lines()` 使用 `word<TAB>freq` 文本
  格式，支持 `#` 注释与空行，无频数列的词按频 1 处理

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置词表演示
python trie_autocomplete.py demo

# 从搜索日志构建，前缀补全 top3
python trie_autocomplete.py complete search_log.tsv --prefix ca --limit 3

# 通配查询（. 匹配一个字符）
python trie_autocomplete.py wildcard search_log.tsv --pattern "..t"

# 交互式：c 补全 / w 通配 / s 精确
python trie_autocomplete.py repl search_log.tsv

# 标准输入
echo "alpha 9" | python trie_autocomplete.py complete - --prefix a
```

作为库使用：

```python
from trie_autocomplete import Trie

t = Trie()
t.insert("apple", 42)
t.complete("ap", limit=5)     # [('apple', 42), ...]
t.wildcard("ap..e")
```

## 实现要点

1. **为什么用 Trie**：前缀补全要求"给定 prefix 快速枚举全部后缀"。
  哈希表只能做精确匹配，而 Trie 一次定位前缀节点后，子树即全部候选，
  查询复杂度只与前缀长度和候选数有关，与词表总量无关。
2. **补全排序的确定性**：DFS 收集后统一按词频降序、词形升序排序，
  结果不依赖遍历顺序，测试可稳定断言。
3. **通配符严格匹配一个字符**："do." 只命中 dog/dot，不会命中 4 字母
  的 door——这是与 `.*`（任意长度）的关键区别。
4. **删除剪枝**：递归返回"该节点是否可删"，只有非词尾且子节点为空
  才向上删除；词尾节点即使无子节点也保留（它本身是一个词）。
5. **词频累加语义**：搜索日志中同一词出现多行/多次插入时累加频率，
  词数只计一次，符合日志聚合场景。

## 测试

```bash
python -m unittest test_trie_autocomplete -v
```

共 27 个用例：插入/共享前缀/词频累加/节点计数与非法插入；补全的
词频排名、分支排名、缺失前缀、空前缀全局排序与同频词形平局；通配的
定长匹配、首字符通配与无匹配；删除后共享词保留、缺失词与全部删除后
回到单根；序列化往返、注释/纯词行与坏词频；以及 complete/wildcard/
demo/repl/stdin/缺文件/坏词频的 CLI 子进程冒烟。

开发中修正三处测试构造：①`do.` 不匹配 4 字母 door；②4 个点能匹配
4 字母词，改用 12 个点验证无匹配；③注释/空行不计词数（应为 2）。
