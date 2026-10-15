"""cipher.py -- 零依赖古典密码实验台。

实现：
- Caesar 凯撒移位（含 ROT13）
- Vigenere 维吉尼亚密码
- 基于英文字母频率卡方评分的 Caesar 自动破解
只处理 A-Z / a-z，大小写保留，非字母字符原样保留。
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Tuple

# 英文书面语字母频率（百分比，常见基准）
ENGLISH_FREQ = {
    "a": 8.17, "b": 1.49, "c": 2.78, "d": 4.25, "e": 12.70,
    "f": 2.23, "g": 2.02, "h": 6.09, "i": 6.97, "j": 0.15,
    "k": 0.77, "l": 4.03, "m": 2.41, "n": 6.75, "o": 7.51,
    "p": 1.93, "q": 0.10, "r": 5.99, "s": 6.33, "t": 9.06,
    "u": 2.76, "v": 0.98, "w": 2.36, "x": 0.15, "y": 1.97,
    "z": 0.07,
}


# --------------------------------------------------------------------------- #
# Caesar
# --------------------------------------------------------------------------- #
def _shift_char(ch: str, shift: int) -> str:
    base = ord("A" if ch.isupper() else "a")
    return chr((ord(ch) - base + shift) % 26 + base)


def caesar(text: str, shift: int) -> str:
    out = []
    for ch in text:
        if ch.isalpha():
            out.append(_shift_char(ch, shift))
        else:
            out.append(ch)
    return "".join(out)


def rot13(text: str) -> str:
    return caesar(text, 13)


# --------------------------------------------------------------------------- #
# Vigenere
# --------------------------------------------------------------------------- #
def _clean_key(key: str) -> str:
    letters = [ch.lower() for ch in key if ch.isalpha()]
    if not letters:
        raise ValueError("密钥必须包含至少一个字母")
    return "".join(letters)


def vigenere(text: str, key: str, decrypt: bool = False) -> str:
    key = _clean_key(key)
    shifts = [ord(k) - ord("a") for k in key]
    sign = -1 if decrypt else 1
    out = []
    ki = 0
    for ch in text:
        if ch.isalpha():
            out.append(_shift_char(ch, sign * shifts[ki % len(shifts)]))
            ki += 1
        else:
            out.append(ch)
    return "".join(out)


# --------------------------------------------------------------------------- #
# 频率分析与破解
# --------------------------------------------------------------------------- #
def chi_square_score(text: str) -> float:
    """英文字母频率卡方距离，越小越像英文。"""
    letters = [ch.lower() for ch in text if ch.isalpha()]
    n = len(letters)
    if n == 0:
        return float("inf")
    counts = {c: 0 for c in ENGLISH_FREQ}
    for ch in letters:
        counts[ch] += 1
    score = 0.0
    for c, expected_pct in ENGLISH_FREQ.items():
        expected = expected_pct / 100.0 * n
        observed = counts[c]
        score += (observed - expected) ** 2 / max(expected, 1e-9)
    return score


def crack_caesar(text: str) -> Tuple[int, str, float]:
    """枚举 26 个移位，返回卡方最小的 (shift, 明文, 分数)。"""
    best = None
    for shift in range(26):
        candidate = caesar(text, shift)
        score = chi_square_score(candidate)
        if best is None or score < best[2]:
            best = (shift, candidate, score)
    return best


def crack_all(text: str) -> List[Tuple[int, float, str]]:
    rows = []
    for shift in range(26):
        candidate = caesar(text, shift)
        rows.append((shift, chi_square_score(candidate), candidate))
    return sorted(rows, key=lambda r: r[1])


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_caesar(args) -> int:
    print(caesar(args.text, -args.shift if args.decrypt else args.shift))
    return 0


def cmd_rot13(args) -> int:
    print(rot13(args.text))
    return 0


def cmd_vigenere(args) -> int:
    print(vigenere(args.text, args.key, args.decrypt))
    return 0


def cmd_crack(args) -> int:
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print("error: file not found", file=sys.stderr)
        return 2
    shift, plain, score = crack_caesar(text)
    print(f"best shift: {shift}  (chi-square: {score:.1f})")
    print("-" * 40)
    print(plain)
    return 0


def cmd_demo(args) -> int:
    secret = "The quick brown fox jumps over the lazy dog."
    enc = caesar(secret, 7)
    print("caesar shift 7:", enc)
    print("decrypted:    ", caesar(enc, -7))
    print("rot13 twice:  ", rot13(rot13(secret)) == secret)

    vig = vigenere("ATTACKATDAWN", "LEMON")
    print("vigenere ATTACKATDAWN / LEMON ->", vig)
    print("decrypted:", vigenere(vig, "LEMON", decrypt=True))

    shifted = caesar(secret, 15)
    shift, plain, score = crack_caesar(shifted)
    print(f"cracked shifted text: shift={shift}, matches={plain == secret}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="古典密码实验台（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("caesar", help="凯撒移位")
    pc.add_argument("text")
    pc.add_argument("-s", "--shift", type=int, default=3)
    pc.add_argument("-d", "--decrypt", action="store_true")
    pc.set_defaults(func=cmd_caesar)

    pr = sub.add_parser("rot13")
    pr.add_argument("text")
    pr.set_defaults(func=cmd_rot13)

    pv = sub.add_parser("vigenere", help="维吉尼亚密码")
    pv.add_argument("text")
    pv.add_argument("-k", "--key", required=True)
    pv.add_argument("-d", "--decrypt", action="store_true")
    pv.set_defaults(func=cmd_vigenere)

    pk = sub.add_parser("crack", help="频率分析破解 Caesar")
    pk.add_argument("file")
    pk.set_defaults(func=cmd_crack)

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
