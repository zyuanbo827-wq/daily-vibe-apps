"""test_jsonlite.py -- jsonlite.py 的单元测试（标准库 unittest）。"""

import json as stdjson
import random
import subprocess
import sys
import unittest
from pathlib import Path

import jsonlite
from jsonlite import JSONError, dumps, loads, query

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample.json"


class TestLiterals(unittest.TestCase):
    def test_literals(self):
        self.assertIsNone(loads("null"))
        self.assertIs(loads("true"), True)
        self.assertIs(loads("false"), False)

    def test_whitespace_padding(self):
        self.assertEqual(loads("  \n\t42 "), 42)

    def test_empty_and_trailing(self):
        with self.assertRaises(JSONError):
            loads("")
        with self.assertRaises(JSONError):
            loads("1 2")
        with self.assertRaises(JSONError):
            loads("truex")


class TestNumbers(unittest.TestCase):
    def test_valid_numbers(self):
        self.assertEqual(loads("0"), 0)
        self.assertEqual(loads("-0"), 0)
        self.assertEqual(loads("-17"), -17)
        self.assertEqual(loads("3.14"), 3.14)
        self.assertEqual(loads("1e3"), 1000.0)
        self.assertEqual(loads("-2.5E-2"), -0.025)
        self.assertIsInstance(loads("10"), int)
        self.assertIsInstance(loads("10.0"), float)

    def test_invalid_numbers(self):
        for bad in ["01", "+1", "1.", ".5", "1e", "1E+", "00", "- 1", "NaN",
                    "Infinity", "-Infinity"]:
            with self.assertRaises(JSONError, msg=bad):
                loads(bad)


class TestStrings(unittest.TestCase):
    def test_simple_escapes(self):
        self.assertEqual(loads(r'"a\nb\tc\\d\"e\/f"'),
                         'a\nb\tc\\d"e/f')

    def test_unicode_escape(self):
        self.assertEqual(loads(r'"\u00e9"'), "é")
        self.assertEqual(loads(r'"\u00E9"'), "é")

    def test_surrogate_pair(self):
        self.assertEqual(loads(r'"\uD83D\uDE00"'), "\U0001F600")

    def test_lone_surrogate_rejected(self):
        with self.assertRaises(JSONError):
            loads(r'"\uD83D"')
        with self.assertRaises(JSONError):
            loads(r'"\uDE00"')

    def test_bad_escape_and_unclosed(self):
        with self.assertRaises(JSONError):
            loads(r'"\x"')
        with self.assertRaises(JSONError):
            loads('"abc')
        with self.assertRaises(JSONError):
            loads('"a\nb"')  # 未转义换行


class TestContainers(unittest.TestCase):
    def test_array_and_object(self):
        self.assertEqual(loads("[1, [2, 3], {}]"), [1, [2, 3], {}])
        self.assertEqual(loads('{"a": 1, "b": [true, null]}'),
                         {"a": 1, "b": [True, None]})

    def test_trailing_comma_rejected(self):
        with self.assertRaises(JSONError):
            loads("[1, 2,]")
        with self.assertRaises(JSONError):
            loads('{"a": 1,}')

    def test_strict_syntax_rejected(self):
        for bad in ["{'a': 1}", "{a: 1}", "// comment\n1", "[1,] ",
                    '{"a" 1}', "[1 2]", '{"a":1 "b":2}']:
            with self.assertRaises(JSONError, msg=bad):
                loads(bad)

    def test_duplicate_keys_last_wins(self):
        self.assertEqual(loads('{"x": 1, "x": 2}'), {"x": 2})

    def test_error_has_position(self):
        try:
            loads('{\n  "a": x\n}')
        except JSONError as exc:
            self.assertEqual(exc.line, 2)
            self.assertGreaterEqual(exc.col, 1)
        else:
            self.fail("应当报错")


