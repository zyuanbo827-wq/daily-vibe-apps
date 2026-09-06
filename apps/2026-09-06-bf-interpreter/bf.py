"""bf-interpreter：零依赖 Brainfuck 解释器（仅 Python 标准库）。

语义约定：
- 纸带单元为 8 位无符号整数，``+``/``-`` 在 0~255 间回绕；
- 指针向右自动扩展纸带；向左越过 0 抛 ``RuntimeError``；
- ``,`` 读取一个输入字节，输入结束（EOF）时把当前单元置 0（最常见约定，
  保证 ``,[.,]`` 这类回环程序能正常终止）；
- 非 Brainfuck 指令字符一律视为注释忽略；
- 方括号不配对时在解析阶段抛 ``ValueError`` 并给出位置。

命令行：
    python bf.py examples/hello.bf
    python bf.py -e "++[>+++<-]>."
    python bf.py echo.bf --input-file input.bin
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

COMMANDS = set("+-<>[].,")


def strip_comments(source: str) -> str:
    """保留 8 个合法指令，其余字符作为注释丢弃。"""
    return "".join(ch for ch in source if ch in COMMANDS)


def build_bracket_map(code: str) -> Dict[int, int]:
    """预计算每个 [ 与 ] 的配对位置；不配对则抛 ValueError。"""
    pairs: Dict[int, int] = {}
    stack: list[int] = []
    for pos, ch in enumerate(code):
        if ch == "[":
            stack.append(pos)
        elif ch == "]":
            if not stack:
                raise ValueError(f"unmatched ']' at position {pos}")
            left = stack.pop()
            pairs[left] = pos
            pairs[pos] = left
    if stack:
        raise ValueError(f"unmatched '[' at position {stack[-1]}")
    return pairs


def run(source: str, data: bytes = b"") -> bytes:
    """执行 Brainfuck 源码，返回输出字节串。"""
    code = strip_comments(source)
    jumps = build_bracket_map(code)

    tape = bytearray([0])
    pointer = 0
    pc = 0
    inputs = iter(data)
    output = bytearray()

    while pc < len(code):
        command = code[pc]
        if command == ">":
            pointer += 1
            if pointer == len(tape):
                tape.append(0)
        elif command == "<":
            pointer -= 1
            if pointer < 0:
                raise RuntimeError(f"tape pointer moved below 0 at position {pc}")
        elif command == "+":
            tape[pointer] = (tape[pointer] + 1) & 0xFF
        elif command == "-":
            tape[pointer] = (tape[pointer] - 1) & 0xFF
        elif command == ".":
            output.append(tape[pointer])
        elif command == ",":
            nxt = next(inputs, None)
            tape[pointer] = 0 if nxt is None else nxt  # EOF 置 0
        elif command == "[":
            if tape[pointer] == 0:
                pc = jumps[pc]
        elif command == "]":
            if tape[pointer] != 0:
                pc = jumps[pc]
        pc += 1

    return bytes(output)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zero-dependency Brainfuck interpreter (Python stdlib only)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs="?", help="path to a .bf source file")
    group.add_argument("-e", "--eval", dest="expr", help="inline Brainfuck code")
    parser.add_argument("-i", "--input-file", help="binary input fed to ',' commands")
    args = parser.parse_args(argv)

    source = args.expr if args.expr is not None else Path(args.file).read_text(encoding="utf-8")
    data = Path(args.input_file).read_bytes() if args.input_file else b""

    try:
        result = run(source, data)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(result)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
