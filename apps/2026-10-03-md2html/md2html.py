"""md2html.py -- 零依赖 Markdown -> HTML 转换器。

支持常见块级语法（ATX 标题、围栏代码块、引用、无序/有序列表、
分割线、段落）与行内语法（行内代码、粗体、斜体、链接、图片），
默认输出 HTML 片段，--full 输出完整文档；对原始 HTML 做转义，
并拦截 javascript: 等危险 URL。
"""

from __future__ import annotations

import argparse
import html as html_mod
import re
import sys
from typing import List, Optional


class MarkdownError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# 行内转换
# --------------------------------------------------------------------------- #
SAFE_SCHEMES = ("http://", "https://", "mailto:", "#", "/", "./", "../")
CODE_PLACEHOLDER = "\x00CODE%d\x00"


def safe_url(url: str) -> Optional[str]:
    """允许 http(s)/mailto/锚点/相对路径；拒绝带冒号的其他 scheme。"""
    u = url.strip()
    if not u:
        return None
    lowered = u.lower()
    if lowered.startswith(SAFE_SCHEMES):
        return u
    # 相对路径中若出现 scheme（形如 xxx:）则拒绝
    if re.match(r"^[a-z][a-z0-9+.\-]*:", lowered):
        return None
    return u


def inline(text: str) -> str:
    # 1) 先抽取行内代码（内容直接转义，不做其他行内解析）
    codes: List[str] = []

    def take_code(match: re.Match) -> str:
        codes.append(html_mod.escape(match.group(1)))
        return CODE_PLACEHOLDER % (len(codes) - 1)

    text = re.sub(r"`([^`]+)`", take_code, text)

    # 2) 转义原始 HTML
    text = html_mod.escape(text)

    # 3) 图片（须在链接之前处理）
    def image(match: re.Match) -> str:
        alt, url = match.group(1), match.group(2)
        checked = safe_url(url)
        if checked is None:
            return html_mod.escape(match.group(0))
        return f'<img src="{html_mod.escape(checked, quote=True)}" alt="{alt}">'

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", image, text)

    # 4) 链接
    def link(match: re.Match) -> str:
        label, url = match.group(1), match.group(2)
        checked = safe_url(url)
        if checked is None:
            return html_mod.escape(match.group(0))
        return (f'<a href="{html_mod.escape(checked, quote=True)}">'
                f"{label}</a>")

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)

    # 5) 粗体 / 斜体
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"(?<![A-Za-z0-9])_([^_]+)_(?![A-Za-z0-9])",
                  r"<em>\1</em>", text)

    # 6) 还原行内代码
    for i, code in enumerate(codes):
        text = text.replace(CODE_PLACEHOLDER % i, f"<code>{code}</code>")
    return text


# --------------------------------------------------------------------------- #
# 块级解析
# --------------------------------------------------------------------------- #
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
HR_RE = re.compile(r"^\s*([-*_])\s*(?:\1\s*){2,}$")
UL_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
OL_RE = re.compile(r"^\s*(\d+)\.\s+(.*)$")
QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
FENCE_RE = re.compile(r"^\s*```\s*([\w-]*)\s*$")


def parse_blocks(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # 空行
        if not line.strip():
            i += 1
            continue

        # 围栏代码块
        fence = FENCE_RE.match(line)
        if fence:
            lang = fence.group(1)
            i += 1
            buf: List[str] = []
            while i < n and not FENCE_RE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            if i < n:                          # 消费闭合围栏
                i += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html_mod.escape(chr(10).join(buf))}"
                       f"</code></pre>")
            continue

        # 标题
        h = HEADING_RE.match(line)
        if h:
            level = len(h.group(1))
            out.append(f"<h{level}>{inline(h.group(2))}</h{level}>")
            i += 1
            continue

        # 分割线
        if HR_RE.match(line):
            out.append("<hr>")
            i += 1
            continue

        # 引用
        if QUOTE_RE.match(line):
            buf = []
            while i < n and QUOTE_RE.match(lines[i]):
                buf.append(QUOTE_RE.match(lines[i]).group(1))
                i += 1
            out.append("<blockquote>" + inline(" ".join(buf)) + "</blockquote>")
            continue

        # 无序列表
        if UL_RE.match(line):
            items = []
            while i < n and UL_RE.match(lines[i]):
                items.append(UL_RE.match(lines[i]).group(1))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>"
                                        for x in items) + "</ul>")
            continue

        # 有序列表
        if OL_RE.match(line):
            start = int(OL_RE.match(line).group(1))
            items = []
            while i < n and OL_RE.match(lines[i]):
                items.append(OL_RE.match(lines[i]).group(2))
                i += 1
            attr = f' start="{start}"' if start != 1 else ""
            out.append("<ol" + attr + ">" +
                       "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue

        # 段落：收集连续非空、非块级起始行
        buf = []
        while i < n and lines[i].strip() and not _starts_block(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")

    return "\n".join(out)


def _starts_block(line: str) -> bool:
    return bool(HEADING_RE.match(line) or HR_RE.match(line)
                or UL_RE.match(line) or OL_RE.match(line)
                or QUOTE_RE.match(line) or FENCE_RE.match(line))


def convert(markdown: str, full: bool = False, title: str = "") -> str:
    body = parse_blocks(markdown)
    if not full:
        return body
    title_html = html_mod.escape(title or "Document")
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{title_html}</title>\n</head>\n<body>\n{body}\n</body>\n</html>")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
DEMO_MD = """# md2html demo

A **zero-dependency** Markdown converter with *inline* formatting.

- inline `code` spans
- safe [links](https://example.com)
- blocked `[bad](javascript:alert(1))` URLs

> Quotes and fenced code are supported.

```python
print("hello")
```

1. first
2. second
"""


def read_source(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise SystemExit(2)


def cmd_convert(args: argparse.Namespace) -> int:
    source = read_source(args.file)
    print(convert(source, full=args.full, title=args.title))
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    print(convert(DEMO_MD, full=True, title="md2html demo"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Markdown -> HTML（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("convert", help="转换 Markdown 文件")
    pc.add_argument("file", help="Markdown 文件，- 为标准输入")
    pc.add_argument("--full", action="store_true", help="输出完整 HTML 文档")
    pc.add_argument("--title", default="")
    pc.set_defaults(func=cmd_convert)

    pd = sub.add_parser("demo", help="内置样例完整文档")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
