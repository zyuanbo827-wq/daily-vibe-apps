"""test_csvkit_lite.py -- csvkit_lite.py 的单元测试（标准库 unittest）。"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from csvkit_lite import (CsvError, Table, aggregate, needs_quoting,
                         parse_csv, write_csv)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample.csv"
SAMPLE_TEXT = SAMPLE.read_text(encoding="utf-8")


class TestParser(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_csv("a,b\n1,2"),
                         [["a", "b"], ["1", "2"]])

    def test_quoted_comma(self):
        self.assertEqual(parse_csv('a,"b,c",d'),
                         [["a", "b,c", "d"]])

    def test_escaped_quote(self):
        self.assertEqual(parse_csv('"a""b"'), [['a"b']])

    def test_embedded_newline(self):
        self.assertEqual(parse_csv('"a\nb"'), [["a\nb"]])

    def test_crlf(self):
        self.assertEqual(parse_csv("a,b\r\n1,2"),
                         [["a", "b"], ["1", "2"]])

    def test_empty_fields(self):
        self.assertEqual(parse_csv("a,,b"), [["a", "", "b"]])
        self.assertEqual(parse_csv("a,b,"), [["a", "b", ""]])

    def test_single_column_and_trailing_newline(self):
        self.assertEqual(parse_csv("a\n1\n2"), [["a"], ["1"], ["2"]])
        self.assertEqual(len(parse_csv("a,b\n1,2\n")), 2)

    def test_errors(self):
        with self.assertRaises(CsvError):
            parse_csv('"abc')
        with self.assertRaises(CsvError):
            parse_csv('a"b"')

    def test_bom_stripped(self):
        self.assertEqual(parse_csv("\ufeffa,b\n1,2")[0], ["a", "b"])


class TestWriter(unittest.TestCase):
    def test_quoting_rules(self):
        self.assertTrue(needs_quoting("a,b"))
        self.assertTrue(needs_quoting('a"b'))
        self.assertFalse(needs_quoting("plain123"))

    def test_roundtrip(self):
        rows = parse_csv(SAMPLE_TEXT)
        again = parse_csv(write_csv(rows))
        self.assertEqual(again, rows)


class TestTableOps(unittest.TestCase):
    def setUp(self):
        self.t = Table.from_text(SAMPLE_TEXT)

    def test_select(self):
        out = self.t.select(["name", "score"])
        self.assertEqual(out.headers, ["name", "score"])
        self.assertEqual(len(out.rows), 6)
        self.assertEqual(self.t.select(["*"]).headers, self.t.headers)

    def test_filter(self):
        self.assertEqual([r[0] for r in self.t.filter("city=Beijing").rows],
                         ["1", "5"])
        self.assertEqual(len(self.t.filter("score>80").rows), 3)
        self.assertEqual(len(self.t.filter("city!=Beijing").rows), 4)
        self.assertEqual(len(self.t.filter("tags contains math").rows), 3)

    def test_sort(self):
        out = self.t.sort("score", desc=True)
        self.assertEqual([r[1] for r in out.rows][:2], ["Eve", "Alice"])
        out2 = self.t.sort("name")
        self.assertEqual([r[1] for r in out2.rows][0], "Alice")

    def test_limit(self):
        self.assertEqual(len(self.t.limit(2).rows), 2)

    def test_unknown_column(self):
        with self.assertRaises(CsvError):
            self.t.select(["nope"])

    def test_formats(self):
        data = json.loads(self.t.to_json())
        self.assertEqual(data[0]["name"], "Alice")
        md = self.t.to_markdown()
        self.assertIn("---", md)
        t2 = Table(["a"], [["x|y"]])
        self.assertIn(r"x\|y", t2.to_markdown())


class TestAggregate(unittest.TestCase):
    def setUp(self):
        self.t = Table.from_text(SAMPLE_TEXT)

    def test_group_by(self):
        res = aggregate(self.t, "city", ["count", "avg:score"])
        d = dict(zip(res.headers, res.rows[0]))
        beijing = [r for r in res.rows if r[0] == "Beijing"][0]
        shanghai = [r for r in res.rows if r[0] == "Shanghai"][0]
        self.assertEqual(beijing[1], "2")
        self.assertEqual(beijing[2], "93")
        self.assertEqual(shanghai[2], "75")

    def test_overall(self):
        res = aggregate(self.t, None, ["count", "sum:score"])
        self.assertEqual(res.rows[0], ["6", "487"])

    def test_bad_agg(self):
        with self.assertRaises(CsvError):
            aggregate(self.t, "city", ["median:score"])


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "csvkit_lite.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Engineering", proc.stdout)

    def test_query_json(self):
        proc = self.run_cli("query", str(SAMPLE),
                            "--filter", "score>80",
                            "--sort", "score", "--desc",
                            "--select", "name,score",
                            "--format", "json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual([d["name"] for d in data],
                         ["Eve", "Alice", "Carol"])

    def test_stats_md(self):
        proc = self.run_cli("stats", str(SAMPLE), "--by", "city",
                            "--agg", "count,avg:score")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Beijing", proc.stdout)

    def test_stdin(self):
        proc = self.run_cli("query", "-", "--format", "json",
                            input_text="a,b\n1,2\n")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout), [{"a": "1", "b": "2"}])

    def test_missing_file_exit_two(self):
        proc = self.run_cli("query", "no.csv")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
