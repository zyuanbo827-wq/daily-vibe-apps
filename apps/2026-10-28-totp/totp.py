"""totp.py -- 零依赖 TOTP/HOTP 动态口令（两步验证）实现。

对应 RFC 4648（Base32）、RFC 4226（HOTP）、RFC 6238（TOTP）：
- Base32 编码/解码
- HOTP：HMAC-SHA1 + 动态截断
- TOTP：以时间步长派生计数器
- 带时间窗口的校验
并附带 CLI（生成密钥 / 取当前口令 / 校验）。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import secrets
import sys
import time
from typing import List, Optional

# --------------------------------------------------------------------------- #
# Base32（RFC 4648）
# --------------------------------------------------------------------------- #
_B32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def base32_encode(data: bytes) -> str:
    """把字节串编码为无填充的 Base32 字符串。"""
    out: List[str] = []
    buf = 0
    bits = 0
    for byte in data:
        buf = (buf << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            out.append(_B32_ALPHABET[(buf >> bits) & 0x1F])
    if bits:
        out.append(_B32_ALPHABET[(buf << (5 - bits)) & 0x1F])
    return "".join(out)


def base32_decode(text: str) -> bytes:
    """解码无填充（或带 = 填充）的 Base32 字符串。"""
    text = text.upper().replace("=", "").replace(" ", "").strip()
    if not text:
        return b""
    for ch in text:
        if ch not in _B32_ALPHABET:
            raise ValueError(f"非法 Base32 字符: {ch!r}")
    buf = 0
    bits = 0
    out = bytearray()
    for ch in text:
        buf = (buf << 5) | _B32_ALPHABET.index(ch)
        bits += 5
        if bits >= 8:
            bits -= 8
            out.append((buf >> bits) & 0xFF)
    return bytes(out)


# --------------------------------------------------------------------------- #
# HOTP / TOTP
# --------------------------------------------------------------------------- #
def hotp(secret: bytes, counter: int, digits: int = 6) -> str:
    """RFC 4226 HOTP：计数器 + 共享密钥生成数字口令。"""
    if digits < 6 or digits > 8:
        raise ValueError("digits 必须在 6~8 之间")
    counter_bytes = counter.to_bytes(8, "big")
    mac = hmac.new(secret, counter_bytes, hashlib.sha1).digest()
    # 动态截断：取最后一个字节低 4 位作为偏移
    offset = mac[-1] & 0x0F
    code = (
        ((mac[offset] & 0x7F) << 24)
        | (mac[offset + 1] << 16)
        | (mac[offset + 2] << 8)
        | mac[offset + 3]
    )
    return str(code % 10**digits).zfill(digits)


def totp(
    secret: bytes,
    timestamp: Optional[float] = None,
    step: int = 30,
    digits: int = 6,
) -> str:
    """RFC 6238 TOTP：把当前时间换算成计数器后走 HOTP。"""
    if timestamp is None:
        timestamp = time.time()
    counter = int(timestamp) // step
    return hotp(secret, counter, digits)


def verify_totp(
    code: str,
    secret: bytes,
    timestamp: Optional[float] = None,
    step: int = 30,
    digits: int = 6,
    window: int = 1,
) -> bool:
    """校验口令，允许前后各 window 个时间步（容忍时钟漂移）。"""
    if timestamp is None:
        timestamp = time.time()
    counter = int(timestamp) // step
    for delta in range(-window, window + 1):
        if hmac.compare_digest(hotp(secret, counter + delta, digits), code):
            return True
    return False


def generate_secret(length: int = 20) -> bytes:
    """生成随机共享密钥（默认 20 字节，即 160 位）。"""
    if length < 10:
        raise ValueError("密钥长度至少 10 字节")
    return secrets.token_bytes(length)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_genkey(args) -> int:
    secret = generate_secret(args.bytes)
    print(base32_encode(secret))
    return 0


def cmd_code(args) -> int:
    secret = base32_decode(args.secret)
    print(totp(secret, digits=args.digits, step=args.step))
    return 0


def cmd_verify(args) -> int:
    secret = base32_decode(args.secret)
    ok = verify_totp(
        args.code, secret, digits=args.digits, step=args.step, window=args.window
    )
    print("valid" if ok else "invalid")
    return 0 if ok else 1


def cmd_demo(args) -> int:
    # RFC 4226 测试密钥
    secret = bytes.fromhex("3132333435363738393031323334353637383930")
    print("secret (base32):", base32_encode(secret))
    print("HOTP counters 0-9:")
    for i in range(10):
        print(f"  {i}: {hotp(secret, i)}")
    now = time.time()
    current = totp(secret, timestamp=now)
    print("TOTP now:", current)
    print("verify now:", verify_totp(current, secret, timestamp=now))
    print("verify wrong:", verify_totp("000000", secret, timestamp=now))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="TOTP/HOTP 动态口令（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pg = sub.add_parser("genkey", help="生成随机密钥（输出 Base32）")
    pg.add_argument("--bytes", type=int, default=20)
    pg.set_defaults(func=cmd_genkey)

    pc = sub.add_parser("code", help="取当前 TOTP 口令")
    pc.add_argument("secret", help="Base32 密钥")
    pc.add_argument("--digits", type=int, default=6)
    pc.add_argument("--step", type=int, default=30)
    pc.set_defaults(func=cmd_code)

    pv = sub.add_parser("verify", help="校验口令")
    pv.add_argument("secret")
    pv.add_argument("code")
    pv.add_argument("--digits", type=int, default=6)
    pv.add_argument("--step", type=int, default=30)
    pv.add_argument("--window", type=int, default=1)
    pv.set_defaults(func=cmd_verify)

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
