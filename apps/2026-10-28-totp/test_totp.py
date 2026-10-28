"""test_totp.py -- totp.py 的单元测试（标准库 unittest）。

RFC 4226 / RFC 4648 官方测试向量。
"""

import subprocess
import sys
import time
import unittest
from pathlib import Path

from totp import (
    base32_decode,
    base32_encode,
    generate_secret,
    hotp,
    totp,
    verify_totp,
)

APP_DIR = Path(__file__).resolve().parent

# RFC 4226 附录 D 的测试密钥（ASCII "12345678901234567890"）
RFC_SECRET = bytes.fromhex("3132333435363738393031323334353637383930")
RFC_HOTP = [
    "755224", "287082", "359152", "969429", "338314",
    "254676", "287922", "162583", "399871", "520489",
]


class TestBase32(unittest.TestCase):
    # RFC 4648 第 10 节测试向量
    VECTORS = [
        (b"", ""),
        (b"f", "MY"),
        (b"fo", "MZXQ"),
        (b"foo", "MZXW6"),
        (b"foob", "MZXW6YQ"),
        (b"fooba", "MZXW6YTB"),
        (b"foobar", "MZXW6YTBOI"),
    ]

    def test_encode_vectors(self):
        for raw, encoded in self.VECTORS:
            self.assertEqual(base32_encode(raw), encoded)

    def test_decode_vectors(self):
        for raw, encoded in self.VECTORS:
            self.assertEqual(base32_decode(encoded), raw)

    def test_roundtrip(self):
        for n in range(0, 40):
            data = bytes((i * 7 + 3) % 256 for i in range(n))
            self.assertEqual(base32_decode(base32_encode(data)), data)

    def test_decode_with_padding_and_spaces(self):
        self.assertEqual(base32_decode("MZXW6==="), b"foo")
        self.assertEqual(base32_decode("mzxw6"), b"foo")

    def test_invalid_character(self):
        with self.assertRaises(ValueError):
            base32_decode("MZX!6")


class TestHotp(unittest.TestCase):
    def test_rfc4226_vectors(self):
        for counter, expected in enumerate(RFC_HOTP):
            self.assertEqual(hotp(RFC_SECRET, counter), expected)

    def test_digits(self):
        self.assertEqual(len(hotp(RFC_SECRET, 0, digits=7)), 7)
        self.assertEqual(len(hotp(RFC_SECRET, 0, digits=8)), 8)

    def test_invalid_digits(self):
        with self.assertRaises(ValueError):
            hotp(RFC_SECRET, 0, digits=5)


class TestTotp(unittest.TestCase):
    def test_counter_derivation(self):
        # step=30：t=59 时 counter=1，应与 HOTP(secret,1) 一致
        self.assertEqual(totp(RFC_SECRET, timestamp=59, step=30),
                         hotp(RFC_SECRET, 1))
        self.assertEqual(totp(RFC_SECRET, timestamp=60, step=30),
                         hotp(RFC_SECRET, 2))

    def test_custom_step(self):
        self.assertEqual(totp(RFC_SECRET, timestamp=120, step=60),
                         hotp(RFC_SECRET, 2))

    def test_verify_current(self):
        now = time.time()
        code = totp(RFC_SECRET, timestamp=now)
        self.assertTrue(verify_totp(code, RFC_SECRET, timestamp=now))
        self.assertFalse(verify_totp("000000", RFC_SECRET, timestamp=now))

    def test_verify_window(self):
        now = 30 * 100  # 落在计数器 100
        code = hotp(RFC_SECRET, 101)  # 下一个时间步
        self.assertFalse(verify_totp(code, RFC_SECRET, timestamp=now, window=0))
        self.assertTrue(verify_totp(code, RFC_SECRET, timestamp=now, window=1))

    def test_generate_secret(self):
        secret = generate_secret()
        self.assertEqual(len(secret), 20)
        self.assertEqual(base32_decode(base32_encode(secret)), secret)
        with self.assertRaises(ValueError):
            generate_secret(5)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "totp.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("755224", proc.stdout)
        self.assertIn("verify now: True", proc.stdout)

    def test_genkey_code_verify(self):
        proc = self.run_cli("genkey")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        key = proc.stdout.strip()
        self.assertEqual(len(key), 32)  # 20 字节 -> 32 个 Base32 字符

        proc = self.run_cli("code", key)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        code = proc.stdout.strip()
        self.assertEqual(len(code), 6)

        proc = self.run_cli("verify", key, code)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("valid", proc.stdout)

        proc = self.run_cli("verify", key, "000000")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
