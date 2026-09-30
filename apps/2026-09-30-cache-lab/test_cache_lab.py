"""test_cache_lab.py -- cache_lab.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

from cache_lab import (
    BaseCache, CacheError, Command, LFUCache, LRUCache, parse_commands,
    replay, zipf_workload,
)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample_workload.txt"


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, d):
        self.t += d


class TestLRU(unittest.TestCase):
    def test_miss_default_and_stats(self):
        c = LRUCache(2)
        self.assertIsNone(c.get("x"))
        self.assertEqual(c.get("x", "d"), "d")
        self.assertEqual(c.stats()["misses"], 2)

    def test_set_get_update(self):
        c = LRUCache(2)
        c.set("a", 1)
        self.assertEqual(c.get("a"), 1)
        c.set("a", 2)
        self.assertEqual(c.get("a"), 2)
        self.assertEqual(len(c), 1)

    def test_eviction_order(self):
        c = LRUCache(2)
        c.set(1, "v1")
        c.set(2, "v2")
        c.get(1)              # 提升 1，2 成为最久未用
        c.set(3, "v3")
        self.assertIsNone(c.get(2))
        self.assertEqual(c.get(1), "v1")
        self.assertEqual(c.get(3), "v3")
        self.assertEqual(c.evictions, 1)

    def test_update_existing_resets_recency(self):
        c = LRUCache(2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 3)         # a 提升
        c.set("c", 4)         # 淘汰 b
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("a"), 3)

    def test_delete_and_clear(self):
        c = LRUCache(2)
        c.set("a", 1)
        self.assertTrue(c.delete("a"))
        self.assertFalse(c.delete("a"))
        c.set("b", 2)
        c.clear()
        self.assertEqual(len(c), 0)
        self.assertEqual(c.stats()["hits"], 0)


class TestLFU(unittest.TestCase):
    def test_evicts_least_frequent(self):
        c = LFUCache(2)
        c.set(1, "a")
        c.set(2, "b")
        c.get(1)              # 1 频率升到 2
        c.set(3, "c")         # 淘汰频率 1 的 2
        self.assertIsNone(c.get(2))
        self.assertEqual(c.get(1), "a")
        self.assertEqual(c.get(3), "c")

    def test_tie_evicts_lru_in_freq_bucket(self):
        c = LFUCache(3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)         # 同频率，淘汰最久未用的 a
        self.assertIsNone(c.get("a"))
        for k in ("b", "c", "d"):
            self.assertIsNotNone(c.get(k))

    def test_set_existing_increments_freq(self):
        c = LFUCache(2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 3)         # a 频率 2
        c.set("c", 5)         # 淘汰频率 1 的 b
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("a"), 3)

    def test_min_freq_advances(self):
        c = LFUCache(2)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")
        c.get("b")            # 全部进入频率 2，桶 1 消失
        self.assertEqual(c.min_freq, 2)
        c.set("c", 3)         # 淘汰后新键 min_freq 回到 1
        self.assertEqual(c.min_freq, 1)


class TestTTL(unittest.TestCase):
    def test_expiry_lru(self):
        clk = FakeClock()
        c = LRUCache(2, time_func=clk)
        c.set("k", "v", ttl=5)
        clk.advance(4)
        self.assertEqual(c.get("k"), "v")
        clk.advance(2)
        self.assertIsNone(c.get("k"))
        self.assertEqual(len(c), 0)
        self.assertEqual(c.evictions, 0)        # 过期不算容量淘汰

    def test_expired_frees_capacity(self):
        clk = FakeClock()
        c = LRUCache(1, time_func=clk)
        c.set("k", "v", ttl=1)
        clk.advance(2)
        self.assertIsNone(c.get("k"))
        c.set("n", "w")                          # 无需淘汰即可放入
        self.assertEqual(c.evictions, 0)

    def test_expiry_lfu(self):
        clk = FakeClock()
        c = LFUCache(2, time_func=clk)
        c.set("k", "v", ttl=10)
        clk.advance(11)
        self.assertIsNone(c.get("k"))

    def test_bad_ttl(self):
        c = LRUCache(2)
        with self.assertRaises(CacheError):
            c.set("k", "v", ttl=0)


class TestConstructionErrors(unittest.TestCase):
    def test_capacity(self):
        for cls in (LRUCache, LFUCache):
            with self.assertRaises(CacheError):
                cls(0)

    def test_inheritance(self):
        self.assertIsInstance(LRUCache(2), BaseCache)


class TestCommandsAndReplay(unittest.TestCase):
    def test_parse_full(self):
        text = "# c\nset a 1 ttl=5\nget a\ndelete a\n"
        cmds = parse_commands(text)
        self.assertEqual(cmds, [Command("set", "a", "1", 5.0),
                                Command("get", "a"),
                                Command("delete", "a")])

    def test_parse_errors(self):
        for bad in ["set a", "get", "frob x", "set a 1 bad=2"]:
            with self.assertRaises(CacheError, msg=bad):
                parse_commands(bad)

    def test_replay_sample(self):
        cmds = parse_commands(SAMPLE.read_text(encoding="utf-8"))
        for algo in ("lru", "lfu"):
            cache = replay(cmds, algo, 3)
            s = cache.stats()
            self.assertEqual(s["hits"] + s["misses"], 7)

    def test_unknown_algo(self):
        with self.assertRaises(CacheError):
            replay([], "arc", 3)


class TestZipfWorkload(unittest.TestCase):
    def test_shape(self):
        cmds = zipf_workload(1000, key_space=50, seed=1)
        self.assertEqual(len(cmds), 1000)
        for c in cmds:
            self.assertIn(c.key, {f"k{i}" for i in range(50)})

    def test_deterministic(self):
        a = zipf_workload(500, key_space=50, seed=7)
        b = zipf_workload(500, key_space=50, seed=7)
        self.assertEqual([(c.op, c.key) for c in a],
                         [(c.op, c.key) for c in b])


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "cache_lab.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_demo(self):
        proc = self.run_cli("demo", "--requests", "3000", "--capacity", "50")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("lru", proc.stdout)
        self.assertIn("命中率", proc.stdout)

    def test_replay_file(self):
        proc = self.run_cli("replay", str(SAMPLE), "--capacity", "3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(proc.stdout.splitlines()), 2)

    def test_replay_stdin(self):
        proc = self.run_cli("replay", "-", "--capacity", "2",
                            input_text="set a 1\nget a\nget b\n")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("命中率", proc.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("replay", "no-such.txt")
        self.assertEqual(proc.returncode, 2)

    def test_bad_capacity_exit_one(self):
        proc = self.run_cli("replay", str(SAMPLE), "--capacity", "0")
        self.assertEqual(proc.returncode, 1)

    def test_bad_command_exit_one(self):
        proc = self.run_cli("replay", "-", input_text="oops\n")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
