"""btree.py -- 零依赖 B 树（多路平衡查找树）教学实现。

B 树阶数由最小度数 t 决定：
- 每个节点最多 2t-1 个键（根除外）
- 非根节点至少 t-1 个键
- 内部节点的子节点数 = 键数 + 1
支持：查找、插入（节点分裂）、删除（借键/合并）、范围查询、
有序遍历与树结构展示，并附带 CLI。
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional


class Node:
    __slots__ = ("keys", "children", "leaf")

    def __init__(self, leaf: bool = True):
        self.keys: List = []
        self.children: List["Node"] = []
        self.leaf = leaf

    def __repr__(self) -> str:
        return f"Node({self.keys})"


class BTree:
    def __init__(self, t: int = 3):
        if t < 2:
            raise ValueError("最小度数 t 必须 >= 2")
        self.t = t
        self.root = Node(leaf=True)

    # ------------------------------------------------------------------ #
    # 查找
    # ------------------------------------------------------------------ #
    def search(self, key):
        """返回 (是否存在, 节点, 节点内下标)。"""
        return self._search(self.root, key)

    def _search(self, node: Node, key):
        i = 0
        while i < len(node.keys) and key > node.keys[i]:
            i += 1
        if i < len(node.keys) and key == node.keys[i]:
            return True, node, i
        if node.leaf:
            return False, None, -1
        return self._search(node.children[i], key)

    def contains(self, key) -> bool:
        return self.search(key)[0]

    # ------------------------------------------------------------------ #
    # 插入
    # ------------------------------------------------------------------ #
    def insert(self, key) -> None:
        if self.contains(key):
            return  # 键唯一，重复插入忽略
        root = self.root
        if len(root.keys) == 2 * self.t - 1:
            new_root = Node(leaf=False)
            new_root.children.append(root)
            self._split_child(new_root, 0)
            self.root = new_root
        self._insert_nonfull(self.root, key)

    def _split_child(self, parent: Node, i: int) -> None:
        t = self.t
        y = parent.children[i]
        z = Node(leaf=y.leaf)
        # 中间键上移
        parent.keys.insert(i, y.keys[t - 1])
        z.keys = y.keys[t:]
        y.keys = y.keys[: t - 1]
        if not y.leaf:
            z.children = y.children[t:]
            y.children = y.children[:t]
        parent.children.insert(i + 1, z)

    def _insert_nonfull(self, node: Node, key) -> None:
        i = len(node.keys) - 1
        if node.leaf:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            node.keys.insert(i + 1, key)
            return
        while i >= 0 and key < node.keys[i]:
            i -= 1
        i += 1
        if len(node.children[i].keys) == 2 * self.t - 1:
            self._split_child(node, i)
            if key > node.keys[i]:
                i += 1
        self._insert_nonfull(node.children[i], key)

    # ------------------------------------------------------------------ #
    # 有序遍历 / 范围查询
    # ------------------------------------------------------------------ #
    def inorder(self) -> List:
        out: List = []
        self._inorder(self.root, out)
        return out

    def _inorder(self, node: Node, out: List) -> None:
        if node.leaf:
            out.extend(node.keys)
            return
        for i, key in enumerate(node.keys):
            self._inorder(node.children[i], out)
            out.append(key)
        self._inorder(node.children[-1], out)

    def range_query(self, low, high) -> List:
        """返回满足 low <= key <= high 的全部键（有序）。"""
        out: List = []
        self._range(self.root, low, high, out)
        return out

    def _range(self, node: Node, low, high, out: List) -> None:
        if not node.leaf:
            for i, key in enumerate(node.keys):
                if key >= low:
                    self._range(node.children[i], low, high, out)
                if low <= key <= high:
                    out.append(key)
                if key > high:
                    return
            if node.keys[-1] <= high:
                self._range(node.children[-1], low, high, out)
        else:
            out.extend(k for k in node.keys if low <= k <= high)

    # ------------------------------------------------------------------ #
    # 删除（CLRS 三种情形 + 借键/合并）
    # ------------------------------------------------------------------ #
    def delete(self, key) -> bool:
        if not self.contains(key):
            return False
        self._delete(self.root, key)
        if not self.root.keys and not self.root.leaf:
            self.root = self.root.children[0]
        return True

    def _delete(self, node: Node, key) -> None:
        t = self.t
        i = 0
        while i < len(node.keys) and key > node.keys[i]:
            i += 1

        if i < len(node.keys) and key == node.keys[i]:
            if node.leaf:
                node.keys.pop(i)
            else:
                self._delete_internal(node, i)
            return

        if node.leaf:
            return  # 不存在（外层已保证，防御性处理）

        # 保证下降的子节点至少有 t 个键
        at_end = i == len(node.keys)
        if len(node.children[i].keys) < t:
            self._ensure(node, i)
        # 合并后键数与子节点下标可能变化
        if at_end and i > len(node.keys):
            self._delete(node.children[i - 1], key)
        else:
            self._delete(node.children[i], key)

    def _delete_internal(self, node: Node, i: int) -> None:
        t = self.t
        key = node.keys[i]
        left = node.children[i]
        right = node.children[i + 1]
        if len(left.keys) >= t:
            pred = self._predecessor(left)
            node.keys[i] = pred
            self._delete(left, pred)
        elif len(right.keys) >= t:
            succ = self._successor(right)
            node.keys[i] = succ
            self._delete(right, succ)
        else:
            self._merge(node, i)
            self._delete(node.children[i], key)

    def _predecessor(self, node: Node):
        while not node.leaf:
            node = node.children[-1]
        return node.keys[-1]

    def _successor(self, node: Node):
        while not node.leaf:
            node = node.children[0]
        return node.keys[0]

    def _ensure(self, node: Node, i: int) -> None:
        t = self.t
        if i > 0 and len(node.children[i - 1].keys) >= t:
            self._borrow_prev(node, i)
        elif i < len(node.keys) and len(node.children[i + 1].keys) >= t:
            self._borrow_next(node, i)
        else:
            if i == len(node.keys):
                self._merge(node, i - 1)
            else:
                self._merge(node, i)

    def _borrow_prev(self, node: Node, i: int) -> None:
        child = node.children[i]
        sib = node.children[i - 1]
        child.keys.insert(0, node.keys[i - 1])
        node.keys[i - 1] = sib.keys.pop()
        if not sib.leaf:
            child.children.insert(0, sib.children.pop())

    def _borrow_next(self, node: Node, i: int) -> None:
        child = node.children[i]
        sib = node.children[i + 1]
        child.keys.append(node.keys[i])
        node.keys[i] = sib.keys.pop(0)
        if not sib.leaf:
            child.children.append(sib.children.pop(0))

    def _merge(self, node: Node, i: int) -> None:
        left = node.children[i]
        right = node.children[i + 1]
        left.keys.append(node.keys.pop(i))
        left.keys.extend(right.keys)
        if not left.leaf:
            left.children.extend(right.children)
        node.children.pop(i + 1)

    # ------------------------------------------------------------------ #
    # 结构展示
    # ------------------------------------------------------------------ #
    def height(self) -> int:
        h = 1
        node = self.root
        while not node.leaf:
            node = node.children[0]
            h += 1
        return h

    def dump(self) -> str:
        lines: List[str] = []
        self._dump(self.root, 0, lines)
        return "\n".join(lines)

    def _dump(self, node: Node, depth: int, lines: List[str]) -> None:
        indent = "  " * depth
        lines.append(f"{indent}{'L' if node.leaf else 'N'} {node.keys}")
        for child in node.children:
            self._dump(child, depth + 1, lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_build(args) -> int:
    tree = BTree(t=args.degree)
    keys = _read_keys(args.file)
    for k in keys:
        tree.insert(k)
    print(f"loaded {len(tree.inorder())} keys, height={tree.height()}")
    if args.search is not None:
        print(f"contains {args.search}: {tree.contains(args.search)}")
    if args.range:
        low, high = args.range
        print(f"range [{low},{high}]: {tree.range_query(low, high)}")
    if args.dump:
        print(tree.dump())
    return 0


def cmd_demo(args) -> int:
    tree = BTree(t=2)
    for k in [10, 20, 5, 6, 12, 30, 7, 17, 3, 25, 1, 15, 22, 28]:
        tree.insert(k)
    print("after inserts:")
    print(tree.dump())
    print("inorder:", tree.inorder())
    print("range [6,20]:", tree.range_query(6, 20))
    for k in [6, 10, 20, 7, 3]:
        tree.delete(k)
        print(f"deleted {k}: {tree.inorder()}")
    return 0


def _read_keys(file=None) -> List:
    text = open(file, "r", encoding="utf-8").read() if file else sys.stdin.read()
    out = []
    for token in text.replace(",", " ").split():
        if token.strip():
            out.append(int(token))
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="B 树实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pb = sub.add_parser("build", help="批量建键并查询")
    pb.add_argument("file", nargs="?")
    pb.add_argument("--degree", type=int, default=2, help="最小度数 t")
    pb.add_argument("--search", type=int)
    pb.add_argument("--range", type=int, nargs=2, metavar=("LOW", "HIGH"))
    pb.add_argument("--dump", action="store_true")
    pb.set_defaults(func=cmd_build)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
