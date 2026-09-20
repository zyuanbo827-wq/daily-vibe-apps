"""spellcheck.py -- 零依赖拼写检查器（编辑距离 + BK-tree）。

两部分：
  * levenshtein：两行 DP 计算 Levenshtein 编辑距离（增/删/改各代价 1）；
  * BKTree：利用编辑距离满足三角不等式的性质建度量树，
    查询时按 |d(边) - d(目标)| <= 半径 剪枝，精确返回半径内所有词。

SpellChecker 在 BK-tree 之上提供：
  * 词典加载（小写归一、去重）
  * 单词建议（按距离、字母序排序，可限量）
  * 文本检查（保留单词在原文中的位置，输出疑似拼写错误及建议）

附带 check / suggest 两个 CLI 子命令。仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import re

_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


class SpellError(ValueError):
    """参数错误。"""


# --------------------------------------------------------------------------- #
# 编辑距离
# --------------------------------------------------------------------------- #
def levenshtein(a: str, b: str) -> int:
    """标准 Levenshtein 距离，两行 DP，O(len(a)*len(b)) 时间、O(len(b)) 空间。"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # 让 b 为较短串以节省空间
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (ca != cb)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


# --------------------------------------------------------------------------- #
# BK-tree
# --------------------------------------------------------------------------- #
class _Node:
    __slots__ = ("word", "children")

    def __init__(self, word: str):
        self.word = word
        self.children: Dict[int, "_Node"] = {}


class BKTree:
    """以编辑距离为度量的 Burkhard-Keller 树。"""

    def __init__(self, words: Iterable[str] = ()):
        self.root: Optional[_Node] = None
        self._size = 0
        for w in words:
            self.add(w)

    def __len__(self) -> int:
        return self._size

    def __contains__(self, word: str) -> bool:
        target = word.lower()
        return any(w == target for w, _ in self.query(target, 0))

    def add(self, word: str) -> None:
        word = word.lower()
        if not word:
            raise SpellError("词典不能包含空词")
        if self.root is None:
            self.root = _Node(word)
            self._size += 1
            return
        node = self.root
        while True:
            d = levenshtein(word, node.word)
            if d == 0:
                return  # 重复词忽略
            nxt = node.children.get(d)
            if nxt is None:
                node.children[d] = _Node(word)
                self._size += 1
                return
            node = nxt

    def query(self, word: str, max_dist: int) -> List[Tuple[str, int]]:
        """返回树中与 word 距离 <= max_dist 的全部 (词, 距离)，按 (距离, 词) 排序。"""
        if max_dist < 0:
            raise SpellError("查询半径不能为负数")
        if self.root is None:
            return []
        target = word.lower()
        results: List[Tuple[str, int]] = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            d = levenshtein(target, node.word)
            if d <= max_dist:
                results.append((node.word, d))
            low, high = d - max_dist, d + max_dist
            for edge, child in node.children.items():
                if low <= edge <= high:
                    stack.append(child)
        results.sort(key=lambda pair: (pair[1], pair[0]))
        return results


# --------------------------------------------------------------------------- #
# 拼写检查
# --------------------------------------------------------------------------- #
@dataclass
class Finding:
    word: str
    start: int
    end: int
    suggestions: List[str] = field(default_factory=list)


class SpellChecker:
    def __init__(self, words: Iterable[str], max_dist: int = 2):
        self.tree = BKTree(words)
        self.max_dist = max_dist

    @classmethod
    def from_file(cls, path: str, max_dist: int = 2) -> "SpellChecker":
        with open(path, "r", encoding="utf-8") as fp:
            words = [line.strip().lower() for line in fp if line.strip()]
        return cls(words, max_dist=max_dist)

    def __len__(self) -> int:
        return len(self.tree)

    def is_word(self, word: str) -> bool:
        return word.lower() in self.tree

    def suggest(self, word: str, max_dist: Optional[int] = None,
                limit: int = 5) -> List[str]:
        radius = self.max_dist if max_dist is None else max_dist
        hits = self.tree.query(word, radius)
        return [w for w, _ in hits[:limit]]

    def check_text(self, text: str, max_dist: Optional[int] = None,
                   limit: int = 5) -> List[Finding]:
        """找出文本中所有词典未收录的单词及其建议。"""
        findings: List[Finding] = []
        for match in _TOKEN_RE.finditer(text):
            token = match.group()
            if self.is_word(token):
                continue
            suggestions = self.suggest(token, max_dist=max_dist, limit=limit)
            findings.append(Finding(token, match.start(), match.end(), suggestions))
        return findings


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _load(path: str) -> SpellChecker:
    return SpellChecker.from_file(path)


def _cmd_suggest(args: argparse.Namespace) -> int:
    checker = _load(args.dict)
    hits = checker.tree.query(args.word, args.max_dist)
    for word, dist in hits[: args.limit]:
        print(f"{word}\t{dist}")
    return 0 if hits else 1


def _cmd_check(args: argparse.Namespace) -> int:
    checker = _load(args.dict)
    text = " ".join(args.text)
    findings = checker.check_text(text, max_dist=args.max_dist, limit=args.limit)
    if not findings:
        print("未发现拼写问题。")
        return 0
    for f in findings:
        tips = ", ".join(f.suggestions) if f.suggestions else "（无相近词）"
        print(f"{f.word} (位置 {f.start}) -> {tips}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="基于编辑距离与 BK-tree 的拼写检查器")
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("suggest", help="查询一个单词的相近词")
    ps.add_argument("dict", help="词典文件（每行一个词）")
    ps.add_argument("word", help="待查询单词")
    ps.add_argument("--max-dist", type=int, default=2, help="最大编辑距离，默认 2")
    ps.add_argument("--limit", type=int, default=5, help="最多返回条数")
    ps.set_defaults(func=_cmd_suggest)

    pc = sub.add_parser("check", help="检查一句话中的拼写")
    pc.add_argument("dict", help="词典文件（每行一个词）")
    pc.add_argument("text", nargs="+", help="待检查文本（多个参数按空格拼接）")
    pc.add_argument("--max-dist", type=int, default=2)
    pc.add_argument("--limit", type=int, default=5)
    pc.set_defaults(func=_cmd_check)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (SpellError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
