# 2026-09-20 · spellcheck —— 编辑距离拼写检查器（Levenshtein + BK-tree）

零依赖的英文拼写检查器：用 Levenshtein 编辑距离度量单词相似度，
用 BK-tree（Burkhard-Keller 度量树）做最近邻检索，
把朴素的「逐词扫描 O(n·d)」剪枝成只访问少量节点的精确查询，
不会漏掉任何半径内的候选词。

## 功能

- **Levenshtein 距离**：两行 DP，增/删/改各代价 1，
  O(a·b) 时间、O(较短串长度) 空间，支持 Unicode
- **BK-tree**：以编辑距离为边权建度量树；查询时依据三角不等式
  `|边权 - d(目标, 当前词)| ≤ 半径` 剪枝，**精确**返回半径内全部词
- **拼写建议**：按 `(距离, 字母序)` 排序，可限量
- **文本检查**：正则切分单词（支持 `don't` 这类撇号缩写），
  保留每个错误词在原文中的起止位置，大小写不敏感
- **CLI**：
  - `suggest <词典> <单词>`：列出相近词及距离，无候选退出码 1
  - `check <词典> <句子...>`：逐词检查，全部正确退出码 0，有错误退出码 1
  - 参数错误 / 文件缺失退出码 2
- 自带 `words_en.txt`：约 380 个常用英文词的示例词典

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
python spellcheck.py suggest words_en.txt speling --max-dist 2 --limit 3
# spelling  1
# spring    2

python spellcheck.py check words_en.txt "a beutiful and wunderful morning"
# beutiful (位置 2) -> beautiful
# wunderful (位置 15) -> wonderful   （退出码 1）
```

作为库使用：

```python
from spellcheck import SpellChecker, levenshtein, BKTree

checker = SpellChecker.from_file("words_en.txt", max_dist=2)
checker.is_word("Because")          # True（大小写不敏感）
checker.suggest("becuase", limit=3) # ['because']
for f in checker.check_text("this is a beutiful dayy"):
    print(f.word, f.start, f.suggestions)
```

## 实现要点

- **为什么 BK-tree 能剪枝**：编辑距离是度量，满足三角不等式。
  设当前节点到目标距离为 d，某子树边权为 w，则子树内词与目标的距离
  必落在 `[d-w, d+w]`；与查询半径区间无交集的子树整体跳过。
  半径 0 的精确查询沿插入路径回溯，天然支持成员判定。
- **插入语义**：重复词（距离 0）静默忽略；所有词小写归一，
  空词抛 `SpellError`。
- **DP 空间优化**：每轮迭代只保留上一行与当前行，
  并把较短串放在列方向。
- **文本检查**：用 `[A-Za-z]+(?:'[A-Za-z]+)?` 做 finditer，
  标点与空白自然跳过，`match.start()/end()` 给出错误位置，
  便于上层做高亮或替换。
- 与 09-19 的布隆过滤器形成对照：后者是概率型、只回答在不在，
  本应用是精确度量检索，给出「差多远、最像谁」。

## 测试

```bash
python -m unittest test_spellcheck -v
```

共 21 个用例，覆盖：经典编辑距离（kitten→sitting=3 等）、
对称性与三角不等式、Unicode；BK-tree 的建库/去重/半径 0/排序/
异常分支，以及 **400 个随机词 × 100 个随机查询、半径 1 和 2 下
与暴力全扫描结果逐条一致** 的剪枝正确性；拼写建议、文本位置、
撇号切词；CLI 命中/未命中/错误退出码。

开发中实际修掉两个问题：`__contains__` 未做小写归一导致
大写词查不到（已加回归用例）、测试对 "speling" 的最近词预期错误
（实际最近是 spring，已把 "spelling" 收入示例词典并修正断言）。
