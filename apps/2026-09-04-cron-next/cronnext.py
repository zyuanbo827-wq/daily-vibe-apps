"""cron-next：零依赖的 cron 表达式解析与下一次执行时间计算器（仅标准库）。

支持标准 5 字段：分 时 日(月) 月 周；支持 ``*``、数字、逗号列表 ``1,3,5``、
区间 ``1-5``、步长 ``*/15`` 与 ``9-18/2``。日与周同时限制时遵循 Vixie cron
的"或"规则（二者任一匹配即触发）。

命令行用法：
    python cronnext.py "*/15 9-18 * * 1-5" -n 5
    python cronnext.py "30 19 * * *" --from "2026-09-04 19:33" -n 3
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Set

FIELD_RANGES = {
    "minute": (0, 59),
    "hour": (0, 23),
    "dom": (1, 31),
    "month": (1, 12),
    "dow": (0, 7),  # 0/7 都是周日
}


def parse_field(spec: str, lo: int, hi: int) -> Set[int]:
    """解析单个 cron 字段为允许的整数集合。"""
    if spec == "":
        raise ValueError("empty field")
    values: Set[int] = set()
    for piece in spec.split(","):
        step = 1
        if "/" in piece:
            range_part, step_part = piece.split("/", 1)
            if not step_part.isdigit() or int(step_part) < 1:
                raise ValueError(f"invalid step in {piece!r}")
            step = int(step_part)
        else:
            range_part = piece

        if range_part == "*":
            start, end = lo, hi
        elif "-" in range_part:
            a, b = range_part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                raise ValueError(f"invalid range {piece!r}")
            start, end = int(a), int(b)
        elif range_part.isdigit():
            if "/" in piece:  # 形如 5/10，等价于 5-hi/10
                start, end = int(range_part), hi
            else:
                start = end = int(range_part)
        else:
            raise ValueError(f"invalid field piece {piece!r}")

        if not (lo <= start <= end <= hi):
            raise ValueError(f"value out of range [{lo},{hi}]: {piece!r}")
        values.update(range(start, end + 1, step))

    if not values:
        raise ValueError(f"field {spec!r} matches nothing")
    return values


@dataclass(frozen=True)
class CronExpr:
    minute: Set[int]
    hour: Set[int]
    dom: Set[int]
    month: Set[int]
    dow: Set[int]
    raw: str

    @classmethod
    def parse(cls, expression: str) -> "CronExpr":
        fields = expression.split()
        if len(fields) != 5:
            raise ValueError(f"cron expression needs exactly 5 fields, got {len(fields)}")
        m, h, dom, mon, dow = fields
        dow_values = parse_field(dow, *FIELD_RANGES["dow"])
        if 7 in dow_values:  # 7 归一化为周日 0
            dow_values.discard(7)
            dow_values.add(0)
        return cls(
            minute=parse_field(m, *FIELD_RANGES["minute"]),
            hour=parse_field(h, *FIELD_RANGES["hour"]),
            dom=parse_field(dom, *FIELD_RANGES["dom"]),
            month=parse_field(mon, *FIELD_RANGES["month"]),
            dow=dow_values,
            raw=expression,
        )

    def _day_matches(self, dt: datetime) -> bool:
        dom_restricted = self.dom != set(range(1, 32))
        dow_restricted = self.dow != set(range(0, 7))
        cron_dow = (dt.weekday() + 1) % 7  # Python 周一=0 -> cron 周一=1，周日=0
        if not dom_restricted and not dow_restricted:
            return True
        if dom_restricted and not dow_restricted:
            return dt.day in self.dom
        if dow_restricted and not dom_restricted:
            return cron_dow in self.dow
        return dt.day in self.dom or cron_dow in self.dow  # Vixie 或规则

    def matches(self, dt: datetime) -> bool:
        return (
            dt.minute in self.minute
            and dt.hour in self.hour
            and dt.month in self.month
            and self._day_matches(dt)
        )

    def next_after(self, after: datetime, inclusive: bool = False) -> datetime:
        """返回 after 之后（不含当前分钟，除非 inclusive）的首次触发时间。"""
        current = after.replace(second=0, microsecond=0)
        if not inclusive:
            current += timedelta(minutes=1)
        deadline = current + timedelta(days=366)
        while current <= deadline:
            if self.matches(current):
                return current
            current += timedelta(minutes=1)
        raise RuntimeError(f"no firing time within a year for {self.raw!r}")

    def next_n(self, after: datetime, n: int = 5, inclusive: bool = False) -> List[datetime]:
        result: List[datetime] = []
        cursor = after
        for _ in range(n):
            fired = self.next_after(cursor, inclusive=inclusive and not result)
            result.append(fired)
            cursor = fired
        return result


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute next firing times for a 5-field cron expression (stdlib only)."
    )
    parser.add_argument("expression", help="cron expression, e.g. '*/15 9-18 * * 1-5'")
    parser.add_argument("-n", "--count", type=int, default=5, help="how many next times")
    parser.add_argument(
        "--from", dest="start", default=None,
        help="start datetime 'YYYY-MM-DD HH:MM' (default: now)",
    )
    args = parser.parse_args(argv)

    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d %H:%M")
    else:
        start = datetime.now().replace(second=0, microsecond=0)

    try:
        expr = CronExpr.parse(args.expression)
        times = expr.next_n(start, n=args.count)
    except ValueError as exc:
        print(f"error: invalid cron expression: {exc}", file=sys.stderr)
        return 2
    print(f"# {expr.raw}   (after {start.strftime('%Y-%m-%d %H:%M')})")
    for t in times:
        print(t.strftime("%Y-%m-%d %H:%M %a"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
