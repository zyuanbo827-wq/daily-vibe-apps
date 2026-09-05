import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from huffman import (
    build_codes,
    build_frequency,
    build_tree,
    compression_report,
    decode,
    encode,
    main,
)


class TestFrequencyAndTree(unittest.TestCase):
    def test_frequency(self):
        self.assertEqual(build_frequency("aabac"), {"a": 3, "b": 1, "c": 1})

    def test_empty_tree(self):
        self.assertIsNone(build_tree({}))
        self.assertEqual(build_codes(None), {})

    def test_tree_is_deterministic(self):
        text = "the quick brown fox"
        t1 = build_codes(build_tree(build_frequency(text)))
        t2 = build_codes(build_tree(build_frequency(text)))
        self.assertEqual(t1, t2)

    def test_codes_are_prefix_free(self):
        text = "abracadabra and a little bit more"
        codes = list(build_codes(build_tree(build_frequency(text))).values())
        for i, a in enumerate(codes):
            for j, b in enumerate(codes):
                if i != j:
                    self.assertFalse(b.startswith(a), f"{a} is prefix of {b}")

    def test_more_frequent_gets_no_longer_code(self):
        # z 出现 10 次，x 仅 1 次：z 的码不应比 x 长
        text = "z" * 10 + "x"
        codes = build_codes(build_tree(build_frequency(text)))
        self.assertLessEqual(len(codes["z"]), len(codes["x"]))


class TestEncodeDecode(unittest.TestCase):
    def roundtrip(self, text):
        data = encode(text)
        self.assertIsInstance(data, bytes)
        self.assertEqual(decode(data), text)

    def test_empty(self):
        import json
        import struct

        data = encode("")
        header_len = struct.unpack(">I", data[:4])[0]
        self.assertEqual(len(data), 4 + header_len)  # 空文本无比特主体
        header = json.loads(data[4:].decode("utf-8"))
        self.assertEqual(header["codes"], {})
        self.assertEqual(decode(data), "")

    def test_single_repeated_char(self):
        self.roundtrip("aaaaaaa")

    def test_two_chars(self):
        self.roundtrip("abababab")

    def test_all_padding_lengths(self):
        # 不同长度触发 0~7 的各种补齐位
        for n in range(1, 24):
            self.roundtrip(("ab" * n)[:n])

    def test_unicode_roundtrip(self):
        self.roundtrip("中文 Huffman 编码测试：熵编码、前缀码！🎉")

    def test_multiline_roundtrip(self):
        text = "line one\nline two\r\nline three\tindented\n" * 5
        self.roundtrip(text)

    def test_truncated_raises(self):
        with self.assertRaises(ValueError):
            decode(b"\x00")
        good = encode("hello world")
        with self.assertRaises(ValueError):
            decode(good[:-2])


class TestReportAndCli(unittest.TestCase):
    def test_report_roundtrip_line(self):
        report = compression_report("abracadabra " * 20)
        self.assertIn("roundtrip      : OK", report)
        self.assertIn("size ratio", report)

    def test_cli_encode_decode_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "s.txt")
            huf = os.path.join(tmp, "s.huf")
            out = os.path.join(tmp, "r.txt")
            text = "huffman coding is a lossless data compression algorithm. " * 10
            with open(src, "w", encoding="utf-8") as f:
                f.write(text)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code1 = main(["encode", src, "-o", huf])
            self.assertEqual(code1, 0)
            self.assertTrue(os.path.exists(huf))
            self.assertEqual(main(["decode", huf, "-o", out]), 0)
            with open(out, encoding="utf-8") as f:
                self.assertEqual(f.read(), text)

    def test_cli_stats_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "s.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("abcabcabc")
            self.assertEqual(main(["stats", src]), 0)

    def test_cli_preserves_crlf_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "crlf.txt")
            huf = os.path.join(tmp, "crlf.huf")
            out = os.path.join(tmp, "crlf.out")
            with open(src, "wb") as f:
                f.write("line1\r\nline2\r\n".encode("utf-8"))
            self.assertEqual(main(["encode", src, "-o", huf]), 0)
            self.assertEqual(main(["decode", huf, "-o", out]), 0)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), b"line1\r\nline2\r\n")


if __name__ == "__main__":
    unittest.main()
