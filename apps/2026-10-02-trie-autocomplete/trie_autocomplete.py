"""trie_autocomplete.py -- 零依赖前缀树（Trie）与自动补全。

Trie 节点按字符分叉，支持：
  插入（带词频）/ 精确查询 / 前缀存在性 / top-k 自动补全
  （按词频降序、词形升序）/ '.' 通配匹配 / 删除并剪枝
  / 词表序列化往返；CLI 可从词频文件构建并查询。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class TrieError(ValueError):
    pass


@dataclass
class Node:
    children: Dict[str, "Node"] = field(default_factory=dict)
    terminal: bool = False
    freq: int = 0


class Trie:
    def __init__(self):
        self.root = Node()
        self.size = 0          # 词数
        self.node_count = 1    # 含根节点

    # -- 基础操作 -- #
    def insert(self, word: str, freq: int = 1) -> None:
        if not word:
            raise TrieError("不能插入空词")
        if freq < 0:
            raise TrieError("词频不能为负")
        node = self.root
        for ch in word:
            nxt = node.children.get(ch)
            if nxt is None:
                nxt = Node()
                node.children[ch] = nxt
                self.node_count += 1
            node = nxt
        if not node.terminal:
            self.size += 1
        node.terminal = True
        node.freq += freq

    def _find(self, prefix: str) -> Optional[Node]:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def contains(self, word: str) -> bool:
        node = self._find(word)
        return node is not None and node.terminal

    def startswith(self, prefix: str) -> bool:
        return self._find(prefix) is not None

    # -- 自动补全 -- #
    def complete(self, prefix: str, limit: int = 10) -> List[Tuple[str, int]]:
        """返回 prefix 下的补全：词频降序，同频按词形升序，取前 limit。"""
        base = self._find(prefix)
        if base is None:
            return []
        found: List[Tuple[str, int]] = []
        stack = [(base, prefix)]
        while stack:
            node, word = stack.pop()
            if node.terminal:
                found.append((word, node.freq))
            for ch, child in node.children.items():
                stack.append((child, word + ch))
        found.sort(key=lambda wf: (-wf[1], wf[0]))
        return found[:limit] if limit > 0 else found

    # -- 通配匹配（'.' 匹配任意单个字符）-- #
    def wildcard(self, pattern: str) -> List[str]:
        results: List[str] = []

        def dfs(node: Node, idx: int, word: str) -> None:
            if idx == len(pattern):
                if node.terminal:
                    results.append(word)
                return
            ch = pattern[idx]
            if ch == ".":
                for c, child in node.children.items():
                    dfs(child, idx + 1, word + c)
            else:
                child = node.children.get(ch)
                if child is not None:
                    dfs(child, idx + 1, word + ch)

        dfs(self.root, 0, "")
        return sorted(results)

    # -- 删除（递归剪枝）-- #
    def delete(self, word: str) -> bool:
        def dfs(node: Node, idx: int) -> bool:
            """返回该节点是否应被删除。"""
            if idx == len(word):
                if not node.terminal:
                    return False
                node.terminal = False
                node.freq = 0
                return not node.children
            ch = word[idx]
            child = node.children.get(ch)
            if child is None or not dfs(child, idx + 1):
                return False
            del node.children[ch]
            self.node_count -= 1
            return not node.terminal and not node.children

        existed = self.contains(word)
        if existed:
            dfs(self.root, 0)
            self.size -= 1
        return existed

    # -- 序列化：每行 "word<TAB>freq" -- #
    def to_lines(self) -> List[str]:
        lines: List[str] = []
        stack = [(self.root, "")]
        while stack:
            node, word = stack.pop()
            if node.terminal:
                lines.append(f"{word}\t{node.freq}")
            for ch, child in node.children.items():
                stack.append((child, word + ch))
        return sorted(lines)

    @classmethod
    def from_lines(cls, lines: List[str]) -> "Trie":
        trie = cls()
        for raw in lines:
            line = raw.rstrip("\n").rstrip("\r")
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                word, freq_s = line.rsplit("\t", 1)
                try:
                    freq = int(freq_s)
                except ValueError:
                    raise TrieError(f"词频不是整数：{line}")
            else:
                word, freq = line, 1
            trie.insert(word, freq)
        return trie


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
DEMO_WORDS = [
    "apple\t42", "app\t30", "application\t18", "apply\t12", "april\t3",
    "banana\t25", "band\t9", "banner\t7", "bank\t11",
    "cat\t33", "car\t28", "card\t15", "care\t10", "carry\t6",
    "dog\t20", "door\t14", "dot\t5",
]


def load_trie(path: str) -> Trie:
    if path == "-":
        return Trie.from_lines(sys.stdin.read().splitlines())
    try:
        with open(path, "r", encoding="utf-8") as f:
            return Trie.from_lines(f.readlines())
    except FileNotFoundError:
        raise SystemExit(2)
    except TrieError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)


def print_completions(rows: List[Tuple[str, int]]) -> None:
    for word, freq in rows:
        print(f"{freq:>6}  {word}")


def cmd_complete(args: argparse.Namespace) -> int:
    trie = load_trie(args.file)
    rows = trie.complete(args.prefix, args.limit)
    print_completions(rows)
    return 0


def cmd_wildcard(args: argparse.Namespace) -> int:
    trie = load_trie(args.file)
    for word in trie.wildcard(args.pattern):
        print(word)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    trie = Trie.from_lines(DEMO_WORDS)
    print(f"词表：{trie.size} 词，{trie.node_count} 节点")
    print("\n== complete 'ap' top5 ==")
    print_completions(trie.complete("ap", 5))
    print("\n== complete 'ca' top5 ==")
    print_completions(trie.complete("ca", 5))
    print("\n== wildcard 'c.r' ==")
    for w in trie.wildcard("c.r"):
        print(w)
    print("\n== wildcard '..t' ==")
    for w in trie.wildcard("..t"):
        print(w)
    return 0


def cmd_repl(args: argparse.Namespace) -> int:
    trie = load_trie(args.file)
    print("命令：c <prefix> 补全 | w <pattern> 通配 | s <word> 精确 | q 退出")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            return 0
        if not line:
            continue
        if line == "q":
            return 0
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            print("error: 缺少参数")
            continue
        op, arg = parts
        if op == "c":
            print_completions(trie.complete(arg, args.limit))
        elif op == "w":
            for w in trie.wildcard(arg):
                print(w)
        elif op == "s":
            print("yes" if trie.contains(arg) else "no")
        else:
            print("error: 未知命令")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Trie 前缀树与自动补全（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("complete", help="前缀 top-k 补全")
    pc.add_argument("file", help="词频文件（每行 word<TAB>freq），- 为标准输入")
    pc.add_argument("--prefix", default="")
    pc.add_argument("--limit", type=int, default=10)
    pc.set_defaults(func=cmd_complete)

    pw = sub.add_parser("wildcard", help="'.' 通配匹配")
    pw.add_argument("file")
    pw.add_argument("--pattern", required=True)
    pw.set_defaults(func=cmd_wildcard)

    pd = sub.add_parser("demo", help="内置词表演示")
    pd.set_defaults(func=cmd_demo)

    pr = sub.add_parser("repl", help="交互式查询")
    pr.add_argument("file")
    pr.add_argument("--limit", type=int, default=5)
    pr.set_defaults(func=cmd_repl)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
