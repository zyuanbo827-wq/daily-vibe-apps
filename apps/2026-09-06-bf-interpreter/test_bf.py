import io
import os
import sys
import tempfile
import unittest

from bf import build_bracket_map, run, strip_comments, main


class TestParsing(unittest.TestCase):
    def test_strip_comments(self):
        self.assertEqual(strip_comments("a+b c\n[d]"), "+[]")

    def test_prose_comment_without_instructions_is_ignored(self):
        # 普通英文单词不含指令符号时整行作为注释
        self.assertEqual(run("print three bell values\n+++.", ), bytes([3]))

    def test_instruction_symbols_inside_prose_still_run(self):
        # Brainfuck 语义：注释里只要出现指令符号就会执行（示例文件曾因此踩坑）
        self.assertEqual(strip_comments("non-command. end"), "-.")

    def test_bracket_pairs(self):
        pairs = build_bracket_map("++[>++<-]")
        self.assertEqual(pairs[2], 8)
        self.assertEqual(pairs[8], 2)

    def test_unmatched_open(self):
        with self.assertRaises(ValueError):
            build_bracket_map("++[>+")

    def test_unmatched_close(self):
        with self.assertRaises(ValueError):
            build_bracket_map("++>+]")


class TestCellArithmetic(unittest.TestCase):
    def test_increment_and_output(self):
        self.assertEqual(run("+++."), bytes([3]))

    def test_overflow_wraps_to_zero(self):
        self.assertEqual(run("+" * 256 + "."), bytes([0]))

    def test_underflow_wraps_to_255(self):
        self.assertEqual(run("-."), bytes([255]))

    def test_tape_grows_right(self):
        self.assertEqual(run(">>>++."), bytes([2]))

    def test_move_below_zero_raises(self):
        with self.assertRaises(RuntimeError):
            run("<")


class TestLoops(unittest.TestCase):
    def test_loop_multiplies_into_next_cell(self):
        # cell0 = 2，循环两次给 cell1 加 3 -> 6
        self.assertEqual(run("++[>+++<-]>."), bytes([6]))

    def test_zero_cell_skips_loop(self):
        # cell0 为 0，循环体不执行，随后输出 cell0=0
        self.assertEqual(run("[+++]."), bytes([0]))

    def test_nested_loops(self):
        # cell0=3，外层 3 次；每次给 cell1 加 2，最终 cell1=6
        self.assertEqual(run("+++[>++<-]>."), bytes([6]))
        # 嵌套：cell0=2，内层把 cell1 每次清零式累加 2*2 -> cell2=4
        code = "++[>++[>+<-]<-]>>."
        self.assertEqual(run(code), bytes([4]))


class TestIO(unittest.TestCase):
    def test_input_then_output(self):
        self.assertEqual(run(",.", b"A"), b"A")

    def test_cat_echo(self):
        self.assertEqual(run(",[.,]", b"brainfuck"), b"brainfuck")

    def test_eof_resets_cell_to_zero(self):
        # 先把单元加到 1，无输入时 ',' 应将其置 0，随后输出 0
        self.assertEqual(run("+,.", b""), bytes([0]))


class TestPrograms(unittest.TestCase):
    def test_hello_world(self):
        here = os.path.dirname(__file__)
        source = open(os.path.join(here, "examples", "hello.bf"), encoding="utf-8").read()
        self.assertEqual(run(source), b"Hello World!\n")

    def test_cli_runs_file_and_inline(self):
        here = os.path.dirname(__file__)
        hello = os.path.join(here, "examples", "hello.bf")
        buf = io.BytesIO()
        old = sys.stdout
        sys.stdout = type("S", (), {"buffer": buf})()
        try:
            code = main([hello])
        finally:
            sys.stdout = old
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue(), b"Hello World!\n")

        buf2 = io.BytesIO()
        sys.stdout = type("S", (), {"buffer": buf2})()
        try:
            self.assertEqual(main(["-e", "+++."]), 0)
        finally:
            sys.stdout = old
        self.assertEqual(buf2.getvalue(), bytes([3]))

    def test_cli_bad_program_returns_2(self):
        self.assertEqual(main(["-e", "++["]), 2)

    def test_cli_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "cat.bf")
            inp = os.path.join(tmp, "in.bin")
            with open(src, "w", encoding="utf-8") as f:
                f.write(",[.,]")
            with open(inp, "wb") as f:
                f.write(b"hi bf")
            buf = io.BytesIO()
            old = sys.stdout
            sys.stdout = type("S", (), {"buffer": buf})()
            try:
                code = main([src, "-i", inp])
            finally:
                sys.stdout = old
            self.assertEqual(code, 0)
            self.assertEqual(buf.getvalue(), b"hi bf")


if __name__ == "__main__":
    unittest.main()
