"""test_md2html.py -- md2html.py 的单元测试（标准库 unittest）。"""

import subprocess
import sys
import unittest
from pathlib import Path

from md2html import convert, inline, parse_blocks, safe_url

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample.md"


class TestHeadingsHr(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(parse_blocks("# H1"), "<h1>H1</h1>")
        self.assertEqual(parse_blocks("### H3"), "<h3>H3</h3>")
        self.assertEqual(parse_blocks("###### H6"), "<h6>H6</h6>")

    def test_seven_hashes_are_paragraph(self):
        out = parse_blocks("####### not heading")
        self.assertTrue(out.startswith("<p>"))

    def test_hr(self):
        self.assertEqual(parse_blocks("---"), "<hr>")
        self.assertEqual(parse_blocks("***"), "<hr>")
        self.assertTrue(parse_blocks("--").startswith("<p>"))


class TestParagraphs(unittest.TestCase):
    def test_line_merge(self):
        self.assertEqual(parse_blocks("a\nb"), "<p>a b</p>")

    def test_blank_line_splits(self):
        out = parse_blocks("a\n\nb")
        self.assertEqual(out.count("<p>"), 2)


class TestInline(unittest.TestCase):
    def test_bold_italic(self):
        self.assertEqual(inline("**b**"), "<strong>b</strong>")
        self.assertEqual(inline("__b__"), "<strong>b</strong>")
        self.assertEqual(inline("*i*"), "<em>i</em>")
        self.assertEqual(inline("_i_"), "<em>i</em>")

    def test_inline_code_escaped_and_verbatim(self):
        out = inline("use `x<y>` now")
        self.assertIn("<code>x&lt;y&gt;</code>", out)
        out2 = inline("`**a**`")
        self.assertIn("<code>**a**</code>", out2)
        self.assertNotIn("<strong>", out2)

    def test_raw_html_escaped(self):
        out = parse_blocks("<script>alert(1)</script>")
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>", out)


class TestLinksImages(unittest.TestCase):
    def test_safe_link(self):
        self.assertIn('<a href="https://example.com">t</a>',
                      inline("[t](https://example.com)") )
        self.assertIn('<a href="./a.md">t</a>',
                      inline("[t](./a.md)"))

    def test_dangerous_link_rejected(self):
        out = inline("[x](javascript:alert(1))")
        self.assertNotIn("<a", out)
        self.assertIn("javascript", out)

    def test_image(self):
        out = inline("![alt](https://example.com/a.png)")
        self.assertIn("<img", out)
        self.assertIn('alt="alt"', out)
        self.assertNotIn("<img", inline("![a](javascript:alert(1))"))

    def test_safe_url(self):
        self.assertEqual(safe_url("https://x"), "https://x")
        self.assertEqual(safe_url("#sec"), "#sec")
        self.assertIsNone(safe_url("javascript:alert(1)"))
        self.assertIsNone(safe_url("ftp://host/file"))
        self.assertIsNone(safe_url(""))


class TestQuoteAndLists(unittest.TestCase):
    def test_blockquote(self):
        self.assertEqual(parse_blocks("> hello"),
                         "<blockquote>hello</blockquote>")
        self.assertEqual(parse_blocks("> a\n> b"),
                         "<blockquote>a b</blockquote>")

    def test_unordered_list(self):
        self.assertEqual(parse_blocks("- a\n- b"),
                         "<ul><li>a</li><li>b</li></ul>")
        self.assertIn("<ul>", parse_blocks("* a\n* b"))

    def test_ordered_list(self):
        self.assertEqual(parse_blocks("1. a\n2. b"),
                         "<ol><li>a</li><li>b</li></ol>")
        self.assertIn('start="3"', parse_blocks("3. a"))


class TestFence(unittest.TestCase):
    def test_fenced_code(self):
        out = parse_blocks("```python\nx<y\n```")
        self.assertIn('<pre><code class="language-python">', out)
        self.assertIn("x&lt;y", out)

    def test_unclosed_fence_runs_to_end(self):
        out = parse_blocks("```\na\nb")
        self.assertIn("<pre><code>a\nb</code></pre>", out)


class TestFullDocument(unittest.TestCase):
    def test_wrapper(self):
        out = convert("# Hi", full=True, title="T")
        self.assertIn("<!DOCTYPE html>", out)
        self.assertIn("<title>T</title>", out)
        self.assertIn("<h1>Hi</h1>", out)


class TestCli(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "md2html.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
            input=input_text,
        )

    def test_convert_sample(self):
        proc = self.run_cli("convert", str(SAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("<h1>Sample Note</h1>", proc.stdout)
        self.assertIn("<blockquote>", proc.stdout)
        self.assertIn("<img", proc.stdout)

    def test_convert_full(self):
        proc = self.run_cli("convert", str(SAMPLE), "--full",
                            "--title", "Note")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("<!DOCTYPE html>", proc.stdout)

    def test_stdin(self):
        proc = self.run_cli("convert", "-", input_text="# hi\n\n**b**\n")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("<h1>hi</h1>", proc.stdout)

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("<!DOCTYPE html>", proc.stdout)
        self.assertNotIn("<a href=\"javascript", proc.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("convert", "no-such.md")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
