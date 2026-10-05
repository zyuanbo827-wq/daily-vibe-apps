"""csvkit_lite.py -- 零依赖 CSV 处理小工具（手写 RFC 4180 解析）。

手写 CSV 解析器（支持引号包裹、双引号转义、字段内嵌逗号/换行、
CRLF），提供列选择、过滤、排序、limit、JSON/Markdown 导出与
分组聚合统计，通过 CLI 对 CSV 文件做查询。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Callable, Dict, List, Optional, Sequence


class CsvError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# 手写 CSV 解析与序列化（RFC 4180）
# --------------------------------------------------------------------------- #
def parse_csv(text: str) -> List[List[str]]:
    if text.startswith("\ufeff"):          # 去 BOM
        text = text[1:]
    rows: List[List[str]] = []
    field: List[str] = []
    row: List[str] = []
    i, n = 0, len(text)
    in_quotes = False

    def end_field():
        row.append("".join(field))
        field.clear()

    def end_row():
        end_field()
        rows.append(row)

    while i < n:
        c = text[i]
        if in_quotes:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                    continue
                in_quotes = False
                i += 1
                continue
            field.append(c)
            i += 1
            continue

        if c == '"':
            if field or (row and i > 0 and text[i - 1] not in ",\n\r"):
                raise CsvError("引号只能出现在字段开头")
            in_quotes = True
            i += 1
        elif c == ",":
            end_field()
            i += 1
        elif c == "\n":
            end_row()
            row = []
            i += 1
        elif c == "\r":
            end_row()
            row = []
            i += 2 if i + 1 < n and text[i + 1] == "\n" else 1
        else:
            field.append(c)
            i += 1

    if in_quotes:
        raise CsvError("未闭合的引号")
    # 最后一行：有内容或刚结束字段才输出；纯尾随换行不产生空行
    if field or row:
        end_field()
        rows.append(row)
    return rows


def needs_quoting(value: str) -> bool:
    return any(ch in value for ch in (",", '"', "\n", "\r"))


def write_csv(rows: Sequence[Sequence[str]]) -> str:
    out_lines = []
    for row in rows:
        fields = []
        for value in row:
            if needs_quoting(value):
                value = '"' + value.replace('"', '""') + '"'
            fields.append(value)
        out_lines.append(",".join(fields))
    return "\r\n".join(out_lines)


# --------------------------------------------------------------------------- #
# 表操作
# --------------------------------------------------------------------------- #
class Table:
    def __init__(self, headers: List[str], rows: List[List[str]]):
        self.headers = headers
        self.rows = rows

    @classmethod
    def from_text(cls, text: str) -> "Table":
        data = parse_csv(text)
        if not data:
            raise CsvError("空 CSV")
        headers, rows = data[0], data[1:]
        width = len(headers)
        for r in rows:
            if len(r) != width:
                raise CsvError("行列数与表头不一致")
        return cls(headers, rows)

    def dicts(self) -> List[Dict[str, str]]:
        return [dict(zip(self.headers, r)) for r in self.rows]

    def index(self, col: str) -> int:
        try:
            return self.headers.index(col)
        except ValueError:
            raise CsvError(f"未知列: {col}")

    def select(self, cols: Sequence[str]) -> "Table":
        if cols == ["*"]:
            return self
        idx = [self.index(c) for c in cols]
        return Table([self.headers[i] for i in idx],
                     [[r[i] for i in idx] for r in self.rows])

    def filter(self, expression: str) -> "Table":
        col, op, expected = parse_filter(expression)
        ci = self.index(col)
        kept = [r for r in self.rows if compare(r[ci], op, expected)]
        return Table(self.headers, kept)

    def sort(self, col: str, desc: bool = False) -> "Table":
        ci = self.index(col)
        return Table(self.headers,
                     sorted(self.rows, key=lambda r: sort_key(r[ci]),
                            reverse=desc))

    def limit(self, count: int) -> "Table":
        return Table(self.headers, self.rows[:count])

    def to_csv(self) -> str:
        return write_csv([self.headers] + self.rows)

    def to_json(self) -> str:
        return json.dumps(self.dicts(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        def esc(v: str) -> str:
            return v.replace("|", "\\|").replace("\n", " ")
        lines = ["| " + " | ".join(esc(h) for h in self.headers) + " |",
                 "| " + " | ".join("---" for _ in self.headers) + " |"]
        for r in self.rows:
            lines.append("| " + " | ".join(esc(v) for v in r) + " |")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 过滤表达式
# --------------------------------------------------------------------------- #
OPS = (">=", "<=", "!=", "=", ">", "<", "contains")


def parse_filter(expression: str):
    for op in OPS:
        if op in expression:
            col, value = expression.split(op, 1)
            return col.strip(), op, value.strip()
    raise CsvError("过滤表达式需包含 = != > < >= <= contains")


def maybe_number(value: str):
    try:
        return float(value)
    except ValueError:
        return value


def compare(actual: str, op: str, expected: str) -> bool:
    a, e = maybe_number(actual), maybe_number(expected)
    if op == "contains":
        return expected in actual
    ops = {"=": lambda x, y: x == y, "!=": lambda x, y: x != y,
           ">": lambda x, y: x > y, "<": lambda x, y: x < y,
           ">=": lambda x, y: x >= y, "<=": lambda x, y: x <= y}
    return ops[op](a, e)


def sort_key(value: str):
    num = maybe_number(value)
    return (1, num) if isinstance(num, float) else (0, value)


# --------------------------------------------------------------------------- #
# 分组聚合
# --------------------------------------------------------------------------- #
AGG_FUNCS = ("count", "sum", "avg", "min", "max")


def aggregate(table: Table, group_by: Optional[str],
               aggs: Sequence[str]) -> Table:
    gi = table.index(group_by) if group_by else None
    groups: Dict[str, List[List[str]]] = {}
    order: List[str] = []
    for r in table.rows:
        key = r[gi] if gi is not None else "(all)"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    headers = ([group_by] if group_by else []) + list(aggs)
    rows = []
    for key in order:
        row = [key] if group_by else []
        for agg in aggs:
            row.append(compute_agg(agg, groups[key], table))
        rows.append(row)
    return Table(headers, rows)


def compute_agg(agg: str, rows: List[List[str]], table: Table) -> str:
    if agg == "count":
        return str(len(rows))
    func, col = agg.split(":", 1)
    if func not in AGG_FUNCS:
        raise CsvError(f"未知聚合: {func}")
    ci = table.index(col)
    values = [float(r[ci]) for r in rows]
    if func == "sum":
        return f"{sum(values):g}"
    if func == "avg":
        return f"{sum(values) / len(values):g}"
    if func == "min":
        return f"{min(values):g}"
    return f"{max(values):g}"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
DEMO_CSV = (
    "name,dept,salary,age\r\n"
    "Alice,Engineering,12000,28\r\n"
    "Bob,Sales,8000,35\r\n"
    "Carol,Engineering,15000,41\r\n"
    "Dave,Sales,9000,30\r\n"
    "Eve,Engineering,11000,26\r\n"
)


def read_file(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except FileNotFoundError:
        raise SystemExit(2)


def apply_query(table: Table, args) -> Table:
    if args.filter:
        for expr in args.filter:
            table = table.filter(expr)
    if args.sort:
        table = table.sort(args.sort, args.desc)
    if args.limit is not None:
        table = table.limit(args.limit)
    if args.select:
        cols = [c.strip() for c in args.select.split(",")]
        table = table.select(cols)
    return table


def cmd_query(args) -> int:
    table = apply_query(Table.from_text(read_file(args.file)), args)
    fmt = args.format
    print({"csv": table.to_csv, "json": table.to_json,
           "md": table.to_markdown}[fmt]())
    return 0


def cmd_stats(args) -> int:
    table = Table.from_text(read_file(args.file))
    aggs = [a.strip() for a in args.agg.split(",")]
    result = aggregate(table, args.by, aggs)
    print({"csv": result.to_csv, "json": result.to_json,
           "md": result.to_markdown}[args.format]())
    return 0


def cmd_demo(args) -> int:
    table = Table.from_text(DEMO_CSV)
    print("# engineering staff under 40, salary desc -> json")
    q = apply_query(table, argparse.Namespace(
        filter=["dept=Engineering", "age<40"], sort="salary", desc=True,
        limit=None, select="name,salary,age"))
    print(q.to_json())
    print("\n# salary stats by dept -> markdown")
    print(aggregate(Table.from_text(DEMO_CSV), "dept",
                    ["count", "sum:salary", "avg:salary"]).to_markdown())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CSV 查询小工具（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pq = sub.add_parser("query")
    pq.add_argument("file")
    pq.add_argument("--select", default="*")
    pq.add_argument("--filter", action="append")
    pq.add_argument("--sort")
    pq.add_argument("--desc", action="store_true")
    pq.add_argument("--limit", type=int)
    pq.add_argument("--format", choices=("csv", "json", "md"), default="csv")
    pq.set_defaults(func=cmd_query)

    ps = sub.add_parser("stats")
    ps.add_argument("file")
    ps.add_argument("--by")
    ps.add_argument("--agg", required=True)
    ps.add_argument("--format", choices=("csv", "json", "md"), default="md")
    ps.set_defaults(func=cmd_stats)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
