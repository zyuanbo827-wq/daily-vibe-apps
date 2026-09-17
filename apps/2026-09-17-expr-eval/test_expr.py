"""test_expr.py -- expr.py 的单元测试（标准库 unittest）。"""

import math
import subprocess
import sys
import unittest
from pathlib import Path

import expr

APP_DIR = Path(__file__).resolve().parent


class TestTokenizer(unittest.TestCase):
    def test_numbers_and_operators(self):
        toks = expr.tokenize("1 + 2.5*3")
        kinds = [(t[0], t[1]) for t in toks]
        self.assertEqual(
            kinds,
            [("NUM", 1.0), ("OP", "+"), ("NUM", 2.5), ("OP", "*"), ("NUM", 3.0)],
        )

    def test_scientific_and_leading_dot(self):
        self.assertAlmostEqual(expr.evaluate("1.5e2*2"), 300.0)
        self.assertAlmostEqual(expr.evaluate(".5 + .5"), 1.0)
        self.assertAlmostEqual(expr.evaluate("2E-1"), 0.2)

    def test_position_recorded(self):
        toks = expr.tokenize("  x")
        self.assertEqual(toks[0], ("IDENT", "x", 2))

    def test_unexpected_character(self):
        with self.assertRaisesRegex(expr.ExprError, "无法识别的字符"):
            expr.tokenize("3 @ 4")

    def test_empty(self):
        with self.assertRaisesRegex(expr.ExprError, "为空"):
            expr.to_rpn("   ")


