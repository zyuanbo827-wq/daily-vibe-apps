"""文本统计小工具（仅依赖 Python 标准库）。

功能：字符数、词数、句数、阅读时长估算、高频词 Top-N（可去停用词）。

命令行用法：
    python text_stats.py sample.txt
    python text_stats.py sample.txt --top 5 --keep-stopwords
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# 允许词内连字符与撇号，如 state-of-the-art、I'm
WORD_PATTERN = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")
SENTENCE_PATTERN = re.compile(r"[.!?]+")

STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
        "is", "are", "was", "were", "it", "its", "this", "that", "with",
        "as", "at", "by", "from", "be", "we", "you", "i",
    }
)

DEFAULT_WPM = 200  # 成年人平均阅读速度（词/分钟）


def count_words(text: str) -> int:
    return len(WORD_PATTERN.findall(text.lower()))


def count_chars(text: str) -> int:
    return len(text)


def count_sentences(text: str) -> int:
    return len([part for part in SENTENCE_PATTERN.split(text) if part.strip()])


def reading_time_minutes(word_count: int, wpm: int = DEFAULT_WPM) -> int:
    """按平均阅读速度估算分钟数，向上取整，空文本为 0。"""
    if word_count <= 0:
        return 0
    return max(1, math.ceil(word_count / wpm))


def top_words(
    text: str, n: int = 10, drop_stopwords: bool = True
) -> List[Tuple[str, int]]:
    words = WORD_PATTERN.findall(text.lower())
    if drop_stopwords:
        words = [w for w in words if w not in STOPWORDS]
    return Counter(words).most_common(n)


@dataclass
class TextStats:
    chars: int
    words: int
    sentences: int
    reading_minutes: int
    top_words: List[Tuple[str, int]]


def analyze(
    text: str, top_n: int = 10, drop_stopwords: bool = True
) -> TextStats:
    words = count_words(text)
    return TextStats(
        chars=count_chars(text),
        words=words,
        sentences=count_sentences(text),
        reading_minutes=reading_time_minutes(words),
        top_words=top_words(text, top_n, drop_stopwords),
    )


def format_report(stats: TextStats) -> str:
    lines = [
        f"characters   : {stats.chars}",
        f"words        : {stats.words}",
        f"sentences    : {stats.sentences}",
        f"reading time : ~{stats.reading_minutes} min",
        "top words    :",
    ]
    lines.extend(f"  - {word}: {freq}" for word, freq in stats.top_words)
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Text statistics analyzer (Python stdlib only)."
    )
    parser.add_argument("path", help="path to a UTF-8 text file")
    parser.add_argument("--top", type=int, default=10, help="top-N frequent words")
    parser.add_argument(
        "--keep-stopwords", action="store_true", help="do not filter stopwords"
    )
    args = parser.parse_args(argv)

    text = Path(args.path).read_text(encoding="utf-8")
    stats = analyze(text, top_n=args.top, drop_stopwords=not args.keep_stopwords)
    print(format_report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
