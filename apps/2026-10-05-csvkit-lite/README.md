# 2026-10-05 · csvkit-lite —— 零依赖 CSV 查询小工具

手写 RFC 4180 CSV 解析器，加上一套类 SQL 的表操作：列选择、
过滤、排序、limit、JSON/Markdown 导出，以及分组聚合统计
（count/sum/avg/min/max）。不依赖标准库以外的任何包，
适合在没有 pandas 的环境里快速查 CSV。

## 功能

**手写解析器**
- 引号包裹字段、双引号 `""` 转义、字段内嵌逗号与换行
- LF / CRLF 通用，自动去 UTF-8 BOM，空字段与尾随逗号正确处理
- 未闭合引号、引号出现在字段中间、行列数不齐均报错

**查询（query）**
- `--select a,b` 选择/重排列顺序，`*` 为全部列
- `--filter "col op value"`，支持 `= != > < >= <= contains`，
  可多次叠加（AND 语义）；数值自动按数字比较，否则按字符串
- `--sort col [--desc]`：数值列按数值、文本列按文本
- `--limit N`
- `--format csv|json|md`：CSV（RFC 规范输出）、JSON 对象数组、
  Markdown 表格（自动转义 `|`）

**聚合（stats）**
- `--by col` 分组，`--agg "count,sum:x,avg:x,min:x,max:x"`
- 不分组时对整表汇总；数值以 `:g` 格式输出，去除多余尾零

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 过滤 + 排序 + 选列，输出 JSON
python csvkit_lite.py query sample.csv \
  --filter "score>80" --sort score --desc \
  --select name,score --format json

# 按城市分组统计
python csvkit_lite.py stats sample.csv --by city \
  --agg "count,avg:score,max:score"

# 标准输入
type sample.csv | python csvkit_lite.py query - --format md

# 内置演示
python csvkit_lite.py demo
```

作为库使用：

```python
from csvkit_lite import Table, parse_csv, aggregate
t = Table.from_text(open("sample.csv", encoding="utf-8").read())
t.filter("city=Beijing").sort("score", desc=True).to_json()
aggregate(t, "city", ["count", "avg:score"]).to_markdown()
```

## 实现要点

1. **解析器是字符级状态机**：核心只有"是否在引号内"一个状态。
  引号内一切原样（含逗号、换行、`""`→`"`），引号外才识别分隔符；
  这样字段内嵌换行/逗号不会破坏结构。
2. **行结束的三种写法统一处理**：`\n`、`\r\n`、`\r` 走同一收尾逻辑，
  纯尾随换行不产生多余空行（用"是否还有未输出内容"判断）。
3. **比较与排序的数值感知**：统一用 `maybe_number` 尝试转 float，
  成功按数值、失败按字符串；排序键用 `(类型标记, 值)` 元组，
  避免数字与字符串直接比较。
4. **输出端最小引用**：只在字段含逗号/引号/换行时才加引号并转义，
  生成的 CSV 干净且仍符合 RFC，往返解析结果一致。
5. **聚合与表结构解耦**：分组保留首次出现顺序，聚合函数按列现算，
  输出本身就是一张新 Table，可继续走任意格式导出。

## 测试

```bash
python -m unittest test_csvkit_lite -v
```

共 25 个用例：解析器 9 个（简单/引号逗号/转义/内嵌换行/CRLF/
空字段/单列与尾随换行/两类错误/BOM）；写入引用规则与往返；
选择、四类过滤、数值与文本排序、limit、未知列、三种格式与
`|` 转义；分组与整表聚合、非法聚合；以及 demo、query、stats、
stdin、缺文件的 CLI 子进程冒烟。全部一次通过，未发现需要
修复的实现缺陷。
