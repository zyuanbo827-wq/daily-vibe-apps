# 2026-09-22 · jsonlite —— 手写 JSON 解析 / 格式化 / 路径查询

零依赖的迷你 jq：不使用标准库 `json` 完成解析，而是手写**递归下降解析器**，
严格实现 JSON 文法并给出带行列号的错误信息；附带 minify / pretty 序列化、
极简路径查询（`a.b[0].c`）和四个 CLI 子命令。

## 功能

- **手写解析器**：对象、数组、字符串（`\" \\ \/ \b \f \n \r \t` 与
  `\uXXXX`，含高低代理对组合、孤立代理项报错、未转义控制字符报错）、
  数字（负号 / 小数 / 指数）、`null` / `true` / `false`
- **严格模式**：拒绝注释、单引号、尾逗号、前导零（`01`）、`+1`、`.5`、
  `1.`、`1e`、`NaN` / `Infinity`、值后多余字符；重复键以后值为准
  （与标准库一致）
- **序列化**：`dumps(obj)` 压缩单行、`dumps(obj, indent=2)` 美化缩进；
  空数组/空对象保持单行；拒绝 NaN/Infinity、非字符串键和不可序列化类型
- **路径查询**：支持 `a.b.c`、`$` 根、`[0]` 整数下标（含负索引）、
  `["带.的键"]` / `['键']`；越界、缺键、类型不符都抛带说明的错误
- **CLI**：
  - `validate <file|-`：校验合法性（合法退出 0、文法错误 1、文件错误 2）
  - `get <file|- <path>`：按路径取值，容器美化输出、标量按 JSON 输出
  - `pretty <file|- [-i N]`：美化
  - `minify <file|->`：压缩为单行
  - 所有子命令支持 `-` 从标准输入读取，便于管道组合

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
python jsonlite.py validate sample.json
python jsonlite.py get sample.json 'items[1].id'      # 2
python jsonlite.py get sample.json 'note'            # "café ☕ 😀"
python jsonlite.py pretty sample.json
python jsonlite.py minify sample.json
echo '{"x" : [ 1, 2 ]}' | python jsonlite.py minify - # {"x":[1,2]}
```

作为库使用：

```python
from jsonlite import loads, dumps, query

data = loads(open("sample.json", encoding="utf-8").read())
print(query(data, "items[0].id"))          # 1
print(dumps(data, indent=2))
```

## 实现要点

- **递归下降**：`parse_value` 按首字符分派到对象 / 数组 / 字符串 / 数字 /
  字面量；对象和数组严格检查逗号与括号，显式拒绝尾逗号。
- **数字识别**：先按文法扫描整数 / 小数 / 指数区间，再用 `int()` /
  `float()` 转换，保证整数值保持 `int` 类型（`10` 不会变成 `10.0`）。
- **代理对**：遇到 `\uD800–\uDBFF` 高代理项时，要求紧跟 `\uDC00–\uDFFF`
  低代理项，按 `0x10000 + ((hi-0xD800)<<10) + (lo-0xDC00)` 合成码点。
- **测试驱动修掉的真实 bug**：
  1. 数字解析用 `peek() in "eE"` 判断指数，输入结束时空字符串 `"" in
     "eE"` 恒为真，导致单独解析 `0` 误报“指数部分至少需要一位数字”——
     改为显式元组比较 `peek() in ("e", "E")`；
  2. `\uXXXX` 的四位十六进制切片 off-by-one（跳过了首位 hex 字符），
     已修正为从当前位置切 4 位并步进 4，补了 `\u00e9`、emoji 代理对、
     孤立代理项的回归用例；
  3. 路径查询最初只认双引号括号键，补齐单引号 `['key']` 支持。
- **交叉验证**：测试用固定种子随机生成 200 组嵌套结构，经标准库
  `json.dumps`（紧凑 / 缩进 / 自定义分隔符三种形式）序列化后，
  用本解析器与 `json.loads` 同时解析并逐值比对。

## 测试

```bash
python -m unittest test_jsonlite -v
```

共 27 个用例：字面量与空白、合法/非法数字、全部字符串转义与代理对、
容器严格语法、错误行列号、200 组随机语料与标准库交叉验证、
序列化往返与类型拒绝、路径查询正反例、四个 CLI 子命令 / stdin /
缺文件的子进程冒烟。
