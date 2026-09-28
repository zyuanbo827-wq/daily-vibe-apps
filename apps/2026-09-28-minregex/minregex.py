"""minregex.py -- 零依赖迷你正则引擎（回溯式）。

不使用标准库 re，手写 解析 -> AST -> 带捕获组的回溯匹配器（生成器
continuation 风格），支持：

  字面量 / . / 字符类 [a-z] [^...] / \\d \\w \\s（及大写反义）
  拼接 / 交替 | / 分组 (...) 与 (?:...)
  量词 * + ? {n} {n,} {n,m}，贪婪与惰性（*? +? ?? {n,m}?）
  锚点 ^ $
  search / match / fullmatch / finditer / findall

附带 grep 风格 CLI：minregex grep <pattern> <file|->。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple, Union

INF = float("inf")


class RegexError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# AST 节点
# --------------------------------------------------------------------------- #
@dataclass
class Char:
    ch: str


@dataclass
class Any:
    pass


@dataclass
class Class:
    members: list          # list[(int,int)] 闭区间
    negate: bool = False


@dataclass
class Start:
    pass


@dataclass
class End:
    pass


@dataclass
class Concat:
    items: list


@dataclass
class Alt:
    left: object
    right: object


@dataclass
class Repeat:
    atom: object
    mn: int
    mx: Union[int, float]
    greedy: bool = True


@dataclass
class Group:
    child: object
    gid: int              # 0 表示非捕获组


# --------------------------------------------------------------------------- #
# 模式解析
# --------------------------------------------------------------------------- #
_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "f": "\f", "v": "\v",
                   "0": "\0"}


def _class_ranges(name: str) -> List[Tuple[int, int]]:
    if name == "d":
        return [(ord("0"), ord("9"))]
    if name == "w":
        return [(ord("a"), ord("z")), (ord("A"), ord("Z")),
                (ord("0"), ord("9")), (ord("_"), ord("_"))]
    if name == "s":
        return [(9, 13), (ord(" "), ord(" "))]
    raise RegexError(f"不支持的转义 \\{name}")


class _Parser:
    def __init__(self, pattern: str):
        self.s = pattern
        self.i = 0
        self.n = len(pattern)
        self.ngroups = 0

    def peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.s[j] if j < self.n else ""

    def error(self, msg: str) -> RegexError:
        return RegexError(f"{msg}（位置 {self.i}）")

    # -- 文法：alt -> concat ('|' concat)* -- #
    def parse_alt(self, stop_at_paren: bool = False):
        node = self.parse_concat()
        pieces = [node]
        while self.peek() == "|":
            self.i += 1
            if self.peek() in ("|", ")"):
                raise self.error("交替分支为空")
            pieces.append(self.parse_concat())
        if len(pieces) == 1:
            return node
        result = pieces[0]
        for p in pieces[1:]:
            result = Alt(result, p)
        return result

    def parse_concat(self):
        items = []
        while self.peek() and self.peek() not in "|)":
            atom = self.parse_piece()
            if atom is not None:
                items.append(atom)
        if not items:
            raise self.error("缺少表达式")
        return items[0] if len(items) == 1 else Concat(items)

    def parse_piece(self):
        atom = self.parse_atom()
        ch = self.peek()
        if ch == "*":
            self.i += 1
            rep = Repeat(atom, 0, INF)
        elif ch == "+":
            self.i += 1
            rep = Repeat(atom, 1, INF)
        elif ch == "?":
            self.i += 1
            rep = Repeat(atom, 0, 1)
        elif ch == "{":
            rep = self.try_brace_quantifier(atom)
        else:
            return atom
        if self.peek() == "?":  # 惰性
            self.i += 1
            rep.greedy = False
        return rep

    def try_brace_quantifier(self, atom):
        j = self.i + 1
        start = j
        while self.peek(j - self.i).isdigit():
            j += 1
        num1 = self.s[start:j]
        if not num1:
            return atom  # 字面量 {
        mn = int(num1)
        mx = mn
        if self.s[j:j + 1] == ",":
            j += 1
            k = j
            while self.s[k:k + 1].isdigit():
                k += 1
            num2 = self.s[j:k]
            mx = int(num2) if num2 else INF
            j = k
        if self.s[j:j + 1] != "}":
            return atom
        self.i = j + 1
        if mx != INF and mx < mn:
            raise self.error("量词上界小于下界")
        return Repeat(atom, mn, mx)

    def parse_atom(self):
        ch = self.peek()
        if ch == "(":
            self.i += 1
            gid = 0
            if self.s[self.i:self.i + 2] == "?:":
                self.i += 2
            else:
                self.ngroups += 1
                gid = self.ngroups
            child = self.parse_alt(stop_at_paren=True)
            if self.peek() != ")":
                raise self.error("分组缺少 ')'")
            self.i += 1
            return Group(child, gid)
        if ch == "[":
            return self.parse_class()
        if ch == ".":
            self.i += 1
            return Any()
        if ch == "^":
            self.i += 1
            return Start()
        if ch == "$":
            self.i += 1
            return End()
        if ch == "\\":
            return self.parse_escape(class_context=False)
        if ch in "*+?)":
            raise self.error(f"意外的字符 {ch!r}")
        self.i += 1
        return Char(ch)

    def parse_escape(self, class_context: bool):
        self.i += 1  # 跳过反斜杠
        e = self.peek()
        if not e:
            raise self.error("结尾的反斜杠")
        if e in "dDsSwW":
            self.i += 1
            negate = e.isupper()
            base = e.lower()
            return Class(_class_ranges(base), negate=negate)
        if e in _SIMPLE_ESCAPES:
            self.i += 1
            return Char(_SIMPLE_ESCAPES[e])
        if e.isalpha():
            raise self.error(f"不支持的转义 \\{e}")
        self.i += 1
        return Char(e)  # 转义的标点按字面量

    def parse_class(self):
        self.i += 1  # 跳过 [
        negate = False
        if self.peek() == "^":
            negate = True
            self.i += 1
        members: List[Tuple[int, int]] = []
        first = True
        while True:
            ch = self.peek()
            if not ch:
                raise self.error("字符类缺少 ']'")
            if ch == "]" and not first:
                self.i += 1
                return Class(members, negate)
            first = False
            if ch == "\\":
                node = self.parse_escape(class_context=True)
                if isinstance(node, Class):
                    members.extend(node.members)
                else:
                    cp = ord(node.ch)
                    members.append((cp, cp))
            else:
                self.i += 1
                lo = ord(ch)
                if self.peek() == "-" and self.peek(1) not in ("]", ""):
                    self.i += 1  # -
                    hi_ch = self.peek()
                    if hi_ch == "\\":
                        hi_node = self.parse_escape(class_context=True)
                        hi = ord(hi_node.ch) if isinstance(hi_node, Char) \
                            else hi_ch
                    else:
                        self.i += 1
                        hi = ord(hi_ch)
                    if hi < lo:
                        raise self.error("字符类区间倒置")
                    members.append((lo, hi))
                else:
                    members.append((lo, lo))


def parse_pattern(pattern: str) -> Tuple[object, int]:
    p = _Parser(pattern)
    ast = p.parse_alt()
    if p.i != p.n:  # 理论上不会发生
        raise p.error("模式未消费完")
    return ast, p.ngroups


# --------------------------------------------------------------------------- #
# 回溯匹配器（生成器 continuation）
# --------------------------------------------------------------------------- #
Cont = "callable"


class _State:
    def __init__(self, ngroups: int):
        self.groups: List[Optional[List[int]]] = [None] * (ngroups + 1)


def _char_in(node: Class, cp: int) -> bool:
    hit = any(lo <= cp <= hi for lo, hi in node.members)
    return (not hit) if node.negate else hit


def _inst(node, text: str, i: int, st: _State, cont) -> Iterator[int]:
    if isinstance(node, Char):
        if i < len(text) and text[i] == node.ch:
            yield from cont(i + 1, st)
    elif isinstance(node, Any):
        if i < len(text) and text[i] != "\n":
            yield from cont(i + 1, st)
    elif isinstance(node, Class):
        if i < len(text) and _char_in(node, ord(text[i])):
            yield from cont(i + 1, st)
    elif isinstance(node, Start):
        if i == 0:
            yield from cont(i, st)
    elif isinstance(node, End):
        if i == len(text):
            yield from cont(i, st)
    elif isinstance(node, Concat):
        yield from _seq(node.items, 0, text, i, st, cont)
    elif isinstance(node, Alt):
        yield from _inst(node.left, text, i, st, cont)
        yield from _inst(node.right, text, i, st, cont)
    elif isinstance(node, Group):
        yield from _group(node, text, i, st, cont)
    elif isinstance(node, Repeat):
        yield from _repeat(node, text, i, st, cont)
    else:  # pragma: no cover
        raise RegexError("未知节点")


def _seq(items, idx: int, text, i, st, cont) -> Iterator[int]:
    if idx == len(items):
        yield from cont(i, st)
        return

    def next_cont(j, st2):
        return _seq(items, idx + 1, text, j, st2, cont)

    yield from _inst(items[idx], text, i, st, next_cont)


def _group(node: Group, text, i, st, cont) -> Iterator[int]:
    if node.gid == 0:
        yield from _inst(node.child, text, i, st, cont)
        return
    old = st.groups[node.gid]
    st.groups[node.gid] = [i, -1]

    def cap(j, st2):
        st2.groups[node.gid] = [i, j]
        try:
            yield from cont(j, st2)
        finally:
            st2.groups[node.gid] = old

    try:
        yield from _inst(node.child, text, i, st, cap)
    finally:
        st.groups[node.gid] = old


def _repeat(node: Repeat, text, i, st, cont) -> Iterator[int]:
    def step(pos, count):
        if node.greedy:
            # 先尝试再消费一次
            if count < node.mx:
                def after(j, st2):
                    if j == pos:  # 零宽进展，停止避免死循环
                        if count + 1 >= node.mn:
                            yield from cont(j, st2)
                        return
                    yield from step(j, count + 1)
                yield from _inst(node.atom, text, pos, st, after)
            if count >= node.mn:
                yield from cont(pos, st)
        else:  # 惰性：先满足 cont，再尝试消费
            if count >= node.mn:
                yield from cont(pos, st)
            if count < node.mx:
                def after(j, st2):
                    if j == pos:
                        return
                    yield from step(j, count + 1)
                yield from _inst(node.atom, text, pos, st, after)

    yield from step(i, 0)


# --------------------------------------------------------------------------- #
# 对外 API
# --------------------------------------------------------------------------- #
@dataclass
class Match:
    text: str
    span_: Tuple[int, int]
    groups_: list

    def group(self, g: int = 0):
        if g == 0:
            return self.text[self.span_[0]:self.span_[1]]
        rec = self.groups_[g] if g < len(self.groups_) else None
        return None if rec is None else self.text[rec[0]:rec[1]]

    def span(self, g: int = 0):
        if g == 0:
            return self.span_
        rec = self.groups_[g] if g < len(self.groups_) else None
        return None if rec is None else tuple(rec)

    def groups(self):
        return tuple(self.group(g) for g in range(1, len(self.groups_)))

    def __getitem__(self, g: int):
        return self.group(g)


class Pattern:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.ast, self.ngroups = parse_pattern(pattern)

    def _run_at(self, text: str, start: int) -> Optional[Match]:
        st = _State(self.ngroups)

        def terminal(i, _st):
            yield i

        for end in _inst(self.ast, text, start, st, terminal):
            return Match(text, (start, end),
                         [None if g is None else list(g) for g in st.groups])
        return None

    def search(self, text: str, pos: int = 0) -> Optional[Match]:
        for start in range(pos, len(text) + 1):
            m = self._run_at(text, start)
            if m is not None:
                return m
        return None

    def match(self, text: str) -> Optional[Match]:
        m = self._run_at(text, 0)
        return m

    def fullmatch(self, text: str) -> Optional[Match]:
        m = self.search(text)
        while m is not None:
            if m.span_[0] == 0 and m.span_[1] == len(text):
                return m
            m = self.search(text, m.span_[0] + 1)
        return None

    def finditer(self, text: str) -> Iterator[Match]:
        pos = 0
        while pos <= len(text):
            m = self.search(text, pos)
            if m is None:
                return
            yield m
            pos = m.span_[1] if m.span_[1] > pos else pos + 1

    def findall(self, text: str) -> list:
        out = []
        for m in self.finditer(text):
            if self.ngroups == 0:
                out.append(m.group(0))
            elif self.ngroups == 1:
                out.append(m.group(1))
            else:
                out.append(m.groups())
        return out


def compile(pattern: str) -> Pattern:
    return Pattern(pattern)


def search(pattern: str, text: str) -> Optional[Match]:
    return Pattern(pattern).search(text)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()


def _cmd_grep(args: argparse.Namespace) -> int:
    try:
        pat = Pattern(args.pattern)
        text = _read_input(args.input)
    except (RegexError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, OSError) else 1
    matched = 0
    for line in text.splitlines():
        if pat.search(line):
            print(line)
            matched += 1
    return 0 if matched else 1


def _cmd_find(args: argparse.Namespace) -> int:
    try:
        pat = Pattern(args.pattern)
        text = _read_input(args.input)
    except (RegexError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, OSError) else 1
    matches = list(pat.finditer(text))
    for m in matches:
        print(f"{m.span_[0]}-{m.span_[1]}: {m.group(0)!r}")
    print(f"共 {len(matches)} 处匹配")
    return 0 if matches else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="迷你正则引擎（回溯匹配）")
    sub = p.add_subparsers(dest="command", required=True)

    pg = sub.add_parser("grep", help="输出匹配的行（- 表示标准输入）")
    pg.add_argument("pattern")
    pg.add_argument("input")
    pg.set_defaults(func=_cmd_grep)

    pf = sub.add_parser("find", help="列出所有匹配的位置与内容")
    pf.add_argument("pattern")
    pf.add_argument("input")
    pf.set_defaults(func=_cmd_find)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
