import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime

from cronnext import CronExpr, main, parse_field


class TestParseField(unittest.TestCase):
    def test_wildcard(self):
        self.assertEqual(parse_field("*", 0, 59), set(range(0, 60)))

    def test_single_and_list(self):
        self.assertEqual(parse_field("5", 0, 59), {5})
        self.assertEqual(parse_field("1,3,5", 0, 59), {1, 3, 5})

    def test_range(self):
        self.assertEqual(parse_field("1-5", 1, 31), {1, 2, 3, 4, 5})

    def test_step_wildcard(self):
        self.assertEqual(parse_field("*/15", 0, 59), {0, 15, 30, 45})

    def test_step_range(self):
        self.assertEqual(parse_field("9-18/3", 0, 23), {9, 12, 15, 18})

    def test_step_from_number(self):
        self.assertEqual(parse_field("5/20", 0, 59), {5, 25, 45})

    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            parse_field("61", 0, 59)
        with self.assertRaises(ValueError):
            parse_field("10-5", 0, 59)

    def test_bad_step(self):
        with self.assertRaises(ValueError):
            parse_field("*/0", 0, 59)


class TestParseExpression(unittest.TestCase):
    def test_wrong_field_count(self):
        with self.assertRaises(ValueError):
            CronExpr.parse("* * *")

    def test_sunday_7_normalized(self):
        expr = CronExpr.parse("0 0 * * 7")
        self.assertIn(0, expr.dow)
        self.assertNotIn(7, expr.dow)


class TestNextAfter(unittest.TestCase):
    def test_every_15_minutes(self):
        expr = CronExpr.parse("*/15 * * * *")
        nxt = expr.next_after(datetime(2026, 9, 4, 10, 7))
        self.assertEqual(nxt, datetime(2026, 9, 4, 10, 15))

    def test_daily_time_already_passed_rolls_to_next_day(self):
        expr = CronExpr.parse("30 19 * * *")
        nxt = expr.next_after(datetime(2026, 9, 4, 19, 33))
        self.assertEqual(nxt, datetime(2026, 9, 5, 19, 30))

    def test_inclusive_matches_current_minute(self):
        expr = CronExpr.parse("30 19 * * *")
        nxt = expr.next_after(datetime(2026, 9, 4, 19, 30), inclusive=True)
        self.assertEqual(nxt, datetime(2026, 9, 4, 19, 30))

    def test_weekday_only_skips_weekend(self):
        expr = CronExpr.parse("0 9 * * 1-5")  # 工作日 9 点
        # 2026-09-04 是周五，下一次应是周一 2026-09-07
        nxt = expr.next_after(datetime(2026, 9, 4, 19, 33))
        self.assertEqual(nxt, datetime(2026, 9, 7, 9, 0))

    def test_monthly_first_day_rolls_over_month(self):
        expr = CronExpr.parse("0 0 1 * *")
        nxt = expr.next_after(datetime(2026, 9, 4, 12, 0))
        self.assertEqual(nxt, datetime(2026, 10, 1, 0, 0))

    def test_sunday_midnight(self):
        expr = CronExpr.parse("0 0 * * 0")
        nxt = expr.next_after(datetime(2026, 9, 4, 19, 33))  # Friday
        self.assertEqual(nxt, datetime(2026, 9, 6, 0, 0))   # Sunday


class TestDomDowOrRule(unittest.TestCase):
    def setUp(self):
        # 每月 13 号 或 周五 触发（Vixie 或规则）
        self.expr = CronExpr.parse("0 0 13 * 5")

    def test_friday_13th_matches(self):
        self.assertEqual(datetime(2026, 11, 13).weekday(), 4)  # 确认确实是周五
        self.assertTrue(self.expr.matches(datetime(2026, 11, 13, 0, 0)))

    def test_friday_not_13th_also_matches(self):
        # 2026-09-04 是周五但不是 13 号，按或规则仍匹配
        self.assertTrue(self.expr.matches(datetime(2026, 9, 4, 0, 0)))

    def test_neither_matches(self):
        self.assertFalse(self.expr.matches(datetime(2026, 9, 3, 0, 0)))  # 周四、非13号


class TestNextN(unittest.TestCase):
    def test_count_order_and_ascending(self):
        expr = CronExpr.parse("0 */6 * * *")  # 每天 0/6/12/18 点
        seq = expr.next_n(datetime(2026, 9, 4, 19, 33), 4)
        self.assertEqual(len(seq), 4)
        self.assertEqual(seq, [
            datetime(2026, 9, 5, 0, 0),
            datetime(2026, 9, 5, 6, 0),
            datetime(2026, 9, 5, 12, 0),
            datetime(2026, 9, 5, 18, 0),
        ])
        self.assertEqual(seq, sorted(seq))


class TestCli(unittest.TestCase):
    def test_valid_cli_returns_0_and_prints(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["30 19 * * *", "--from", "2026-09-04 19:33", "-n", "1"])
        self.assertEqual(code, 0)
        self.assertIn("2026-09-05 19:30", buf.getvalue())

    def test_invalid_cli_returns_2(self):
        self.assertEqual(main(["61 * * * *"]), 2)


if __name__ == "__main__":
    unittest.main()
