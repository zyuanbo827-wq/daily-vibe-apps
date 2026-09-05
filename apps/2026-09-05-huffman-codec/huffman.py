"""huffman-codec：零依赖 Huffman 压缩编解码工具（仅 Python 标准库）。

文件格式：
    [4 字节大端 header 长度 N][N 字节 UTF-8 JSON 码表][压缩后的比特主体]
JSON 码表形如 {"pad": 3, "codes": {"a": "01", ...}}，因此解码端无需原始文本，
仅凭文件即可还原。

命令行：
    python huffman.py encode sample.txt -o sample.huf
    python huffman.py decode sample.huf -o restored.txt
    python huffman.py stats  sample.txt
"""
from __future__ import annotations

import argparse
import heapq
import json
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Node:
    freq: int
    order: int
    char: Optional[str] = None
    left: Optional["Node"] = None
    right: Optional["Node"] = None

    def is_leaf(self) -> bool:
        return self.char is not None


def build_frequency(text: str) -> Dict[str, int]:
    """字符 -> 出现次数。"""
    return dict(Counter(text))


def build_tree(freq: Dict[str, int]) -> Optional[Node]:
    """用最小堆构建 Huffman 树；同频时按入队次序打破平局，保证结果确定。"""
    if not freq:
        return None
    heap: List[Tuple[int, int, Node]] = []
    for order, (char, count) in enumerate(sorted(freq.items())):
        heapq.heappush(heap, (count, order, Node(count, order, char)))
    tie = len(freq)
    while len(heap) > 1:
        f1, _, left = heapq.heappop(heap)
        f2, _, right = heapq.heappop(heap)
        merged = Node(f1 + f2, tie, None, left, right)
        heapq.heappush(heap, (merged.freq, tie, merged))
        tie += 1
    return heap[0][2]


def build_codes(root: Optional[Node]) -> Dict[str, str]:
    """由 Huffman 树生成前缀码；单字符场景约定码长为 "0"。"""
    if root is None:
        return {}
    if root.is_leaf():
        return {root.char: "0"}
    codes: Dict[str, str] = {}
    stack: List[Tuple[Node, str]] = [(root, "")]
    while stack:
        node, prefix = stack.pop()
        if node.is_leaf():
            codes[node.char] = prefix
            continue
        stack.append((node.right, prefix + "1"))
        stack.append((node.left, prefix + "0"))
    return codes


def _pack(text: str) -> Tuple[Dict[str, str], int, bytes]:
    root = build_tree(build_frequency(text))
    codes = build_codes(root)
    bits = "".join(codes[ch] for ch in text)
    padding = (8 - len(bits) % 8) % 8
    bits += "0" * padding
    body = bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))
    return codes, padding, body


def encode(text: str) -> bytes:
    """把文本编码为自描述的压缩字节串。"""
    codes, padding, body = _pack(text)
    header = json.dumps(
        {"pad": padding, "codes": codes}, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return struct.pack(">I", len(header)) + header + body


def decode(data: bytes) -> str:
    """从 encode() 产出的字节串还原文本；损坏数据抛 ValueError。"""
    if len(data) < 4:
        raise ValueError("truncated data: missing 4-byte header length")
    header_len = struct.unpack(">I", data[:4])[0]
    if len(data) < 4 + header_len:
        raise ValueError("truncated data: header incomplete")
    meta = json.loads(data[4 : 4 + header_len].decode("utf-8"))
    codes: Dict[str, str] = meta["codes"]
    padding: int = meta["pad"]
    inverse = {code: ch for ch, code in codes.items()}
    bits = "".join(f"{byte:08b}" for byte in data[4 + header_len :])
    if padding:
        bits = bits[:-padding]

    output: List[str] = []
    buffer = ""
    for bit in bits:
        buffer += bit
        ch = inverse.get(buffer)
        if ch is not None:
            output.append(ch)
            buffer = ""
    if buffer:
        raise ValueError("corrupt data: undecodable trailing bits")
    return "".join(output)


def compression_report(text: str) -> str:
    codes, _, body = _pack(text)
    raw = len(text.encode("utf-8"))
    packed = len(encode(text))
    ratio = (packed / raw * 100) if raw else 0.0
    lines = [
        f"symbols        : {len(text)}",
        f"unique chars   : {len(codes)}",
        f"raw utf-8 bytes: {raw}",
        f"packed bytes   : {packed} (codebook + {len(body)} payload bytes)",
        f"size ratio     : {ratio:.1f}%",
        "huffman codes  :",
    ]
    for ch in sorted(codes, key=lambda c: (len(codes[c]), c)):
        shown = ch if ch.isprintable() else repr(ch)
        lines.append(f"  {shown!s:>6} -> {codes[ch]}")
    restored = decode(encode(text))
    lines.append("roundtrip      : OK" if restored == text else "roundtrip      : FAIL")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zero-dependency Huffman file codec (Python stdlib only)."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_enc = sub.add_parser("encode", help="compress a UTF-8 text file")
    p_enc.add_argument("path")
    p_enc.add_argument("-o", "--output", required=True)
    p_dec = sub.add_parser("decode", help="decompress a .huf file")
    p_dec.add_argument("path")
    p_dec.add_argument("-o", "--output", required=True)
    p_stats = sub.add_parser("stats", help="show codes and compression stats")
    p_stats.add_argument("path")
    args = parser.parse_args(argv)

    try:
        if args.command == "encode":
            text = Path(args.path).read_text(encoding="utf-8", newline="")
            payload = encode(text)
            Path(args.output).write_bytes(payload)
            print(f"encoded -> {args.output} ({len(payload)} bytes)")
        elif args.command == "decode":
            text = decode(Path(args.path).read_bytes())
            Path(args.output).write_text(text, encoding="utf-8", newline="")
            print(f"decoded -> {args.output} ({len(text)} chars)")
        else:
            text = Path(args.path).read_text(encoding="utf-8", newline="")
            print(compression_report(text))
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
