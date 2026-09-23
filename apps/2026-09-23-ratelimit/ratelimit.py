"""ratelimit.py -- 零依赖限流算法实验台。

一次实现四种常见限流算法，统一 try_acquire(now, tokens=1) 接口，
时钟由外部传入（便于确定性测试）：

  1. TokenBucket          令牌桶：恒定速率补充，支持突发与多令牌消费
  2. FixedWindowCounter   固定窗口计数：窗口对齐、计数重置
  3. SlidingWindowLog     滑动窗口日志：保留窗口内时间戳，精确但占内存
  4. SlidingWindowCounter 滑动窗口计数：前后窗口加权估算，平滑且省内存

附带 demo / replay 两个 CLI 子命令，可回放带时间戳的请求流并统计
放行 / 拒绝数量。
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple


class RateLimitError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# 1. 令牌桶
# --------------------------------------------------------------------------- #
@dataclass
class TokenBucket:
    capacity: float
    refill_rate: float          # 每秒补充的令牌数
    tokens: float = field(init=False)
    last: Optional[float] = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.refill_rate < 0:
            raise RateLimitError("capacity 必须为正，refill_rate 不能为负")
        self.tokens = float(self.capacity)

    def try_acquire(self, now: float, tokens: int = 1) -> bool:
        if tokens <= 0:
            raise RateLimitError("请求令牌数必须为正")
        if tokens > self.capacity:
            return False  # 永远无法满足的请求直接拒绝
        if self.last is not None:
            if now < self.last:
                raise RateLimitError("时间戳不能倒退")
            self.tokens = min(
                self.capacity, self.tokens + (now - self.last) * self.refill_rate)
        self.last = now
        if self.tokens + 1e-9 >= tokens:
            self.tokens -= tokens
            return True
        return False


# --------------------------------------------------------------------------- #
# 2. 固定窗口计数器
# --------------------------------------------------------------------------- #
@dataclass
class FixedWindowCounter:
    limit: int
    window: float
    window_start: float = field(default=0.0, init=False)
    count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.limit <= 0 or self.window <= 0:
            raise RateLimitError("limit 与 window 必须为正")

    def try_acquire(self, now: float, tokens: int = 1) -> bool:
        if tokens <= 0:
            raise RateLimitError("请求令牌数必须为正")
        if now < self.window_start:
            raise RateLimitError("时间戳不能倒退")
        if now >= self.window_start + self.window:
            # 跨过若干个窗口，对齐到 now 所属窗口起点
            elapsed = now - self.window_start
            self.window_start += int(elapsed // self.window) * self.window
            self.count = 0
        if self.count + tokens <= self.limit:
            self.count += tokens
            return True
        return False


# --------------------------------------------------------------------------- #
# 3. 滑动窗口日志
# --------------------------------------------------------------------------- #
@dataclass
class SlidingWindowLog:
    limit: int
    window: float
    log: deque = field(default_factory=deque, init=False)

    def __post_init__(self) -> None:
        if self.limit <= 0 or self.window <= 0:
            raise RateLimitError("limit 与 window 必须为正")

    def try_acquire(self, now: float, tokens: int = 1) -> bool:
        if tokens <= 0:
            raise RateLimitError("请求令牌数必须为正")
        boundary = now - self.window
        while self.log and self.log[0] <= boundary:
            self.log.popleft()
        if len(self.log) + tokens <= self.limit:
            for _ in range(tokens):
                self.log.append(now)
            return True
        return False


# --------------------------------------------------------------------------- #
# 4. 滑动窗口计数器（前后窗口加权）
# --------------------------------------------------------------------------- #
@dataclass
class SlidingWindowCounter:
    limit: int
    window: float
    prev_count: int = field(default=0, init=False)
    current_count: int = field(default=0, init=False)
    window_start: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if self.limit <= 0 or self.window <= 0:
            raise RateLimitError("limit 与 window 必须为正")

    def _advance(self, now: float) -> None:
        if now < self.window_start:
            raise RateLimitError("时间戳不能倒退")
        if now >= self.window_start + self.window:
            gap = int((now - self.window_start) // self.window)
            if gap == 1:
                self.prev_count = self.current_count
            else:
                self.prev_count = 0  # 跨过两个及以上窗口，旧计数无意义
            self.window_start += gap * self.window
            self.current_count = 0

    def estimated_count(self, now: float) -> float:
        self._advance(now)
        weight = (self.window - (now - self.window_start)) / self.window
        return self.prev_count * weight + self.current_count

    def try_acquire(self, now: float, tokens: int = 1) -> bool:
        if tokens <= 0:
            raise RateLimitError("请求令牌数必须为正")
        if self.estimated_count(now) + tokens <= self.limit:
            self.current_count += tokens
            return True
        return False


ALGORITHMS = {
    "token-bucket": TokenBucket,
    "fixed-window": FixedWindowCounter,
    "sliding-log": SlidingWindowLog,
    "sliding-window": SlidingWindowCounter,
}


# --------------------------------------------------------------------------- #
# 请求流回放
# --------------------------------------------------------------------------- #
@dataclass
class Event:
    ts: float
    tokens: int = 1


def parse_events(text: str) -> List[Event]:
    """解析请求流：每行 'timestamp' 或 'timestamp,tokens'；
    # 开头与空行忽略。"""
    events: List[Event] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) > 2:
            raise RateLimitError(f"第 {lineno} 行格式错误：{raw!r}")
        try:
            ts = float(parts[0])
            tokens = int(parts[1]) if len(parts) == 2 else 1
        except ValueError:
            raise RateLimitError(f"第 {lineno} 行数字无法解析：{raw!r}")
        if tokens <= 0:
            raise RateLimitError(f"第 {lineno} 行令牌数必须为正")
        if events and ts < events[-1].ts:
            raise RateLimitError(f"第 {lineno} 行时间戳早于前一事件")
        events.append(Event(ts, tokens))
    return events


