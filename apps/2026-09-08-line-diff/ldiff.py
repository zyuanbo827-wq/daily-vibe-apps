"""line-diff：零依赖的行级 diff / patch 工具（仅 Python 标准库）。

- 用最长公共子序列（LCS）对齐两个文本的行序列；
- 生成接近 git 的 unified diff（带上下文与 @@ 块头）；
- 支持把补丁应用回原文本，以及反向应用（回滚）。

命令行：
    python ldiff.py diff old.txt new.txt --context 3
    python ldiff.py apply old.txt change.patch
    python ldiff.py reverse new.txt change.patch
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

# 每个操作：(标签, 旧文件行号或 None, 新文件行号或 None, 行内容)
Op = Tuple[str, Optional[int], Optional[int], str]


def split_lines(text: str) -> List[str]:
    """按行切分，忽略末尾换行差异（行内不再保留换行符）。"""
    if text == "":
        return []
    return text.splitlines()


def lcs_length_table(a: List[str], b: List[str]) -> List[List[int]]:
    """标准动态规划表，dp[i][j] = a[:i] 与 b[:j] 的 LCS 长度。"""
    la, lb = len(a), len(b)
    dp = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la - 1, -1, -1):
        for j in range(lb - 1, -1, -1):
            if a[i] == b[j]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    return dp


def lcs_sequence(a: List[str], b: List[str]) -> List[str]:
    """返回一条 LCS 行序列（相同元素取其中一条对齐）。"""
    dp = lcs_length_table(a, b)
    i = j = 0
    result: List[str] = []
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            result.append(a[i])
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return result


def diff_ops(old: List[str], new: List[str]) -> List[Op]:
    """由 LCS 表回溯出 equal/delete/insert 操作序列，并带两侧行号（0 基）。"""
    dp = lcs_length_table(old, new)
    ops: List[Op] = []
    i = j = 0
    while i < len(old) and j < len(new):
        if old[i] == new[j]:
            ops.append(("equal", i, j, old[i]))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            ops.append(("delete", i, None, old[i]))
            i += 1
        else:
            ops.append(("insert", None, j, new[j]))
            j += 1
    while i < len(old):
        ops.append(("delete", i, None, old[i]))
        i += 1
    while j < len(new):
        ops.append(("insert", None, j, new[j]))
        j += 1
    return ops


def _hunk_header(ops_slice: List[Op]) -> str:
    old_n = sum(1 for op in ops_slice if op[0] in ("equal", "delete"))
    new_n = sum(1 for op in ops_slice if op[0] in ("equal", "insert"))
    first = ops_slice[0]
    old_start = (first[1] if first[1] is not None else _nearby_index(ops_slice, "old")) + 1
    new_start = (first[2] if first[2] is not None else _nearby_index(ops_slice, "new")) + 1
    return f"@@ -{_range_text(old_start, old_n)} +{_range_text(new_start, new_n)} @@"


def _nearby_index(ops_slice: List[Op], side: str) -> int:
    """块首是纯插入/删除时，取该侧"当前位置"行号（0 基）。"""
    idx = 1 if side == "old" else 2
    for op in ops_slice:
        if op[idx] is not None:
            return op[idx] - (1 if op[0] == "equal" else 0)
    return 0


def _range_text(start: int, count: int) -> str:
    if count == 0:
        return f"{start},0"
    if count == 1:
        return str(start)
    return f"{start},{count}"


def unified_diff(old_text: str, new_text: str, context: int = 3,
                 old_name: str = "a", new_name: str = "b") -> str:
    old, new = split_lines(old_text), split_lines(new_text)
    ops = diff_ops(old, new)
    if all(op[0] == "equal" for op in ops):
        return ""

    n = len(ops)
    keep = [False] * n
    for i, op in enumerate(ops):
        if op[0] != "equal":
            for k in range(max(0, i - context), min(n, i + context + 1)):
                keep[k] = True

    lines = [f"--- {old_name}", f"+++ {new_name}"]
    i = 0
    while i < n:
        if not keep[i]:
            i += 1
            continue
        j = i
        while j < n and keep[j]:
            j += 1
        chunk = ops[i:j]
        lines.append(_hunk_header(chunk))
        for tag, _, _, text in chunk:
            prefix = {"equal": " ", "delete": "-", "insert": "+"}[tag]
            lines.append(prefix + text)
        i = j
    return "\n".join(lines) + "\n"


@dataclass
class PatchLine:
    kind: str  # context / delete / insert
    text: str


def parse_patch(patch_text: str) -> List[PatchLine]:
    result: List[PatchLine] = []
    for line in patch_text.splitlines():
        if line.startswith(("--- ", "+++ ", "@@")):
            continue
        if line.startswith(" "):
            result.append(PatchLine("context", line[1:]))
        elif line.startswith("-"):
            result.append(PatchLine("delete", line[1:]))
        elif line.startswith("+"):
            result.append(PatchLine("insert", line[1:]))
    return result


def apply_patch(original_text: str, patch_text: str, reverse: bool = False) -> str:
    """把 unified diff 应用到原文；reverse=True 时把新文本回滚为旧文本。"""
    original = split_lines(original_text)
    entries = parse_patch(patch_text)
    if reverse:
        mapped = []
        for e in entries:
            if e.kind == "delete":
                kind = "insert"
            elif e.kind == "insert":
                kind = "delete"
            else:
                kind = "context"
            mapped.append(PatchLine(kind, e.text))
        entries = mapped

    out: List[str] = []
    cursor = 0
    for entry in entries:
        if entry.kind == "insert":
            out.append(entry.text)
        else:  # context 或 delete 都必须在原文中按序出现
            if cursor >= len(original) or original[cursor] != entry.text:
                raise ValueError(
                    f"patch does not match original at line {cursor + 1}: {entry.text!r}"
                )
            if entry.kind == "context":
                out.append(entry.text)
            cursor += 1
    out.extend(original[cursor:])
    return "\n".join(out) + ("\n" if out else "")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zero-dependency line-level unified diff and patch (stdlib only)."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_diff = sub.add_parser("diff", help="print unified diff")
    p_diff.add_argument("old")
    p_diff.add_argument("new")
    p_diff.add_argument("-c", "--context", type=int, default=3)
    p_apply = sub.add_parser("apply", help="apply patch to original")
    p_apply.add_argument("original")
    p_apply.add_argument("patch")
    p_rev = sub.add_parser("reverse", help="reverse-apply patch (rollback)")
    p_rev.add_argument("original")
    p_rev.add_argument("patch")
    args = parser.parse_args(argv)

    try:
        if args.command == "diff":
            old_t = _read(args.old)
            new_t = _read(args.new)
            sys.stdout.write(unified_diff(old_t, new_t, context=args.context,
                                          old_name=args.old, new_name=args.new))
            return 0
        original = _read(args.original)
        patch = _read(args.patch)
        result = apply_patch(original, patch, reverse=(args.command == "reverse"))
        sys.stdout.write(result)
        return 0
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _read(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


if __name__ == "__main__":
    sys.exit(main())
