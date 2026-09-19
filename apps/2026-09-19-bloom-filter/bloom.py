"""bloom.py -- 零依赖布隆过滤器（Bloom Filter）。

特性：
  * 按预期元素数 n 与误判率 p 自动计算最优位数组大小 m 与哈希函数个数 k
  * 双哈希（double hashing）从两个 64 位 FNV-1a 派生 k 个位置，无需三方库
  * 支持并集 / 交集、误判率估算、二进制序列化与文件存取
  * 附带 build / query / info 三个 CLI 子命令，可对词表建库后批量查询

仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
from typing import Iterable, Iterator, Optional, Union

Item = Union[str, bytes]

MAGIC = b"BLMF"
VERSION = 1
_HEADER = struct.Struct("!4sBIQQ")  # magic, version, k, m, count

_FNV_OFFSET = 0xCBF29CE48497B52D
_FNV_PRIME = 0x100000001B3
_MASK64 = 0xFFFFFFFFFFFFFFFF
_SEED2 = 0x9E3779B97F4A7C15


class BloomError(ValueError):
    """参数或序列化数据错误。"""


def _to_bytes(item: Item) -> bytes:
    if isinstance(item, bytes):
        return item
    if isinstance(item, str):
        return item.encode("utf-8")
    raise BloomError(f"元素必须是 str 或 bytes，实际为 {type(item).__name__}")


def fnv1a_64(data: bytes, seed: int = 0) -> int:
    """带种子的 64 位 FNV-1a 哈希。"""
    h = (_FNV_OFFSET ^ seed) & _MASK64
    for b in data:
        h ^= b
        h = (h * _FNV_PRIME) & _MASK64
    return h


def optimal_bits(expected_items: int, fpp: float) -> int:
    """m = ceil(-n ln p / (ln 2)^2)。"""
    if expected_items <= 0:
        raise BloomError("预期元素数必须为正整数")
    if not 0.0 < fpp < 1.0:
        raise BloomError("误判率 fpp 必须在 (0, 1) 之间")
    m = -expected_items * math.log(fpp) / (math.log(2) ** 2)
    return max(1, math.ceil(m))


def optimal_hashes(m: int, expected_items: int) -> int:
    """k = round(m/n ln 2)，至少 1 个。"""
    k = round(m / expected_items * math.log(2))
    return max(1, k)


class BloomFilter:
    def __init__(self, expected_items: int, fpp: float = 0.01):
        self._m = optimal_bits(expected_items, fpp)
        self._k = optimal_hashes(self._m, expected_items)
        self._fpp_target = fpp
        self._bits = bytearray((self._m + 7) // 8)
        self._count = 0  # add 调用次数（含重复元素）

    # ------------------------------------------------------------------ #
    # 基本属性
    # ------------------------------------------------------------------ #
    @property
    def m(self) -> int:
        return self._m

    @property
    def k(self) -> int:
        return self._k

    @property
    def count(self) -> int:
        """已 add 的元素次数（重复计数）。"""
        return self._count

    def _indices(self, item: Item) -> Iterator[int]:
        data = _to_bytes(item)
        h1 = fnv1a_64(data, 0)
        h2 = fnv1a_64(data, _SEED2) | 1  # 置奇数，改善取模遍历覆盖
        for i in range(self._k):
            yield (h1 + i * h2) % self._m

    def add(self, item: Item) -> None:
        for idx in self._indices(item):
            self._bits[idx >> 3] |= 1 << (idx & 7)
        self._count += 1

    def add_many(self, items: Iterable[Item]) -> None:
        for item in items:
            self.add(item)

    def __contains__(self, item: Item) -> bool:
        bits = self._bits
        return all(bits[idx >> 3] >> (idx & 7) & 1 for idx in self._indices(item))

    def bits_set(self) -> int:
        return sum(bin(b).count("1") for b in self._bits)

    def fill_ratio(self) -> float:
        return self.bits_set() / self._m

    def estimated_fpp(self) -> float:
        """按当前插入次数估算假阳性率：(1 - e^{-kn/m})^k。"""
        if self._count == 0:
            return 0.0
        exponent = -self._k * self._count / self._m
        return (1.0 - math.exp(exponent)) ** self._k

    # ------------------------------------------------------------------ #
    # 集合运算
    # ------------------------------------------------------------------ #
    def _check_compatible(self, other: "BloomFilter") -> None:
        if not isinstance(other, BloomFilter):
            raise BloomError("只能与另一个 BloomFilter 做集合运算")
        if self._m != other._m or self._k != other._k:
            raise BloomError("两个过滤器的 m/k 不一致，无法运算")

    def union(self, other: "BloomFilter") -> "BloomFilter":
        """并集：任一过滤器出现过的元素都判为存在。"""
        self._check_compatible(other)
        result = BloomFilter.__new__(BloomFilter)
        result._m = self._m
        result._k = self._k
        result._fpp_target = self._fpp_target
        result._bits = bytearray(a | b for a, b in zip(self._bits, other._bits))
        result._count = self._count + other._count
        return result

    def intersection(self, other: "BloomFilter") -> "BloomFilter":
        """交集位图：公共位保留（注意：仍可能含假阳性位）。"""
        self._check_compatible(other)
        result = BloomFilter.__new__(BloomFilter)
        result._m = self._m
        result._k = self._k
        result._fpp_target = self._fpp_target
        result._bits = bytearray(a & b for a, b in zip(self._bits, other._bits))
        result._count = min(self._count, other._count)
        return result

    # ------------------------------------------------------------------ #
    # 序列化
    # ------------------------------------------------------------------ #
    def to_bytes(self) -> bytes:
        header = _HEADER.pack(MAGIC, VERSION, self._k, self._m, self._count)
        return header + bytes(self._bits)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "BloomFilter":
        if len(raw) < _HEADER.size:
            raise BloomError("数据过短，不是合法的布隆过滤器文件")
        magic, version, k, m, count = _HEADER.unpack(raw[: _HEADER.size])
        if magic != MAGIC:
            raise BloomError("文件头魔数不匹配")
        if version != VERSION:
            raise BloomError(f"不支持的版本号：{version}")
        bitmap = raw[_HEADER.size:]
        if len(bitmap) != (m + 7) // 8:
            raise BloomError("位图长度与位数 m 不一致")
        if k <= 0 or m <= 0:
            raise BloomError("m/k 非法")
        f = cls.__new__(cls)
        f._m = m
        f._k = k
        f._fpp_target = None
        f._bits = bytearray(bitmap)
        f._count = count
        return f

    def save(self, path: str) -> None:
        with open(path, "wb") as fp:
            fp.write(self.to_bytes())

    @classmethod
    def load(cls, path: str) -> "BloomFilter":
        with open(path, "rb") as fp:
            return cls.from_bytes(fp.read())


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_items(path: str) -> list[str]:
    if path == "-":
        stream = sys.stdin
    else:
        stream = open(path, "r", encoding="utf-8")
    try:
        return [line.strip() for line in stream if line.strip()]
    finally:
        if path != "-":
            stream.close()


def _cmd_build(args: argparse.Namespace) -> int:
    items = _read_items(args.input)
    capacity = args.capacity if args.capacity and args.capacity > 0 else max(len(items), 1)
    bf = BloomFilter(capacity, args.fpp)
    bf.add_many(items)
    bf.save(args.output)
    print(
        f"items={len(items)} capacity={capacity} m={bf.m} bits k={bf.k} "
        f"size={len(bf.to_bytes())}B est_fpp={bf.estimated_fpp():.2e} -> {args.output}"
    )
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    bf = BloomFilter.load(args.file)
    missing = 0
    for item in args.items:
        if item in bf:
            print(f"{item}\t可能存在")
        else:
            print(f"{item}\t一定不存在")
            missing += 1
    return 1 if missing else 0


def _cmd_info(args: argparse.Namespace) -> int:
    bf = BloomFilter.load(args.file)
    print(f"m (位数组)      : {bf.m}")
    print(f"k (哈希个数)    : {bf.k}")
    print(f"add 次数        : {bf.count}")
    print(f"置位位数        : {bf.bits_set()} ({bf.fill_ratio() * 100:.2f}%)")
    print(f"估算误判率      : {bf.estimated_fpp():.6f}")
    print(f"文件位图大小    : {len(bf.to_bytes())} B")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="布隆过滤器：建库 / 查询 / 信息")
    sub = p.add_subparsers(dest="command", required=True)

    pb = sub.add_parser("build", help="从每行一个元素的文本文件建库")
    pb.add_argument("input", help="输入文件，- 表示标准输入")
    pb.add_argument("-o", "--output", required=True, help="输出的 .bloom 文件")
    pb.add_argument("--capacity", type=int, default=0, help="预期元素数，默认取实际行数")
    pb.add_argument("--fpp", type=float, default=0.01, help="目标误判率，默认 0.01")
    pb.set_defaults(func=_cmd_build)

    pq = sub.add_parser("query", help="查询若干元素")
    pq.add_argument("file", help=".bloom 文件")
    pq.add_argument("items", nargs="+", help="待查询元素")
    pq.set_defaults(func=_cmd_query)

    pi = sub.add_parser("info", help="查看过滤器参数与占用率")
    pi.add_argument("file", help=".bloom 文件")
    pi.set_defaults(func=_cmd_info)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (BloomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
