# 2026-10-11 · strmatch —— 字符串模式匹配实验台

三种单模式字符串匹配算法的对比实验台：朴素匹配、KMP（前缀
函数）、Rabin-Karp（滚动哈希）。CLI 像 grep 一样在文件中
查找模式，输出行号、每行出现次数与总匹配数。零三方依赖。

## 功能

- **朴素匹配**：逐起点比较，O(nm)，作为结果基准
- **KMP**：
  - `prefix_function` 计算每个前缀的最长相等真前后缀长度 pi
  - 匹配时文本指针永不回退，失配按 pi 跳转，O(n+m)
  - 完整匹配后按 `pi[j-1]` 继续，支持重叠匹配（`aa` in `aaa`）
- **Rabin-Karp**：固定长度窗口的滚动哈希，进/出字符 O(1)
  更新；哈希命中后逐字符二次确认，杜绝哈希碰撞误报
- **文件查找**：按行扫描，输出 `行号:次数: 内容`；支持 `-i`
  忽略大小写；无匹配退出码 1，文件缺失退出码 2

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置演示：五组用例三算法结果对比、前缀函数示例
python strmatch.py demo

# 在文件中查找（-i 忽略大小写）
python strmatch.py find pattern sample.txt
python strmatch.py find -i fox sample.txt
```

作为库使用：

```python
from strmatch import kmp_search, prefix_function, rabin_karp_search
kmp_search("aaaaa", "aa")          # [0, 1, 2, 3]
prefix_function("ababaca")         # [0, 0, 1, 2, 3, 0, 1]
```

## 实现要点

1. **前缀函数是 KMP 的核心**：pi[i] 表示 `pattern[:i+1]` 的
  最长相等真前缀与真后缀长度。失配时模式串不必从头开始，而是
  跳到 `pi[j-1]`——已匹配部分的边界信息没有浪费。
2. **文本指针不回退**：KMP 主循环只前进 i，整体线性；朴素
  算法在失配后文本起点要整体后移一位、重复比较，最坏 O(nm)。
3. **重叠匹配靠完整匹配后的跳转**：记录一次完整匹配后，令
  j = pi[j-1] 而非归零，才能在 "aaaaa" 中找到 4 个 "aa"。
4. **Rabin-Karp 的滚动更新**：窗口右移时减去离开字符的最高位
  权值、整体乘进制、再加进入字符；`high = base^(m-1)`。
5. **哈希必须二次确认**：模数再大也存在理论碰撞，只有
  `text[i:i+m] == pattern` 才报告命中；这也是测试中要求三种
  算法结果完全一致的原因。

## 测试

```bash
python -m unittest test_strmatch -v
```

共 18 个用例：前缀函数三组（ababaca、全同、abcabcd）；KMP
基本匹配、重叠匹配、issi 双命中、无匹配、模式更长、空模式、
单字符；三算法五组用例结果一致、naive 与 RK 对照；文件按行
计数（pattern 出现 3 次）、忽略大小写 fox 命中两行；以及
demo、find 命中/无匹配退出码 1、缺文件退出码 2 的子进程冒烟。
全部一次通过，未发现需要修复的实现缺陷。