def make_limiter(name: str, limit: int, window: float,
                 rate: Optional[float] = None):
    cls = ALGORITHMS[name]
    if name == "token-bucket":
        return cls(capacity=limit, refill_rate=limit / window if rate is None
                   else rate)
    return cls(limit=limit, window=window)


def replay(events: List[Event], limiter) -> List[Tuple[Event, bool]]:
    return [(ev, limiter.try_acquire(ev.ts, ev.tokens)) for ev in events]


def summarize(results: List[Tuple[Event, bool]]) -> Tuple[int, int]:
    allowed = sum(1 for _, ok in results if ok)
    return allowed, len(results) - allowed


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()


def _print_results(results: List[Tuple[Event, bool]]) -> None:
    for ev, ok in results:
        verdict = "ALLOW" if ok else "DENY "
        extra = f" tokens={ev.tokens}" if ev.tokens != 1 else ""
        print(f"t={ev.ts:<8} {verdict}{extra}")
    allowed, denied = summarize(results)
    total = allowed + denied
    pct = (denied / total * 100) if total else 0.0
    print(f"\n汇总：放行 {allowed} / 拒绝 {denied} / 共 {total}，"
          f"拒绝率 {pct:.1f}%")


def _cmd_replay(args: argparse.Namespace) -> int:
    try:
        events = parse_events(_read_input(args.input))
        limiter = make_limiter(args.algo, args.limit, args.window, args.rate)
        results = replay(events, limiter)
    except (RateLimitError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, OSError) else 1
    _print_results(results)
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    # 场景：容量/限额 5，窗口 10s（令牌桶 0.5/s）；
    # 0s 突发 6 个请求 -> 第 6 个拒绝；12s 再来 3 个，观察各算法差异。
    events = [Event(0.0)] * 6 + [Event(12.0)] * 3
    for name in ALGORITHMS:
        limiter = make_limiter(name, limit=5, window=10.0, rate=0.5)
        results = replay(events, limiter)
        allowed, denied = summarize(results)
        timeline = "".join("A" if ok else "D" for _, ok in results)
        print(f"{name:<16} {timeline}  放行 {allowed} / 拒绝 {denied}")
    print("\n说明：前 6 个请求发生在 t=0（突发），后 3 个在 t=12。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="限流算法实验台（四种算法 + 回放）")
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("replay", help="回放请求流文件（- 表示标准输入）")
    pr.add_argument("input")
    pr.add_argument("--algo", choices=ALGORITHMS, default="sliding-log")
    pr.add_argument("--limit", type=int, default=5, help="容量 / 限额")
    pr.add_argument("--window", type=float, default=10.0, help="窗口秒数")
    pr.add_argument("--rate", type=float, default=None,
                    help="令牌桶每秒补充速率（默认 limit/window）")
    pr.set_defaults(func=_cmd_replay)

    pd = sub.add_parser("demo", help="内置突发场景对比四种算法")
    pd.set_defaults(func=_cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
