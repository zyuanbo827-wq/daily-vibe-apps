# 2026-10-04 · minisearch —— 倒排索引与迷你搜索引擎

一个小而完整的信息检索内核：文档分词后建立**词项 → 文档**的倒排
记录表并记录词频，支持布尔 AND 查询与 TF-IDF 打分排名查询，
可增删文档、JSON 序列化往返；CLI 可对目录下 `.txt` 文件一键建库
检索，也可运行内置演示。

## 功能

- **分词**：小写化，按字母/数字串切词（正则 `[^\W_]+`，天然切掉下划线，
  支持非 ASCII 字母），可配置停用词，建库与查询使用同一套分词
- **倒排记录表**：`term -> {doc_id: tf}`，用 Counter 统计词频
- **增删文档**：重复添加同一 id 会先删后加（计数不翻倍）；删除时
  清空对应记录项，记录表为空的词项一并移除
- **布尔 AND**：对各词项的文档集合求交，缺词即返回空，结果按 id 升序
- **TF-IDF 排名**：
  - 文档侧词频权重 `1 + log(tf)`
  - 平滑逆文档频率 `idf = log((N+1)/(df+1)) + 1`，恒为正
  - 文档得分 = 查询中每个词项的权重之和；分数降序、id 升序破平，支持 top-k
- **序列化**：保存停用词与原始文档（JSON），加载后完整重建索引

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置演示：AND 交集、TF-IDF 排名、罕见词 vs 常见词
python minisearch.py demo

# 对目录下所有 .txt 建库并排名查询（文件名即文档 id）
python minisearch.py query "inverted index documents" --dir sample_docs

# 布尔 AND 查询
python minisearch.py query "inverted index" --dir sample_docs --mode and
```

作为库使用：

```python
from minisearch import InvertedIndex
idx = InvertedIndex(stopwords=("the", "a"))
idx.add("d1", "the quick brown fox")
idx.search_and("quick fox")          # ['d1']
idx.search_rank("brown fox")         # [('d1', score)]
idx.dumps()                          # JSON 持久化
```

## 实现要点

1. **倒排表是检索的核心数据结构**：从"逐文档扫描"变为"按词项直达
  文档集合"，AND 查询就是集合交集，排名只需累加命中词项的权重。
2. **词频与逆文档频率分工**：`1+log(tf)` 刻画词在文档中的重要性且
  抑制高频词的边际影响；idf 让罕见词更有区分度（停用词进一步在
  分词阶段剔除无信息词）。
3. **删除的正确性**：先按该文档出现过的词项逐一删记录项，再删空词项，
  保证 df 与后续 idf 计算不被污染。
4. **确定性输出**：排名以 `(-score, id)` 排序，破平规则固定；序列化
  按 id 排序重建，测试可逐值断言。
5. **零依赖持久化**：只存原文与配置、不存派生索引，加载即重建，
  格式简单且不会出现索引与文档不一致。

## 测试

```bash
python -m unittest test_minisearch -v
```

共 20 个用例：分词（大小写/数字/下划线/停用词）；添加与重复添加、
删除与空词项清理、词表；AND 交集/缺词/空查询；idf 罕见词更高、
tf 加权、排名顺序与同分破平、top-k、查询侧停用词；JSON 序列化
往返；以及 demo、rank/and 查询、空目录退出码的 CLI 子进程冒烟。
全部一次通过，未发现需要修复的实现缺陷。