class TestPrecedenceAndAssociativity(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(expr.evaluate("1 + 2 * 3"), 7.0)
        self.assertEqual(expr.evaluate("(1 + 2) * 3"), 9.0)
        self.assertEqual(expr.evaluate("7 / 2"), 3.5)
        self.assertEqual(expr.evaluate("2 + 3 * 4 - 6 / 2"), 11.0)

    def test_modulo(self):
        self.assertEqual(expr.evaluate("7 % 3"), 1.0)
        self.assertAlmostEqual(expr.evaluate("5.5 % 2"), 1.5)
        with self.assertRaisesRegex(expr.ExprError, "除数为零"):
            expr.evaluate("1 % 0")
        with self.assertRaisesRegex(expr.ExprError, "除数为零"):
            expr.evaluate("1 / 0")

    def test_power_right_associative(self):
        # 2^(3^2) == 512，(2^3)^2 == 64
        self.assertEqual(expr.evaluate("2 ^ 3 ^ 2"), 512.0)

    def test_unary_minus_vs_power_convention(self):
        # 数学惯例：-2^2 == -(2^2) == -4
        self.assertEqual(expr.evaluate("-2 ^ 2"), -4.0)
        self.assertEqual(expr.evaluate("(-2) ^ 2"), 4.0)
        self.assertAlmostEqual(expr.evaluate("2 ^ -2"), 0.25)
        self.assertEqual(expr.evaluate("--3"), 3.0)
        self.assertEqual(expr.evaluate("-3 * 2"), -6.0)
        self.assertEqual(expr.evaluate("2 * -3"), -6.0)
        self.assertEqual(expr.evaluate("1 + -2"), -1.0)
        self.assertEqual(expr.evaluate("+5"), 5.0)


class TestFunctionsAndConstants(unittest.TestCase):
    def test_basic_functions(self):
        self.assertEqual(expr.evaluate("sqrt(16)"), 4.0)
        self.assertEqual(expr.evaluate("abs(-5)"), 5.0)
        self.assertEqual(expr.evaluate("floor(2.9)"), 2.0)
        self.assertEqual(expr.evaluate("ceil(2.1)"), 3.0)
        self.assertEqual(expr.evaluate("round(2.6)"), 3.0)
        self.assertAlmostEqual(expr.evaluate("log(100)"), 2.0)
        self.assertAlmostEqual(expr.evaluate("ln(e)"), 1.0)
        self.assertAlmostEqual(expr.evaluate("sin(pi / 2)"), 1.0)
        self.assertAlmostEqual(expr.evaluate("cos(0)"), 1.0)
        self.assertAlmostEqual(expr.evaluate("exp(0)"), 1.0)

    def test_variadic_functions(self):
        self.assertEqual(expr.evaluate("max(2, 9, 3)"), 9.0)
        self.assertEqual(expr.evaluate("min(4, 2, 8)"), 2.0)
        self.assertEqual(expr.evaluate("min(7)"), 7.0)
        self.assertEqual(expr.evaluate("min(1, max(2, 3), 0)"), 0.0)
        self.assertEqual(expr.evaluate("max(-1, -5, abs(-9) * -1)"), -1.0)

    def test_nested_with_unary(self):
        self.assertEqual(expr.evaluate("min(-1, -2, -3)"), -3.0)
        self.assertAlmostEqual(expr.evaluate("sqrt(abs(-16))"), 4.0)

    def test_domain_errors(self):
        with self.assertRaisesRegex(expr.ExprError, "定义域"):
            expr.evaluate("sqrt(-1)")
        with self.assertRaisesRegex(expr.ExprError, "定义域"):
            expr.evaluate("ln(0)")
        with self.assertRaisesRegex(expr.ExprError, "定义域"):
            expr.evaluate("asin(2)")


class TestVariables(unittest.TestCase):
    def test_user_variables(self):
        self.assertEqual(expr.evaluate("x ^ 2 + y ^ 2", {"x": 3, "y": 4}), 25.0)
        self.assertAlmostEqual(expr.evaluate("pi * r ^ 2", {"r": 2}), 4 * math.pi)

    def test_unknown_variable(self):
        with self.assertRaisesRegex(expr.ExprError, "未知变量"):
            expr.evaluate("zzz + 1")


class TestSyntaxErrors(unittest.TestCase):
    def test_unknown_function(self):
        with self.assertRaisesRegex(expr.ExprError, "未知函数"):
            expr.evaluate("foo(1)")

    def test_parentheses_mismatch(self):
        with self.assertRaisesRegex(expr.ExprError, r"缺少 '\)'"):
            expr.evaluate("(1 + 2")
        with self.assertRaisesRegex(expr.ExprError, r"多余的 '\)'"):
            expr.evaluate("1 + 2)")

    def test_trailing_or_leading_binary_operator(self):
        with self.assertRaises(expr.ExprError):
            expr.evaluate("1 +")
        with self.assertRaises(expr.ExprError):
            expr.evaluate("* 2")

    def test_comma_outside_call(self):
        with self.assertRaisesRegex(expr.ExprError, "逗号"):
            expr.evaluate("1, 2")

    def test_function_arity(self):
        with self.assertRaisesRegex(expr.ExprError, "需要 1 个参数"):
            expr.evaluate("sqrt()")
        with self.assertRaisesRegex(expr.ExprError, "需要 1 个参数"):
            expr.evaluate("sqrt(1, 2)")
        with self.assertRaisesRegex(expr.ExprError, "至少需要 1 个参数"):
            expr.evaluate("min()")


class TestRpnAndFormatting(unittest.TestCase):
    def test_rpn_structure(self):
        rpn = expr.to_rpn("1 + 2")
        self.assertEqual(rpn, [1.0, 2.0, ("op", "+")])
        self.assertEqual(expr.rpn_to_text(expr.to_rpn("sqrt(4)")), "4 sqrt/1")

    def test_format_result(self):
        self.assertEqual(expr.format_result(4.0), "4")
        self.assertEqual(expr.format_result(0.5), "0.5")
        self.assertEqual(expr.format_result(1.0 / 3.0).startswith("0.33333"), True)


class TestCli(unittest.TestCase):
    def test_cli_expression(self):
        proc = subprocess.run(
            [sys.executable, str(APP_DIR / "expr.py"), "2 + 2"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "4")

    def test_cli_rpn_flag(self):
        proc = subprocess.run(
            [sys.executable, str(APP_DIR / "expr.py"), "--rpn", "1+2*3"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RPN:", proc.stdout)
        self.assertTrue(proc.stdout.strip().endswith("7"))

    def test_cli_error_exit_code(self):
        proc = subprocess.run(
            [sys.executable, str(APP_DIR / "expr.py"), "1/0"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("除数为零", proc.stderr)

    def test_repl_assignment(self):
        proc = subprocess.run(
            [sys.executable, str(APP_DIR / "expr.py")],
            input="x = 3\nx ^ 2 + 4 * x\nquit\n",
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("x = 3", proc.stdout)
        self.assertIn("21", proc.stdout)


if __name__ == "__main__":
    unittest.main()