class TestStdlibEquivalence(unittest.TestCase):
    def make_value(self, rng, depth=0):
        if depth > 3:
            choices = ["num", "str", "bool"]
        else:
            choices = ["obj", "arr", "num", "str", "bool", "null"]
        kind = rng.choice(choices)
        if kind == "obj":
            return {
                f"k{rng.randrange(100)}": self.make_value(rng, depth + 1)
                for _ in range(rng.randrange(5))
            }
        if kind == "arr":
            return [self.make_value(rng, depth + 1)
                    for _ in range(rng.randrange(6))]
        if kind == "num":
            return rng.choice([
                rng.randrange(-10000, 10000),
                round(rng.uniform(-100, 100), 4),
            ])
        if kind == "str":
            return "".join(rng.choice("ab cd\tef\\gh\"ij0123é")
                           for _ in range(rng.randrange(12)))
        if kind == "bool":
            return rng.choice([True, False])
        return None

    def test_random_corpus_matches_stdlib(self):
        rng = random.Random(20260922)
        for _ in range(200):
            value = self.make_value(rng)
            for kwargs in ({}, {"indent": 2}, {"separators": (",", ":")}):
                text = stdjson.dumps(value, ensure_ascii=False, **kwargs)
                self.assertEqual(loads(text), stdjson.loads(text), text)


class TestDumps(unittest.TestCase):
    def test_roundtrip(self):
        obj = {"a": [1, 2, {"b": True, "c": None}], "d": "x\ny"}
        self.assertEqual(stdjson.loads(dumps(obj)), obj)
        self.assertEqual(stdjson.loads(dumps(obj, indent=2)), obj)

    def test_minify_and_pretty(self):
        self.assertNotIn("\n", dumps([1, 2]))
        pretty = dumps({"a": [1, 2]}, indent=2)
        self.assertIn("\n", pretty)
        self.assertIn("  ", pretty)
        self.assertEqual(dumps([]), "[]")
        self.assertEqual(dumps({}), "{}")

    def test_tuple_and_rejects(self):
        self.assertEqual(dumps((1, 2)), "[1,2]")
        with self.assertRaises(JSONError):
            dumps(float("nan"))
        with self.assertRaises(JSONError):
            dumps({1: "x"})
        with self.assertRaises(JSONError):
            dumps(object())


class TestQuery(unittest.TestCase):
    def setUp(self):
        self.data = loads(SAMPLE.read_text(encoding="utf-8"))

    def test_dot_and_brackets(self):
        self.assertEqual(query(self.data, "name"), "daily-vibe")
        self.assertEqual(query(self.data, "tags[1]"), "stdlib")
        self.assertEqual(query(self.data, "items[0].id"), 1)
        self.assertEqual(query(self.data, "$['items'][1]['ok']"), True)

    def test_negative_index(self):
        self.assertEqual(query(self.data, "countdown[-1]"), 0)

    def test_quoted_key_with_dot(self):
        data = {"a.b": {"c": 3}}
        self.assertEqual(query(data, '["a.b"].c'), 3)

    def test_errors(self):
        with self.assertRaises(JSONError):
            query(self.data, "nope")
        with self.assertRaises(JSONError):
            query(self.data, "tags[9]")
        with self.assertRaises(JSONError):
            query(self.data, "name[0]")  # 对字符串取下标
        with self.assertRaises(JSONError):
            query(self.data, "tags.x")


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "jsonlite.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_validate(self):
        ok = self.run_cli("validate", str(SAMPLE))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("JSON 合法", ok.stdout)

        bad = self.run_cli("validate", "-", input_text="{a:1}")
        self.assertEqual(bad.returncode, 1)

        missing = self.run_cli("validate", "no-such.json")
        self.assertEqual(missing.returncode, 2)

    def test_get(self):
        proc = self.run_cli("get", str(SAMPLE), "items[1].id")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "2")

        nested = self.run_cli("get", str(SAMPLE), "tags")
        self.assertEqual(nested.returncode, 0)
        self.assertEqual(loads(nested.stdout),
                         ["python", "stdlib", "cli"])

        bad_path = self.run_cli("get", str(SAMPLE), "nope.key")
        self.assertEqual(bad_path.returncode, 1)

    def test_pretty_and_minify(self):
        pretty = self.run_cli("pretty", str(SAMPLE))
        self.assertEqual(pretty.returncode, 0, pretty.stderr)
        self.assertIn("\n", pretty.stdout)

        mini = self.run_cli("minify", str(SAMPLE))
        self.assertEqual(mini.returncode, 0)
        self.assertNotIn("\n", mini.stdout.strip())
        self.assertEqual(loads(mini.stdout), loads(pretty.stdout))

    def test_stdin_roundtrip(self):
        proc = self.run_cli("minify", "-", input_text='{"x" : [ 1, 2 ]}')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), '{"x":[1,2]}')


if __name__ == "__main__":
    unittest.main()
