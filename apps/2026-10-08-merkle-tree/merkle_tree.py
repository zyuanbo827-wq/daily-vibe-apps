"""merkle_tree.py -- 零依赖 Merkle 树实验台。

用 SHA-256 从数据块构造 Merkle 树（奇数节点复制最后一个），
支持根哈希、包含证明（audit path，带左右方向）与证明验证，
可对文件按固定块大小做完整性校验。叶子与内部节点使用不同
域前缀，抗第二像混淆。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from typing import List, Sequence, Tuple

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(LEAF_PREFIX + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


class MerkleTree:
    def __init__(self, items: Sequence[bytes]):
        if not items:
            raise ValueError("至少需要一个数据块")
        self.levels: List[List[bytes]] = [[leaf_hash(x) for x in items]]
        self._build()

    def _build(self) -> None:
        layer = self.levels[0]
        while len(layer) > 1:
            if len(layer) % 2 == 1:
                layer = layer + [layer[-1]]      # 奇数：复制最后一个
            parents = [node_hash(layer[i], layer[i + 1])
                       for i in range(0, len(layer), 2)]
            self.levels.append(parents)
            layer = parents

    @property
    def root(self) -> bytes:
        return self.levels[-1][0]

    @property
    def root_hex(self) -> str:
        return self.root.hex()

    @property
    def size(self) -> int:
        return len(self.levels[0])

    def proof(self, index: int) -> List[Tuple[str, str]]:
        """返回从叶子到根的审计路径：(方向, 兄弟哈希hex)。

        方向 'L' 表示兄弟在左、'R' 表示兄弟在右。
        """
        if not 0 <= index < self.size:
            raise IndexError("叶子下标越界")
        path: List[Tuple[str, str]] = []
        idx = index
        for level in self.levels[:-1]:
            layer = level
            if len(layer) % 2 == 1:
                layer = layer + [layer[-1]]
            if idx % 2 == 0:
                sibling = layer[idx + 1]
                path.append(("R", sibling.hex()))
            else:
                sibling = layer[idx - 1]
                path.append(("L", sibling.hex()))
            idx //= 2
        return path


def verify_proof(data: bytes, proof: Sequence[Tuple[str, str]],
                 root_hex: str) -> bool:
    digest = leaf_hash(data)
    for direction, sibling_hex in proof:
        sibling = bytes.fromhex(sibling_hex)
        digest = node_hash(sibling, digest) if direction == "L" \
            else node_hash(digest, sibling)
    return digest.hex() == root_hex


# --------------------------------------------------------------------------- #
# 文件分块
# --------------------------------------------------------------------------- #
def file_blocks(path: str, block_size: int) -> List[bytes]:
    if block_size <= 0:
        raise ValueError("块大小必须为正数")
    blocks: List[bytes] = []
    with open(path, "rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            blocks.append(chunk)
    if not blocks:                       # 空文件：一个空块
        blocks = [b""]
    return blocks


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
DEMO_TX = [
    b"Alice->Bob: 10",
    b"Bob->Carol: 5",
    b"Carol->Dave: 2",
    b"Dave->Alice: 1",
    b"Eve->Alice: 7",
]


def cmd_root(args) -> int:
    tree = MerkleTree(file_blocks(args.file, args.block))
    print(tree.root_hex)
    return 0


def cmd_verify(args) -> int:
    tree = MerkleTree(file_blocks(args.file, args.block))
    ok = tree.root_hex == args.expected
    print("OK" if ok else "MISMATCH")
    return 0 if ok else 1


def cmd_demo(args) -> int:
    tree = MerkleTree(DEMO_TX)
    print(f"{len(DEMO_TX)} transactions, tree depth {len(tree.levels)}")
    print("root:", tree.root_hex)

    for i, tx in enumerate(DEMO_TX):
        proof = tree.proof(i)
        assert verify_proof(tx, proof, tree.root_hex)
    print(f"inclusion proofs verified for all {len(DEMO_TX)} leaves "
          f"(proof length {len(tree.proof(0))})")

    tampered = b"Alice->Bob: 999"
    bad = verify_proof(tampered, tree.proof(0), tree.root_hex)
    print("tampered tx accepted?", "YES (BAD)" if bad else "NO (detected)")

    other = b"NotInTree: 0"
    print("foreign leaf accepted?",
          "YES (BAD)" if verify_proof(other, tree.proof(1),
                                      tree.root_hex) else "NO (detected)")

    odd = MerkleTree([b"a", b"b", b"c"])
    print("odd-size tree root:", odd.root_hex,
          "| single leaf:", MerkleTree([b"only"]).root_hex)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Merkle 树实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("root", help="计算文件的 Merkle 根")
    pr.add_argument("file")
    pr.add_argument("--block", type=int, default=1024)
    pr.set_defaults(func=cmd_root)

    pv = sub.add_parser("verify", help="用期望根校验文件")
    pv.add_argument("file")
    pv.add_argument("expected")
    pv.add_argument("--block", type=int, default=1024)
    pv.set_defaults(func=cmd_verify)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, IndexError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
