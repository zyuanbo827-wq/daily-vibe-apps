"""expr.py -- 零依赖算术表达式求值器（调度场算法）。

支持：
  * 运算符  + - * / % ^（幂为右结合），以及一元 +/-
  * 括号、小数、科学计数法（1.5e-3、.5）
  * 常量 pi、e；函数 sqrt/abs/sin/cos/tan/asin/acos/atan/exp/ln/log/
    floor/ceil/round 以及变参 min/max
  * 用户变量（通过 evaluate(expr, variables) 传入，或在 REPL 中赋值）

实现路径：tokenize（词法） -> to_rpn（调度场，中缀转后缀） -> eval_rpn（栈求值）。

只使用 Python 标准库。
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


class ExprError(Exception):
    """表达式词法/语法/求值错误，message 面向最终用户。"""


# token: (kind, value, pos)；kind ∈ NUM / IDENT / OP / LPAREN / RPAREN / COMMA
Token = Tuple[str, Any, int]

_NUMBER_RE = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_BINARY = {
    "+": (1, "L"),
    "-": (1, "L"),
    "*": (2, "L"),
    "/": (2, "L"),
    "%": (2, "L"),
    # 幂右结合
    "^": (4, "R"),
}
# 一元 +/- 的优先级介于乘除与幂之间：
# 既保证 -2^2 == -(2^2) == -4，又保证 2^-2 == 0.25。
_UNARY_PREC = 3

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


def _fixed1(fn):
    return ("fixed", 1, fn)


_FUNCTIONS: Dict[str, Tuple[str, int, Any]] = {
    "sqrt": _fixed1(math.sqrt),
    "abs": _fixed1(abs),
    "sin": _fixed1(math.sin),
    "cos": _fixed1(math.cos),
    "tan": _fixed1(math.tan),
    "asin": _fixed1(math.asin),
    "acos": _fixed1(math.acos),
    "atan": _fixed1(math.atan),
    "exp": _fixed1(math.exp),
    "ln": _fixed1(math.log),
    "log": _fixed1(math.log10),
    "floor": _fixed1(math.floor),
    "ceil": _fixed1(math.ceil),
    "round": _fixed1(round),
    # 变参函数：至少 1 个参数
    "min": ("variadic", 1, min),
    "max": ("variadic", 1, max),
}


# --------------------------------------------------------------------------- #
# 词法分析
# --------------------------------------------------------------------------- #
def tokenize(text: str) -> List[Token]:
    """把表达式字符串切分为 token 列表。"""
    tokens: List[Token] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        m = _NUMBER_RE.match(text, i)
        if m:
            try:
                value = float(m.group())
            except ValueError as exc:  # pragma: no cover - 正则已限定格式
                raise ExprError(f"数字格式错误：{m.group()!r}（位置 {i}）") from exc
            tokens.append(("NUM", value, i))
            i = m.end()
            continue
        m = _IDENT_RE.match(text, i)
        if m:
            tokens.append(("IDENT", m.group(), i))
            i = m.end()
            continue
        if ch == "(":
            tokens.append(("LPAREN", ch, i))
        elif ch == ")":
            tokens.append(("RPAREN", ch, i))
        elif ch == ",":
            tokens.append(("COMMA", ch, i))
        elif ch in _BINARY:
            tokens.append(("OP", ch, i))
        else:
            raise ExprError(f"无法识别的字符 {ch!r}（位置 {i}）")
        i += 1
    return tokens


# --------------------------------------------------------------------------- #
# 调度场：中缀 -> 后缀（RPN）
# --------------------------------------------------------------------------- #
# 栈元素：
#   二元/一元运算符：str（一元为 "u-" / "u+"）
#   分组左括号："("
#   函数调用左括号：("call", 函数名)
# RPN 元素：float | ("var", name) | ("op", op) | ("call", name, argc)
StackItem = Any
RpnItem = Any


def to_rpn(text_or_tokens) -> List[RpnItem]:
    """中缀表达式转后缀 token 序列。"""
    tokens = tokenize(text_or_tokens) if isinstance(text_or_tokens, str) else text_or_tokens
    if not tokens:
        raise ExprError("表达式为空")

    output: List[RpnItem] = []
    stack: List[StackItem] = []
    # 与函数调用 marker 平行：逗号数 / 括号内是否已出现实参
    comma_counts: List[int] = []
    started: List[bool] = []

    def mark_started() -> None:
        # 实参/嵌套调用结果归属于当前最近的未闭合函数调用
        if started:
            started[-1] = True

    prev: Optional[Token] = None
    i = 0
    while i < len(tokens):
        kind, value, pos = tokens[i]
        if kind == "NUM":
            output.append(value)
            mark_started()
        elif kind == "IDENT":
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            if nxt is not None and nxt[0] == "LPAREN":
                if value not in _FUNCTIONS:
                    raise ExprError(f"未知函数 {value!r}（位置 {pos}）")
                # 函数调用：marker 在下、'(' 在上作为弹出屏障
                stack.append(("call", value))
                stack.append("(")
                comma_counts.append(0)
                started.append(False)
                i += 2  # 跳过 IDENT 与紧随的 LPAREN
                prev = nxt
                continue
            output.append(("var", value))
            mark_started()
        elif kind == "LPAREN":
            stack.append("(")
        elif kind == "RPAREN":
            while stack and stack[-1] != "(":
                output.append(("op", stack.pop()))
            if not stack:
                raise ExprError(f"括号不匹配：多余的 ')'（位置 {pos}）")
            stack.pop()  # 丢掉 '('
            if stack and isinstance(stack[-1], tuple) and stack[-1][0] == "call":
                _, name = stack.pop()
                commas = comma_counts.pop()
                has_arg = started.pop()
                argc = commas + 1 if has_arg else 0
                kind_spec, min_argc, _ = _FUNCTIONS[name]
                if kind_spec == "fixed":
                    if argc != min_argc:
                        raise ExprError(
                            f"函数 {name} 需要 {min_argc} 个参数，实际给出 {argc} 个（位置 {pos}）"
                        )
                elif argc < min_argc:
                    raise ExprError(f"函数 {name} 至少需要 {min_argc} 个参数（位置 {pos}）")
                output.append(("call", name, argc))
                mark_started()
        elif kind == "COMMA":
            if "(" not in stack:
                raise ExprError(f"逗号只能出现在函数调用参数中（位置 {pos}）")
            while stack and stack[-1] != "(":
                output.append(("op", stack.pop()))
            if comma_counts:
                comma_counts[-1] += 1
        elif kind == "OP":
            unary = value in "+-" and (
                prev is None or prev[0] in ("OP", "LPAREN", "COMMA")
            )
            if unary:
                stack.append("u-" if value == "-" else "u+")
            else:
                if value not in _BINARY:
                    raise ExprError(f"此处不应出现运算符 {value!r}（位置 {pos}）")
                prec, assoc = _BINARY[value]
                while stack and isinstance(stack[-1], str) and stack[-1] != "(":
                    top = stack[-1]
                    top_prec = _UNARY_PREC if top in ("u-", "u+") else _BINARY.get(top, (0,))[0]
                    if top_prec > prec or (top_prec == prec and assoc == "L"):
                        output.append(("op", stack.pop()))
                    else:
                        break
                stack.append(value)
        prev = tokens[i]
        i += 1

    while stack:
        item = stack.pop()
        if item == "(" or isinstance(item, tuple) and item[0] == "call":
            raise ExprError("括号不匹配：缺少 ')'")
        output.append(("op", item))
    return output


# --------------------------------------------------------------------------- #
# 后缀求值
# --------------------------------------------------------------------------- #
def eval_rpn(rpn: Sequence[RpnItem], variables: Optional[Dict[str, float]] = None) -> float:
    """对后缀序列做栈求值。"""
    env = dict(_CONSTANTS)
    if variables:
        env.update(variables)

    stack: List[float] = []
    for item in rpn:
        if isinstance(item, float):
            stack.append(item)
        elif isinstance(item, tuple) and item[0] == "var":
            name = item[1]
            if name not in env:
                raise ExprError(f"未知变量 {name!r}（可通过 variables 传入）")
            stack.append(float(env[name]))
        elif isinstance(item, tuple) and item[0] == "call":
            _, name, argc = item
            if len(stack) < argc:
                raise ExprError(f"函数 {name} 的参数不足")
            args = [stack.pop() for _ in range(argc)][::-1]
            kind_spec, _, fn = _FUNCTIONS[name]
            try:
                # 单参数的 min/max 直接返回自身（内置 min/max 不接受单个标量）
                if kind_spec == "variadic" and len(args) == 1:
                    stack.append(float(args[0]))
                else:
                    stack.append(float(fn(*args)))
            except ValueError as exc:
                raise ExprError(f"函数 {name} 的参数超出定义域：{exc}") from exc
        elif isinstance(item, tuple) and item[0] == "op":
            op = item[1]
            if op in ("u-", "u+"):
                if not stack:
                    raise ExprError("表达式不完整：缺少操作数")
                x = stack.pop()
                stack.append(-x if op == "u-" else +x)
                continue
            if len(stack) < 2:
                raise ExprError(f"表达式不完整：运算符 {op!r} 缺少操作数")
            b, a = stack.pop(), stack.pop()
            if op == "+":
                stack.append(a + b)
            elif op == "-":
                stack.append(a - b)
            elif op == "*":
                stack.append(a * b)
            elif op == "/":
                if b == 0:
                    raise ExprError("除数为零")
                stack.append(a / b)
            elif op == "%":
                if b == 0:
                    raise ExprError("取模时除数为零")
                stack.append(math.fmod(a, b))
            elif op == "^":
                try:
                    stack.append(math.pow(a, b))
                except ValueError as exc:
                    raise ExprError(f"幂运算定义域错误：{exc}") from exc
    if len(stack) != 1:
        raise ExprError("表达式不完整：存在未参与运算的数字")
    result = stack[0]
    if not math.isfinite(result):
        raise ExprError("运算结果不是有限数（无穷大或 NaN）")
    return result


def evaluate(text: str, variables: Optional[Dict[str, float]] = None) -> float:
    """求值入口：中缀表达式字符串 -> float 结果。"""
    return eval_rpn(to_rpn(tokenize(text)), variables)


def format_result(x: float) -> str:
    """把结果格式化为人类可读字符串：整值不带 .0。"""
    if abs(x) < 1e16 and float(x).is_integer():
        return str(int(x))
    return f"{x:.12g}"


def rpn_to_text(rpn: Sequence[RpnItem]) -> str:
    """把后缀序列渲染成可读字符串，便于调试/教学。"""
    parts = []
    for item in rpn:
        if isinstance(item, float):
            parts.append(format_result(item))
        elif item[0] == "var":
            parts.append(item[1])
        elif item[0] == "op":
            parts.append(item[1])
        elif item[0] == "call":
            parts.append(f"{item[1]}/{item[2]}")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# CLI / REPL
# --------------------------------------------------------------------------- #
_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", re.S)


def repl() -> int:
    """交互式 REPL，支持 name = expr 赋值、vars/help/quit 命令。"""
    scope: Dict[str, float] = {}
    print("expr 求值器 REPL（输入 help 查看帮助，quit 退出）")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        low = line.lower()
        if low in ("quit", "exit"):
            return 0
        if low == "help":
            print(
                "示例：\n"
                "  1 + 2 * 3\n"
                "  sqrt(2) ^ 2\n"
                "  x = 3        （赋值变量）\n"
                "  x^2 + 4*x\n"
                "  min(3, -1, 2.5)\n"
                "  vars         （查看变量）\n"
                "  quit         （退出）"
            )
            continue
        if low == "vars":
            if scope:
                print(", ".join(f"{k} = {format_result(v)}" for k, v in scope.items()))
            else:
                print("（暂无变量）")
            continue
        m = _ASSIGN_RE.match(line)
        if m:
            name, expr_text = m.group(1), m.group(2).strip()
            if name in _FUNCTIONS:
                print(f"error: {name} 是内置函数名，不能作为变量名")
                continue
            try:
                scope[name] = evaluate(expr_text, scope)
            except ExprError as exc:
                print(f"error: {exc}")
                continue
            print(f"{name} = {format_result(scope[name])}")
            continue
        try:
            print(format_result(evaluate(line, scope)))
        except ExprError as exc:
            print(f"error: {exc}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return repl()
    show_rpn = False
    if args[0] == "--rpn":
        show_rpn = True
        args = args[1:]
    if not args:
        print("usage: python expr.py [--rpn] \"expression\"", file=sys.stderr)
        return 2
    expr_text = " ".join(args)
    try:
        rpn = to_rpn(tokenize(expr_text))
        if show_rpn:
            print("RPN:", rpn_to_text(rpn))
        print(format_result(eval_rpn(rpn)))
    except ExprError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
