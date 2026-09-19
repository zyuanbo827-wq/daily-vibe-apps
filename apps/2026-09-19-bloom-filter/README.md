# 2026-09-19 · bloom-filter —— 零依赖布隆过滤器

一个纯标准库实现的布隆过滤器（Bloom Filter）：自动按容量与误判率计算最优参数，
支持双哈希定位、并集/交集、误判率估算、二进制序列化，以及
`build / query / info` 命令行工具（可对词表建库后批量判重）。

## 功能

- 参数自动设计：给定预期元素数 n 与目标误判率 p
  - 位数组大小 `m = ⌈-n·ln p / (ln 2)²⌉`
  - 哈希函数个数 `k = round(m/n·ln 2)`（n=10000、p=1% 时为经典的 m≈95851、k=7）
- 双哈希（double hashing）：两个带不同种子的 64 位 FNV-1a 派生 k 个位置
  （`h_i = (h1 + i·h2) mod m`，h2 置奇数改善覆盖），无需任何三方哈希库
- 零漏报：已加入元素必定命中；未加入元素可能假阳性，假阳性率可估算
- 集合运算：同参数过滤器的并集（OR）与交集（AND）
- 紧凑二进制格式（魔数 `BLMF` + 版本 + m/k/count + 位图），带合法性校验
- CLI：
  - `build`：每行一个元素的文本（或标准输入）→ `.bloom` 文件
  - `query`：批量查询，全部命中退出码 0，存在“一定不存在”退出码 1
  - `info`：查看 m、k、插入次数、位占用率、估算误判率、文件大小

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 用示例词表建库
python bloom.py build sample_words.txt -o words.bloom --fpp 0.01
python bloom.py info words.bloom
python bloom.py query words.bloom apple zebra ghost
# apple/zebra -> 可能存在；ghost -> 一定不存在（退出码 1）

# 从标准输入建库
type urls.txt | python bloom.py build - -o urls.bloom --capacity 1000000
```

作为库使用：

```python
from bloom import BloomFilter

bf = BloomFilter(expected_items=10_000, fpp=0.01)
bf.add_many(f"user-{i}" for i in range(10_000))
"user-42" in bf          # True（零漏报）
bf.estimated_fpp()       # 满载时约 0.01
other = BloomFilter(10_000, 0.01)
merged = bf.union(other)
raw = bf.to_bytes()      # 可落盘 / 网络传输
```

## 实现要点

- 位图用 `bytearray`，定位为 `bits[i >> 3] |= 1 << (i & 7)`，
  空间占用约为 `ceil(m/8)` 字节 + 25 字节文件头。
- 双哈希只需两次完整哈希即可生成任意 k 个位置，避免对每个元素做 k 次摘要；
  这是布隆过滤器工程实现中的标准折中。
- 估算误判率公式 `(1 - e^{-kn/m})^k` 以实际插入次数为准，
  超容量使用时数值会明显上升，可作为扩容信号。
- 并集/交集要求两侧 m、k 完全一致，否则抛 `BloomError`；
  交集结果仍可能保留假阳性位，这是概率数据结构的固有性质。
- 反序列化校验魔数、版本号、m/k 合法性与位图长度，拒绝截断或伪造数据。

## 测试

```bash
python -m unittest test_bloom -v
```

共 26 个用例，覆盖参数公式与边界、FNV 哈希性质、零漏报、
**2 万次确定性探测的实测假阳性率上界**、满载估算误判率、
并集/交集、序列化往返与损坏数据拒绝，以及 CLI 建库/查询/信息/标准输入
的子进程冒烟（含退出码语义）。
