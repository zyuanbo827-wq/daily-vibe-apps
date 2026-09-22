"""jsonlite.py -- 零依赖 JSON 解析 / 格式化 / 路径查询工具。

手写递归下降 JSON 解析器（不使用标准库 json 完成解析），支持：
  * 完整 JSON 语法：对象、数组、字符串转义（含 \\uXXXX 与代理对）、
    数字（小数 / 指数）、null/true/false；严格拒绝注释、尾逗号、单引号、
    NaN/Infinity、前导零等非法写法，错误带行列号
  * minify / pretty 序列化
  * 极简路径查询：a.b[0].c 或 $["a"]["b"][-1]

附带 validate / get / pretty / minify 四个 CLI 子命令。
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, List, Tuple

# --------------------------------------------------------------------------- #
# 异常
# --------------------------------------------------------------------------- #


class JSONError(ValueError):
    def __init__(self, message: str, line: int = 0, col: int = 0):
        self.line = line
        self.col = col
        if line:
            super().__init__(f"{message} (第 {line} 行, 第 {col} 列)")
        else:
            super().__init__(message)


# --------------------------------------------------------------------------- #
# 词法 / 递归下降解析
# --------------------------------------------------------------------------- #
_ESCAPES = {
    '"': '"', "\\": "\\", "/": "/", "b": "\b",
    "f": "\f", "n": "\n", "r": "\r", "t": "\t",
}


class _Parser:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    # -- 基础工具 ---------------------------------------------------------- #
    def error(self, message: str) -> JSONError:
        line = self.s.count("\n", 0, self.i) + 1
        last_nl = self.s.rfind("\n", 0, self.i)
        col = self.i - last_nl if last_nl >= 0 else self.i + 1
        return JSONError(message, line, col)

    def skip_ws(self) -> None:
        while self.i < self.n and self.s[self.i] in " \t\r\n":
            self.i += 1

    def peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    def expect(self, ch: str, what: str) -> None:
        if self.peek() != ch:
            raise self.error(f"期望 {what}")
        self.i += 1

    # -- 值 --------------------------------------------------------------- #
    def parse_value(self) -> Any:
        self.skip_ws()
        ch = self.peek()
        if ch == "{":
            return self.parse_object()
        if ch == "[":
            return self.parse_array()
        if ch == '"':
            return self.parse_string()
        if ch == "-" or ch.isdigit():
            return self.parse_number()
        if self.s.startswith("true", self.i):
            self.i += 4
            return True
        if self.s.startswith("false", self.i):
            self.i += 5
            return False
        if self.s.startswith("null", self.i):
            self.i += 4
            return None
        if ch == "":
            raise self.error("意外的输入结尾")
        raise self.error(f"无法识别的字符 {ch!r}")

    def parse_object(self) -> dict:
        self.expect("{", "'{'")
        obj: dict = {}
        self.skip_ws()
        if self.peek() == "}":
            self.i += 1
            return obj
        while True:
            self.skip_ws()
            if self.peek() != '"':
                raise self.error("对象键必须是双引号字符串")
            key = self.parse_string()
            self.skip_ws()
            self.expect(":", "':'")
            obj[key] = self.parse_value()
            self.skip_ws()
            ch = self.peek()
            if ch == ",":
                self.i += 1
                self.skip_ws()
                if self.peek() == "}":
                    raise self.error("对象不允许尾逗号")
                continue
            if ch == "}":
                self.i += 1
                return obj
            raise self.error("对象成员之间需要 ','")

    def parse_array(self) -> list:
        self.expect("[", "'['")
        arr: list = []
        self.skip_ws()
        if self.peek() == "]":
            self.i += 1
            return arr
        while True:
            arr.append(self.parse_value())
            self.skip_ws()
            ch = self.peek()
            if ch == ",":
                self.i += 1
                self.skip_ws()
                if self.peek() == "]":
                    raise self.error("数组不允许尾逗号")
                continue
            if ch == "]":
                self.i += 1
                return arr
            raise self.error("数组元素之间需要 ','")

    def parse_string(self) -> str:
        self.expect('"', '字符串')
        out: List[str] = []
        while True:
            if self.i >= self.n:
                raise self.error("字符串未闭合")
            ch = self.s[self.i]
            if ch == '"':
                self.i += 1
                return "".join(out)
            if ch == "\\":
                self.i += 1
                if self.i >= self.n:
                    raise self.error("转义序列不完整")
                e = self.s[self.i]
                if e in _ESCAPES:
                    out.append(_ESCAPES[e])
                    self.i += 1
                elif e == "u":
                    out.append(self.parse_unicode_escape())
                else:
                    raise self.error(f"非法转义 \\{e}")
            elif ord(ch) < 0x20:
                raise self.error("字符串内出现未转义的控制字符")
            else:
                out.append(ch)
                self.i += 1

    def parse_unicode_escape(self) -> str:
        def hex4() -> int:
            hexd = self.s[self.i:self.i + 4]
            if len(hexd) != 4 or any(c not in "0123456789abcdefABCDEF"
                                     for c in hexd):
                raise self.error("\\u 转义需要 4 位十六进制数")
            self.i += 4
            return int(hexd, 16)

        self.i += 1  # 跳过 'u'
        cp = hex4()
        if 0xD800 <= cp <= 0xDBFF:  # 高代理项，必须跟 \\u 低代理项
            if self.s[self.i:self.i + 2] != "\\u":
                raise self.error("高代理项后必须紧跟 \\u 低代理项")
            self.i += 2
            low = hex4()
            if not 0xDC00 <= low <= 0xDFFF:
                raise self.error("代理对的低代理项非法")
            cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00)
        elif 0xDC00 <= cp <= 0xDFFF:
            raise self.error("出现孤立的低代理项")
        return chr(cp)

    def parse_number(self) -> Any:
        start = self.i
        if self.peek() == "-":
            self.i += 1
        if self.peek() == "0":
            self.i += 1
            if self.peek().isdigit():
                raise self.error("数字不允许前导零")
        elif self.peek().isdigit():
            while self.peek().isdigit():
                self.i += 1
        else:
            raise self.error("数字格式错误")

        is_float = False
        if self.peek() == ".":
            is_float = True
            self.i += 1
            if not self.peek().isdigit():
                raise self.error("小数部分至少需要一位数字")
            while self.peek().isdigit():
                self.i += 1
        if self.peek() in ("e", "E"):
            is_float = True
            self.i += 1
            if self.peek() in ("+", "-"):
                self.i += 1
            if not self.peek().isdigit():
                raise self.error("指数部分至少需要一位数字")
            while self.peek().isdigit():
                self.i += 1
        token = self.s[start:self.i]
        return float(token) if is_float else int(token)


def loads(text: str) -> Any:
    """解析 JSON 文本；非法输入抛 JSONError（带行列号）。"""
    parser = _Parser(text)
    value = parser.parse_value()
    parser.skip_ws()
    if parser.i != parser.n:
        raise parser.error("JSON 值之后存在多余字符")
    return value


# --------------------------------------------------------------------------- #
# 序列化
# --------------------------------------------------------------------------- #
def _escape_string(s: str) -> str:
    out = ['"']
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _check_type(obj: Any) -> None:
    if obj is None or isinstance(obj, (bool, int, str)):
        return
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise JSONError("JSON 不支持 NaN / Infinity")
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _check_type(item)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise JSONError("对象键必须是字符串")
            _check_type(v)
        return
    raise JSONError(f"类型 {type(obj).__name__} 不能序列化为 JSON")


def dumps(obj: Any, indent: int = None) -> str:
    _check_type(obj)

    def emit(value: Any, depth: int) -> str:
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, str):
            return _escape_string(value)
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (list, tuple)):
            if not value:
                return "[]"
            if indent is None:
                return "[" + ",".join(emit(v, depth + 1) for v in value) + "]"
            pad = "\n" + " " * indent * (depth + 1)
            close = "\n" + " " * indent * depth + "]"
            return "[" + pad + ("," + pad).join(
                emit(v, depth + 1) for v in value) + close
        if isinstance(value, dict):
            if not value:
                return "{}"
            if indent is None:
                return "{" + ",".join(
                    _escape_string(k) + ":" + emit(v, depth + 1)
                    for k, v in value.items()) + "}"
            pad = "\n" + " " * indent * (depth + 1)
            close = "\n" + " " * indent * depth + "}"
            body = ("," + pad).join(
                _escape_string(k) + ": " + emit(v, depth + 1)
                for k, v in value.items())
            return "{" + pad + body + close
        raise JSONError("不可序列化的值")  # _check_type 已兜底

    return emit(obj, 0)


# --------------------------------------------------------------------------- #
# 极简路径查询：a.b[0].c / $["a"]["b"][-1]
# --------------------------------------------------------------------------- #
def _parse_path(path: str) -> List[Any]:
    segments: List[Any] = []
    i, n = 0, len(path)
    if path.startswith("$"):
        i = 1
    while i < n:
        ch = path[i]
        if ch == ".":
            i += 1
            start = i
            while i < n and path[i] not in ".[":
                i += 1
            key = path[start:i]
            if not key:
                raise JSONError("路径中 '.' 后缺少键名")
            segments.append(key)
        elif ch == "[":
            i += 1
            if i < n and path[i] in ('"', "'"):
                quote = path[i]
                i += 1
                start = i
                while i < n and path[i] != quote:
                    i += 1
                if i >= n:
                    raise JSONError("路径中引号未闭合")
                segments.append(path[start:i])
                i += 1  # 跳过结束引号
            else:
                start = i
                while i < n and path[i] != "]":
                    i += 1
                num = path[start:i].strip()
                try:
                    segments.append(int(num))
                except ValueError:
                    raise JSONError(f"路径下标必须是整数：{num!r}")
            if i >= n or path[i] != "]":
                raise JSONError("路径中缺少 ']'")
            i += 1
        else:
            # 允许直接以裸键开头（如 "a.b"）
            start = i
            while i < n and path[i] not in ".[":
                i += 1
            segments.append(path[start:i])
    return segments


def query(obj: Any, path: str) -> Any:
    cur = obj
    for seg in _parse_path(path):
        if isinstance(seg, int):
            if not isinstance(cur, list):
                raise JSONError(f"下标 {seg} 只能用于数组")
            idx = seg if seg >= 0 else len(cur) + seg
            if not 0 <= idx < len(cur):
                raise JSONError(f"数组下标越界：{seg}（长度 {len(cur)}）")
            cur = cur[idx]
        else:
            if not isinstance(cur, dict):
                raise JSONError(f"键 {seg!r} 只能用于对象")
            if seg not in cur:
                raise JSONError(f"对象不存在键 {seg!r}")
            cur = cur[seg]
    return cur


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()


def _load(path: str) -> Any:
    return loads(_read_input(path))


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        value = _load(args.input)
    except (JSONError, OSError) as exc:
        print(f"无效：{exc}")
        return 2 if isinstance(exc, OSError) else 1
    kind = type(value).__name__
    print(f"JSON 合法：顶层类型 {kind}")
    return 0


def _cmd_get(args: argparse.Namespace) -> int:
    try:
        value = query(_load(args.input), args.path)
    except (JSONError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, OSError) else 1
    if isinstance(value, (dict, list)):
        print(dumps(value, indent=2))
    else:
        print(dumps(value))
    return 0


def _cmd_pretty(args: argparse.Namespace) -> int:
    try:
        value = _load(args.input)
    except (JSONError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, OSError) else 1
    print(dumps(value, indent=args.indent))
    return 0


def _cmd_minify(args: argparse.Namespace) -> int:
    try:
        value = _load(args.input)
    except (JSONError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, OSError) else 1
    print(dumps(value))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="手写 JSON 解析 / 格式化 / 路径查询")
    sub = p.add_subparsers(dest="command", required=True)

    pv = sub.add_parser("validate", help="校验 JSON 是否合法（- 表示标准输入）")
    pv.add_argument("input")
    pv.set_defaults(func=_cmd_validate)

    pg = sub.add_parser("get", help="按路径取值，如 a.b[0].name")
    pg.add_argument("input")
    pg.add_argument("path")
    pg.set_defaults(func=_cmd_get)

    pp = sub.add_parser("pretty", help="美化输出")
    pp.add_argument("input")
    pp.add_argument("-i", "--indent", type=int, default=2)
    pp.set_defaults(func=_cmd_pretty)

    pm = sub.add_parser("minify", help="压缩为单行")
    pm.add_argument("input")
    pm.set_defaults(func=_cmd_minify)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
