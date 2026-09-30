"""cache_lab.py -- 零依赖缓存算法实验台：LRU / LFU / TTL。

手写双向链表实现：
  LRUCache  -- 最近最少使用，O(1) get/set，访问即提升
  LFUCache  -- 最不经常使用，频率分桶 + minFreq，O(1) get/set
两者都支持容量淘汰、TTL 过期（惰性，时钟可注入）、命中统计；
附带工作流回放（比较两种算法命中率）与确定性 Zipf 负载 demo。
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


class CacheError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# 双向链表（带头尾哨兵）
# --------------------------------------------------------------------------- #
class Node:
    __slots__ = ("key", "value", "prev", "next", "freq", "expire")

    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev: Optional[Node] = None
        self.next: Optional[Node] = None
        self.freq = 1
        self.expire: Optional[float] = None


class DoublyLinkedList:
    def __init__(self):
        self.head = Node()
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head
        self.size = 0

    def push_front(self, node: Node) -> None:
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
        self.size += 1

    def remove(self, node: Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev
        self.size -= 1

    def pop_back(self) -> Node:
        if self.size == 0:
            raise CacheError("链表为空")
        node = self.tail.prev
        self.remove(node)
        return node

    def front(self) -> Node:
        return self.head.next


# --------------------------------------------------------------------------- #
# 公共基类
# --------------------------------------------------------------------------- #
class BaseCache:
    def __init__(self, capacity: int, time_func: Callable[[], float] = time.time):
        if capacity < 1:
            raise CacheError("容量 capacity 必须 >= 1")
        self.capacity = capacity
        self._now = time_func
        self.map: Dict[object, Node] = {}
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def __len__(self):
        return len(self.map)

    def _expired(self, node: Node) -> bool:
        return node.expire is not None and self._now() >= node.expire

    def _purge_if_expired(self, key) -> bool:
        node = self.map.get(key)
        if node is not None and self._expired(node):
            self._delete_node(node)
            self.misses += 1
            return True
        return False

    def _delete_node(self, node: Node) -> None:  # 由子类实现
        raise NotImplementedError

    def get(self, key, default=None):
        raise NotImplementedError

    def set(self, key, value, ttl: Optional[float] = None) -> None:
        raise NotImplementedError

    def delete(self, key) -> bool:
        node = self.map.pop(key, None)
        if node is None:
            return False
        self._detach(node)
        return True

    def _detach(self, node: Node) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        self.map.clear()
        self.hits = self.misses = self.evictions = 0

    def stats(self) -> Dict[str, float]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": len(self.map),
            "hit_ratio": (self.hits / total) if total else 0.0,
        }


# --------------------------------------------------------------------------- #
# LRU
# --------------------------------------------------------------------------- #
class LRUCache(BaseCache):
    def __init__(self, capacity: int, time_func=time.time):
        super().__init__(capacity, time_func)
        self.list = DoublyLinkedList()

    def _detach(self, node: Node) -> None:
        self.list.remove(node)

    def _delete_node(self, node: Node) -> None:
        self.list.remove(node)
        self.map.pop(node.key, None)

    def get(self, key, default=None):
        if self._purge_if_expired(key):
            return default
        node = self.map.get(key)
        if node is None:
            self.misses += 1
            return default
        self.list.remove(node)
        self.list.push_front(node)
        self.hits += 1
        return node.value

    def set(self, key, value, ttl: Optional[float] = None) -> None:
        if ttl is not None and ttl <= 0:
            raise CacheError("ttl 必须为正数")
        node = self.map.get(key)
        expire = self._now() + ttl if ttl is not None else None
        if node is not None:
            if self._expired(node):
                self._delete_node(node)
            else:
                node.value = value
                node.expire = expire
                self.list.remove(node)
                self.list.push_front(node)
                return
        if len(self.map) >= self.capacity:
            old = self.list.pop_back()
            self.map.pop(old.key, None)
            self.evictions += 1
        node = Node(key, value)
        node.expire = expire
        self.map[key] = node
        self.list.push_front(node)

    def clear(self) -> None:
        super().clear()
        self.list = DoublyLinkedList()


# --------------------------------------------------------------------------- #
# LFU（频率分桶，同频内按 LRU 排列）
# --------------------------------------------------------------------------- #
class LFUCache(BaseCache):
    def __init__(self, capacity: int, time_func=time.time):
        super().__init__(capacity, time_func)
        self.freq_lists: Dict[int, DoublyLinkedList] = {}
        self.min_freq = 0

    def _detach(self, node: Node) -> None:
        lst = self.freq_lists[node.freq]
        lst.remove(node)
        if lst.size == 0:
            del self.freq_lists[node.freq]
            if self.min_freq == node.freq:
                self.min_freq = min(self.freq_lists, default=0)

    def _delete_node(self, node: Node) -> None:
        self._detach(node)
        self.map.pop(node.key, None)

    def _add_freq(self, node: Node, freq: int) -> None:
        node.freq = freq
        self.freq_lists.setdefault(freq, DoublyLinkedList()).push_front(node)

    def get(self, key, default=None):
        if self._purge_if_expired(key):
            return default
        node = self.map.get(key)
        if node is None:
            self.misses += 1
            return default
        old_freq = node.freq
        self._detach(node)
        self._add_freq(node, old_freq + 1)
        if not self.freq_lists or self.min_freq == 0:
            self.min_freq = node.freq
        self.hits += 1
        return node.value

    def set(self, key, value, ttl: Optional[float] = None) -> None:
        if ttl is not None and ttl <= 0:
            raise CacheError("ttl 必须为正数")
        node = self.map.get(key)
        expire = self._now() + ttl if ttl is not None else None
        if node is not None:
            if self._expired(node):
                self._delete_node(node)
            else:
                node.value = value
                node.expire = expire
                old_freq = node.freq
                self._detach(node)
                self._add_freq(node, old_freq + 1)
                return
        if len(self.map) >= self.capacity:
            lst = self.freq_lists[self.min_freq]
            old = lst.pop_back()
            if lst.size == 0:
                del self.freq_lists[self.min_freq]
            self.map.pop(old.key, None)
            self.evictions += 1
        node = Node(key, value)
        node.expire = expire
        self.map[key] = node
        self._add_freq(node, 1)
        self.min_freq = 1

    def clear(self) -> None:
        super().clear()
        self.freq_lists = {}
        self.min_freq = 0


# --------------------------------------------------------------------------- #
# 工作流回放
# --------------------------------------------------------------------------- #
@dataclass
class Command:
    op: str
    key: str = ""
    value: str = ""
    ttl: Optional[float] = None


def parse_commands(text: str) -> List[Command]:
    commands: List[Command] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        op = parts[0].lower()
        if op == "set":
            if len(parts) < 3:
                raise CacheError(f"第 {lineno} 行：set 需要 key value [ttl=N]")
            ttl = None
            extra = parts[3:]
            for token in extra:
                if token.startswith("ttl="):
                    ttl = float(token[4:])
                else:
                    raise CacheError(f"第 {lineno} 行：无法识别 {token}")
            commands.append(Command("set", parts[1], parts[2], ttl))
        elif op == "get":
            if len(parts) != 2:
                raise CacheError(f"第 {lineno} 行：get 需要一个 key")
            commands.append(Command("get", parts[1]))
        elif op == "delete":
            commands.append(Command("delete", parts[1]))
        else:
            raise CacheError(f"第 {lineno} 行：未知操作 {op}")
    return commands


def make_cache(algo: str, capacity: int, time_func=time.time) -> BaseCache:
    if algo == "lru":
        return LRUCache(capacity, time_func)
    if algo == "lfu":
        return LFUCache(capacity, time_func)
    raise CacheError(f"未知算法：{algo}")


def replay(commands: List[Command], algo: str, capacity: int,
           time_func=time.time) -> BaseCache:
    cache = make_cache(algo, capacity, time_func)
    for cmd in commands:
        if cmd.op == "set":
            cache.set(cmd.key, cmd.value, ttl=cmd.ttl)
        elif cmd.op == "get":
            cache.get(cmd.key)
        elif cmd.op == "delete":
            cache.delete(cmd.key)
    return cache


# --------------------------------------------------------------------------- #
# Zipf 负载生成
# --------------------------------------------------------------------------- #
def zipf_workload(n: int, key_space: int, skew: float = 1.0,
                  seed: int = 42, get_ratio: float = 0.8) -> List[Command]:
    rng = random.Random(seed)
    weights = [1.0 / ((i + 1) ** skew) for i in range(key_space)]
    total = sum(weights)
    commands = []
    for _ in range(n):
        r = rng.random() * total
        acc = 0.0
        key = 0
        for i, w in enumerate(weights):
            acc += w
            if acc >= r:
                key = i
                break
        if rng.random() < get_ratio:
            commands.append(Command("get", f"k{key}"))
        else:
            commands.append(Command("set", f"k{key}", "v"))
    return commands


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()


def _print_stats(name: str, cache: BaseCache) -> None:
    s = cache.stats()
    print(f"{name:<6} 命中 {s['hits']:>5} / 未命中 {s['misses']:>5} / "
          f"淘汰 {s['evictions']:>5} / 命中率 {s['hit_ratio'] * 100:.2f}%")


def _cmd_demo(args: argparse.Namespace) -> int:
    commands = zipf_workload(args.requests, key_space=args.key_space,
                             skew=args.skew, seed=args.seed)
    gets = sum(1 for c in commands if c.op == "get")
    print(f"Zipf 负载：{args.requests} 个请求（get {gets} / "
          f"set {args.requests - gets}），键空间 {args.key_space}，"
          f"缓存容量 {args.capacity}")
    for algo in ("lru", "lfu"):
        cache = replay(commands, algo, args.capacity)
        _print_stats(algo, cache)
    print("\n说明：Zipf 偏斜越高，少量热键越集中，两种算法命中率差异越小；")
    print("在频率分布变化的负载下 LFU 可能保留旧热键，LRU 对近期热点更敏感。")
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    try:
        text = _read_text(args.commands_file)
        commands = parse_commands(text)
    except (CacheError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, OSError) else 1
    for algo in ("lru", "lfu"):
        cache = replay(commands, algo, args.capacity)
        _print_stats(algo, cache)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LRU / LFU 缓存算法实验台")
    sub = p.add_subparsers(dest="command", required=True)

    pd = sub.add_parser("demo", help="Zipf 负载下对比 LRU/LFU 命中率")
    pd.add_argument("--requests", type=int, default=10000)
    pd.add_argument("--key-space", type=int, default=200)
    pd.add_argument("--capacity", type=int, default=50)
    pd.add_argument("--skew", type=float, default=1.0)
    pd.add_argument("--seed", type=int, default=42)
    pd.set_defaults(func=_cmd_demo)

    pr = sub.add_parser("replay", help="回放命令文件（set/get/delete）")
    pr.add_argument("commands_file", help="- 表示标准输入")
    pr.add_argument("--capacity", type=int, default=10)
    pr.set_defaults(func=_cmd_replay)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
