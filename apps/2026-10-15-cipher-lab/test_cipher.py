"""test_cipher.py -- cipher.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

from cipher import (caesar, chi_square_score, crack_all, crack_caesar,
                    rot13, vigenere)

APP_DIR = Path(__file__).resolve().parent
PLAIN = APP_DIR / "sample_plain.txt"
ENC = APP_DIR / "sample_encrypted.txt"


class TestCaesar(unittest.TestCase):
    def test_known_vector(self):
        self.assertEqual(caesar("abc", 3), "def")

    def test_wrap(self):
        self.assertEqual(caesar("xyz", 3), "abc")
        self.assertEqual(caesar("ABC", -3), "XYZ")

    def test_case_and_punctuation(self):
        self.assertEqual(caesar("Hello, World!", 3), "Khoor, Zruog!")

    def test_roundtrip(self):
        text = "The quick brown fox jumps over the lazy dog."
        self.assertEqual(caesar(caesar(text, 15), -15), text)

    def test_rot13_involution(self):
        text = "Python 3.13"
        self.assertEqual(rot13(rot13(text)), text)


class TestVigenere(unittest.TestCase):
    def test_known_vector(self):
        self.assertEqual(vigenere("ATTACKATDAWN", "LEMON"),
                         "LXFOPVEFRNHR")

    def test_roundtrip(self):
        text = "Meet me at the old bridge at noon."
        key = "SECRET"
        enc = vigenere(text, key)
        self.assertEqual(vigenere(enc, key, decrypt=True), text)

    def test_nonalpha_preserved(self):
        enc = vigenere("hi there!", "x")
        self.assertEqual(enc[2], " ")
        self.assertTrue(enc.endswith("!"))

    def test_key_cleaned(self):
        self.assertEqual(vigenere("ATTACK", "L! E M-1"),
                         vigenere("ATTACK", "LEM"))

    def test_empty_key_raises(self):
        with self.assertRaises(ValueError):
            vigenere("abc", "123")


class TestCrack(unittest.TestCase):
    def test_english_scores_lower_than_shifted(self):
        plain = PLAIN.read_text(encoding="utf-8")
        self.assertLess(chi_square_score(plain),
                        chi_square_score(caesar(plain, 7)))

    def test_no_letters(self):
        self.assertEqual(chi_square_score("123 - !!"), float("inf"))

    def test_crack_recovers_shift(self):
        enc_text = ENC.read_text(encoding="utf-8")
        shift, plain, _ = crack_caesar(enc_text)
        self.assertEqual(shift, (26 - 7) % 26)
        self.assertEqual(plain,
                         PLAIN.read_text(encoding="utf-8"))

    def test_crack_all_has_26(self):
        rows = crack_all(ENC.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 26)
        self.assertEqual(len({r[0] for r in rows}), 26)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "cipher.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("LXFOPVEFRNHR", proc.stdout)
        self.assertIn("matches=True", proc.stdout)

    def test_caesar_cli(self):
        proc = self.run_cli("caesar", "abc", "-s", "3")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "def")

    def test_vigenere_cli_decrypt(self):
        proc = self.run_cli("vigenere", "LXFOPVEFRNHR",
                            "-k", "LEMON", "-d")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "ATTACKATDAWN")

    def test_crack_file(self):
        proc = self.run_cli("crack", str(ENC))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("best shift: 19", proc.stdout)

    def test_crack_missing_file_exit_two(self):
        proc = self.run_cli("crack", "no.txt")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
