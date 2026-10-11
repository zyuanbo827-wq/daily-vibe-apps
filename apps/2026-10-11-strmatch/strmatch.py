"""strmatch.py -- 零依赖字符串模式匹配实验台。

实现三种单模式匹配算法并核对结果一致：
- 朴素匹配（暴力双指针）
- KMP（前缀函数 pi，匹配不回退文本指针）
- Rabin-Karp（滚动哈希，命中后二次确认防哈希碰撞）
CLI 像 grep 一样在文件中查找模式并输出行号与出现次数。
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Tuple

# Rabin-Karp 参数：大素数模数与进制
_RK_BASE = 256
_RK_MOD = 1_000_000_007


# --------------------------------------------------------------------------- #
# 朴素匹配
# --------------------------------------------------------------------------- #
def naive_search(text: str, pattern: str) -> List[int]:
    if not pattern:
        return []
    out: List[int] = []
    n, m = len(text), len(pattern)
    for i in range(n - m + 1):
        if text[i:i + m] == pattern:
            out.append(i)
    return out


# --------------------------------------------------------------------------- #
# KMP
# --------------------------------------------------------------------------- #
def prefix_function(pattern: str) -> List[int]:
    """pi[i] = pattern[:i+1] 最长相等真前缀/真后缀长度。"""
    m = len(pattern)
    pi = [0] * m
    for i in range(1, m):
        j = pi[i - 1]
        while j > 0 and pattern[i] != pattern[j]:
            j = pi[j - 1]
        if pattern[i] == pattern[j]:
            j += 1
        pi[i] = j
    return pi


def kmp_search(text: str, pattern: str) -> List[int]:
    if not pattern:
        return []
    pi = prefix_function(pattern)
    out: List[int] = []
    j = 0
    for i, ch in enumerate(text):
        while j > 0 and ch != pattern[j]:
            j = pi[j - 1]
        if ch == pattern[j]:
            j += 1
        if j == len(pattern):
            out.append(i - j + 1)
            j = pi[j - 1]   # 支持重叠匹配
    return out


# --------------------------------------------------------------------------- #
# Rabin-Karp
# --------------------------------------------------------------------------- #
def rabin_karp_search(text: str, pattern: str) -> List[int]:
    if not pattern:
        return []
    n, m = len(text), len(pattern)
    if m > n:
        return []
    high = pow(_RK_BASE, m - 1, _RK_MOD)

    def hash_chunk(chunk: str) -> int:
        h = 0
        for ch in chunk:
            h = (h * _RK_BASE + ord(ch)) % _RK_MOD
        return h

    pat_hash = hash_chunk(pattern)
    win_hash = hash_chunk(text[:m])
    out: List[int] = []
    for i in range(n - m + 1):
        if win_hash == pat_hash and text[i:i + m] == pattern:
            out.append(i)  # 二次确认，杜绝哈希碰撞误报
        if i < n - m:
            win_hash = (
                (win_hash - ord(text[i]) * high) * _RK_BASE
                + ord(text[i + m])
            ) % _RK_MOD
    return out


# --------------------------------------------------------------------------- #
def all_agree(text: str, pattern: str) -> bool:
    a = naive_search(text, pattern)
    b = kmp_search(text, pattern)
    c = rabin_karp_search(text, pattern)
    return a == b == c


# --------------------------------------------------------------------------- #
# 文件级查找
# --------------------------------------------------------------------------- #
def find_in_lines(lines: List[str], pattern: str, ignore_case: bool
                  ) -> List[Tuple[int, int, str]]:
    """返回 (行号, 该行出现次数, 行内容)，行号从 1 开始。"""
    hits = []
    for lineno, raw in enumerate(lines, 1):
        line = raw.rstrip("\n")
        hay = line.lower() if ignore_case else line
        needle = pattern.lower() if ignore_case else pattern
        positions = kmp_search(hay, needle)
        if positions:
            hits.append((lineno, len(positions), line))
    return hits


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_find(args) -> int:
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return 2
    hits = find_in_lines(lines, args.pattern, args.ignore_case)
    total = 0
    for lineno, count, line in hits:
        total += count
        print(f"{lineno}:{count}: {line}")
    print(f"matches: {total}")
    return 0 if hits else 1


def cmd_demo(args) -> int:
    cases = [
        ("ababcabcabababd", "ababd"),
        ("aaaaa", "aa"),
        ("the quick brown fox", "fox"),
        ("mississippi", "issi"),
        ("abcdef", "xyz"),
    ]
    print("algorithm comparison (naive / kmp / rabin-karp):")
    for text, pattern in cases:
        positions = kmp_search(text, pattern)
        agree = all_agree(text, pattern)
        print(f"  {pattern!r} in {text!r}: {positions} "
              f"{'AGREE' if agree else 'DIFFER'}")

    print("\nprefix function of 'ababaca':", prefix_function("ababaca"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="字符串模式匹配实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("find", help="在文件中查找模式")
    pf.add_argument("pattern")
    pf.add_argument("file")
    pf.add_argument("-i", "--ignore-case", action="store_true")
    pf.set_defaults(func=cmd_find)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
