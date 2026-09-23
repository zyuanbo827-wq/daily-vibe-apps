"""test_ratelimit.py -- ratelimit.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

import ratelimit
from ratelimit import (
    Event, FixedWindowCounter, RateLimitError, SlidingWindowCounter,
    SlidingWindowLog, TokenBucket, make_limiter, parse_events, replay,
    summarize,
)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample_requests.txt"


class TestTokenBucket(unittest.TestCase):
    def test_burst_capacity(self):
        tb = TokenBucket(capacity=5, refill_rate=1.0)
        for _ in range(5):
            self.assertTrue(tb.try_acquire(0.0))
        self.assertFalse(tb.try_acquire(0.0))

    def test_refill_over_time(self):
        tb = TokenBucket(capacity=5, refill_rate=1.0)
        for _ in range(5):
            tb.try_acquire(0.0)
        # 耗尽后 t=1：补 1 个令牌
        self.assertTrue(tb.try_acquire(1.0))
        self.assertFalse(tb.try_acquire(1.0))
        # t=1->3 再补 2 个，恰好两次成功、第三次拒绝
        self.assertTrue(tb.try_acquire(3.0))
        self.assertTrue(tb.try_acquire(3.0))
        self.assertFalse(tb.try_acquire(3.0))

    def test_tokens_capped(self):
        tb = TokenBucket(capacity=5, refill_rate=2.0)
        tb.try_acquire(0.0, 1)
        self.assertTrue(tb.try_acquire(100.0, 5))
        self.assertFalse(tb.try_acquire(100.0))

    def test_multi_token_no_partial_consume(self):
        tb = TokenBucket(capacity=5, refill_rate=0.0)
        self.assertTrue(tb.try_acquire(0.0, 3))
        self.assertFalse(tb.try_acquire(0.0, 3))  # 剩 2，拒绝且不扣
        self.assertTrue(tb.try_acquire(0.0, 2))

    def test_oversized_request_rejected(self):
        tb = TokenBucket(capacity=5, refill_rate=10.0)
        self.assertFalse(tb.try_acquire(0.0, 6))

    def test_invalid_args_and_clock(self):
        with self.assertRaises(RateLimitError):
            TokenBucket(capacity=0, refill_rate=1.0)
        tb = TokenBucket(capacity=5, refill_rate=1.0)
        tb.try_acquire(10.0)
        with self.assertRaises(RateLimitError):
            tb.try_acquire(9.0)
        with self.assertRaises(RateLimitError):
            tb.try_acquire(11.0, tokens=0)


class TestFixedWindow(unittest.TestCase):
    def test_limit_and_reset(self):
        fw = FixedWindowCounter(limit=5, window=10)
        for _ in range(5):
            self.assertTrue(fw.try_acquire(1.0))
        self.assertFalse(fw.try_acquire(9.9))
        self.assertTrue(fw.try_acquire(10.0))  # 新窗口

    def test_multi_window_jump(self):
        fw = FixedWindowCounter(limit=5, window=10)
        fw.try_acquire(0.0, 5)
        self.assertTrue(fw.try_acquire(25.0, 5))
        self.assertEqual(fw.window_start, 20.0)

    def test_multi_token(self):
        fw = FixedWindowCounter(limit=5, window=10)
        self.assertTrue(fw.try_acquire(0.0, 3))
        self.assertFalse(fw.try_acquire(0.0, 3))
        self.assertTrue(fw.try_acquire(0.0, 2))


class TestSlidingLog(unittest.TestCase):
    def test_limit(self):
        log = SlidingWindowLog(limit=5, window=10)
        for i in range(5):
            self.assertTrue(log.try_acquire(float(i)))
        self.assertFalse(log.try_acquire(5.0))

    def test_exact_window_expiry(self):
        log = SlidingWindowLog(limit=5, window=10)
        for i in range(5):
            log.try_acquire(float(i))  # 0..4
        self.assertTrue(log.try_acquire(10.0))  # t=0 恰好过期
        self.assertEqual(len(log.log), 5)

    def test_old_requests_pruned(self):
        log = SlidingWindowLog(limit=2, window=10)
        log.try_acquire(0.0)
        log.try_acquire(0.0)
        self.assertTrue(log.try_acquire(10.1))


class TestSlidingWindowCounter(unittest.TestCase):
    def test_weighted_formula(self):
        sw = SlidingWindowCounter(limit=10, window=10)
        for i in range(10):
            self.assertTrue(sw.try_acquire(float(i)))   # 窗口 0 填满
        self.assertFalse(sw.try_acquire(10.0))          # 估算 10
        # t=15：前窗口权重 0.5 -> 估算 5，可再放 5 个
        for _ in range(5):
            self.assertTrue(sw.try_acquire(15.0))
        self.assertFalse(sw.try_acquire(15.0))          # 估算回到 10

    def test_gap_resets_previous(self):
        sw = SlidingWindowCounter(limit=5, window=10)
        sw.try_acquire(0.0, 5)
        self.assertTrue(sw.try_acquire(25.0, 5))        # 跨 2+ 窗口
        self.assertEqual(sw.prev_count, 0)
        self.assertEqual(sw.window_start, 20.0)


class TestEventsAndReplay(unittest.TestCase):
    def test_parse_variants(self):
        events = parse_events(
            "# comment\n\n1.0\n2.0,3\n  3.5 , 2 \n")
        self.assertEqual(events, [Event(1.0), Event(2.0, 3), Event(3.5, 2)])

    def test_parse_errors(self):
        with self.assertRaises(RateLimitError):
            parse_events("1.0,1,2")
        with self.assertRaises(RateLimitError):
            parse_events("abc")
        with self.assertRaises(RateLimitError):
            parse_events("1.0,0")
        with self.assertRaises(RateLimitError):
            parse_events("2.0\n1.0")

    def test_replay_and_summary(self):
        events = [Event(0.0)] * 6
        results = replay(events, make_limiter("sliding-log", 5, 10))
        self.assertEqual(summarize(results), (5, 1))


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "ratelimit.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in ratelimit.ALGORITHMS:
            self.assertIn(name, proc.stdout)
        self.assertIn("D", proc.stdout)
        # 滑动窗口计数器在跨窗口时最保守
        sw_line = [ln for ln in proc.stdout.splitlines()
                   if ln.startswith("sliding-window")][0]
        self.assertEqual(sw_line.split()[1], "AAAAADADD")

    def test_replay_sample(self):
        proc = self.run_cli("replay", str(SAMPLE),
                            "--algo", "sliding-log", "--limit", "5",
                            "--window", "10")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("放行 8 / 拒绝 2", proc.stdout)

    def test_replay_token_bucket_stdin(self):
        stream = "0.0\n0.0\n0.0\n5.0\n5.0\n"
        proc = self.run_cli("replay", "-", "--algo", "token-bucket",
                            "--limit", "2", "--window", "10", "--rate", "0.5",
                            input_text=stream)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # t0 放 2 拒 1；t5 按 0.5/s 补 2.5（封顶 2）-> 放 2
        self.assertIn("放行 4 / 拒绝 1", proc.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("replay", "no-such.txt")
        self.assertEqual(proc.returncode, 2)

    def test_bad_event_exit_one(self):
        proc = self.run_cli("replay", "-", input_text="oops\n")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
