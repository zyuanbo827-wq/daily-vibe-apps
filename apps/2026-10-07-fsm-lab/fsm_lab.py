"""fsm_lab.py -- 零依赖有限状态机实验台（DFA / NFA / 确定化）。

支持 DFA 与带 epsilon 边的 NFA：DFA 逐字符模拟并给出状态轨迹；
NFA 用 epsilon 闭包 + 子集模拟；并通过子集构造把 NFA 确定化为
等价 DFA。机器用 JSON 定义，CLI 可运行输入串、转换 NFA、演示。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

EPSILON = ""


class FsmError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# DFA
# --------------------------------------------------------------------------- #
class DFA:
    def __init__(self, states: List[str], alphabet: List[str],
                 transitions: Dict[str, Dict[str, str]],
                 start: str, accept: List[str]):
        self.states = states
        self.alphabet = alphabet
        self.transitions = transitions
        self.start = start
        self.accept = set(accept)
        self._validate()

    def _validate(self) -> None:
        if self.start not in self.states:
            raise FsmError("起始状态不在状态集中")
        if not self.accept <= set(self.states):
            raise FsmError("接受状态不在状态集中")

    def step(self, state: str, symbol: str) -> Optional[str]:
        if symbol not in self.alphabet:
            raise FsmError(f"非法输入符号: {symbol!r}")
        return self.transitions.get(state, {}).get(symbol)

    def run(self, text: str) -> Tuple[bool, List[str]]:
        state = self.start
        trace = [state]
        for symbol in text:
            state = self.step(state, symbol)
            trace.append(state if state else "(dead)")
            if state is None:
                return False, trace
        return state in self.accept, trace

    def to_dict(self) -> dict:
        return {"type": "dfa", "states": self.states,
                "alphabet": self.alphabet, "start": self.start,
                "accept": sorted(self.accept),
                "transitions": self.transitions}


# --------------------------------------------------------------------------- #
# NFA
# --------------------------------------------------------------------------- #
class NFA:
    def __init__(self, states: List[str], alphabet: List[str],
                 transitions: Dict[str, Dict[str, List[str]]],
                 start: str, accept: List[str]):
        self.states = states
        self.alphabet = alphabet
        self.transitions = transitions
        self.start = start
        self.accept = set(accept)
        if start not in states or not self.accept <= set(states):
            raise FsmError("起始/接受状态不合法")

    def epsilon_closure(self, states: Set[str]) -> Set[str]:
        stack = list(states)
        closure = set(states)
        while stack:
            s = stack.pop()
            for t in self.transitions.get(s, {}).get(EPSILON, []):
                if t not in closure:
                    closure.add(t)
                    stack.append(t)
        return closure

    def move(self, states: Set[str], symbol: str) -> Set[str]:
        result: Set[str] = set()
        for s in states:
            result.update(self.transitions.get(s, {}).get(symbol, []))
        return result

    def accepts(self, text: str) -> bool:
        current = self.epsilon_closure({self.start})
        for symbol in text:
            if symbol not in self.alphabet:
                raise FsmError(f"非法输入符号: {symbol!r}")
            current = self.epsilon_closure(self.move(current, symbol))
            if not current:
                return False
        return bool(current & self.accept)

    # ------------------------------------------------------------------ #
    # 子集构造确定化
    # ------------------------------------------------------------------ #
    def determinize(self) -> DFA:
        start_set = frozenset(self.epsilon_closure({self.start}))
        labels: Dict[FrozenSet[str], str] = {}
        work: List[FrozenSet[str]] = []

        def label(sub: FrozenSet[str]) -> str:
            if sub not in labels:
                labels[sub] = "{" + ",".join(sorted(sub)) + "}"
                work.append(sub)
            return labels[sub]

        start_label = label(start_set)
        dfa_trans: Dict[str, Dict[str, str]] = {}
        dfa_accept: List[str] = []

        while work:
            sub = work.pop(0)
            src = label(sub)
            dfa_trans.setdefault(src, {})
            if sub & self.accept:
                dfa_accept.append(src)
            for symbol in self.alphabet:
                nxt = frozenset(self.epsilon_closure(self.move(set(sub),
                                                             symbol)))
                if not nxt:
                    continue
                dfa_trans[src][symbol] = label(nxt)

        return DFA(list(labels.values()), list(self.alphabet), dfa_trans,
                   start_label, dfa_accept)

    def to_dict(self) -> dict:
        return {"type": "nfa", "states": self.states,
                "alphabet": self.alphabet, "start": self.start,
                "accept": sorted(self.accept),
                "transitions": self.transitions}


# --------------------------------------------------------------------------- #
# JSON 装载
# --------------------------------------------------------------------------- #
def from_dict(data: dict):
    kind = data.get("type")
    if kind not in ("dfa", "nfa"):
        raise FsmError("type 必须为 dfa 或 nfa")
    common = (data["states"], data["alphabet"], data["transitions"],
              data["start"], data["accept"])
    if kind == "dfa":
        return DFA(*common)
    return NFA(*common)


def load_machine(path: str):
    if path == "-":
        data = json.loads(sys.stdin.read())
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise SystemExit(2)
    return from_dict(data)


# --------------------------------------------------------------------------- #
# 预置机器
# --------------------------------------------------------------------------- #
def ending_one_dfa() -> DFA:
    # 二进制串以 1 结尾
    return DFA(["q0", "q1"], ["0", "1"],
               {"q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q0", "1": "q1"}},
               "q0", ["q1"])


def containing_ab_nfa() -> NFA:
    # 含子串 ab
    return NFA(["q0", "q1", "q2"], ["a", "b"],
               {"q0": {"a": ["q0", "q1"], "b": ["q0"]},
                "q1": {"b": ["q2"]},
                "q2": {"a": ["q2"], "b": ["q2"]}},
               "q0", ["q2"])


def epsilon_nfa() -> NFA:
    # epsilon 边：语言 {1, 10}
    return NFA(["s", "a", "b", "c"], ["0", "1"],
               {"s": {"1": ["a"], "": ["b"]},
                "b": {"1": ["c"]},
                "c": {"0": ["a"]}},
               "s", ["a"])


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_run(args) -> int:
    machine = load_machine(args.file)
    if isinstance(machine, DFA):
        ok, trace = machine.run(args.input)
        print("trace:", " -> ".join(trace))
    else:
        ok = machine.accepts(args.input)
    print("accept" if ok else "reject")
    return 0 if ok else 1


def cmd_convert(args) -> int:
    machine = load_machine(args.file)
    if not isinstance(machine, NFA):
        raise FsmError("convert 仅接受 NFA")
    print(json.dumps(machine.determinize().to_dict(), ensure_ascii=False,
                     indent=2))
    return 0


def cmd_demo(args) -> int:
    dfa = ending_one_dfa()
    for s in ("1", "01", "10", "1010"):
        ok, trace = dfa.run(s)
        print(f"DFA end-in-1  {s:>5} -> {'accept' if ok else 'reject'}  "
              f"[{' -> '.join(trace)}]")

    nfa = containing_ab_nfa()
    print()
    for s in ("ba", "ab", "aab", "bbb"):
        print(f"NFA has 'ab'  {s:>5} -> "
              f"{'accept' if nfa.accepts(s) else 'reject'}")

    det = nfa.determinize()
    print(f"\nNFA determinized: {len(det.states)} DFA states -> "
          f"{det.states}")
    cases = ("ab", "ba", "aab", "aba", "bbb", "bba")
    agree = all(nfa.accepts(s) == det.run(s)[0] for s in cases)
    print("equivalence check on", cases, "->", "AGREE" if agree else "DIFFER")

    enfa = epsilon_nfa()
    print("\nepsilon NFA language {1,10}:")
    for s in ("1", "10", "01", "11"):
        print(f"  {s:>3} -> {'accept' if enfa.accepts(s) else 'reject'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="有限状态机实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("run", help="在机器上运行输入串")
    pr.add_argument("file")
    pr.add_argument("input")
    pr.set_defaults(func=cmd_run)

    pc = sub.add_parser("convert", help="NFA 子集构造确定化为 DFA")
    pc.add_argument("file")
    pc.set_defaults(func=cmd_convert)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FsmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
