"""markov-text：零依赖的马尔可夫链文本生成器（仅 Python 标准库）。

- 从训练文本切句、分词，构建 1 阶或 2 阶词级马尔可夫链；
- 用注入的 random.Random 生成，同种子同文本必得同结果；
- 支持句首/句尾哨兵、最大词数保护、可选小写归一化。

命令行：
    python markov.py sample.txt --seed 7 --sentences 5 --order 2
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

START = "^"   # 句首哨兵
END = "$"     # 句尾哨兵
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENT_RE = re.compile(r"[^.!?]+[.!?]?")

Chain = Dict[Tuple[str, ...], List[str]]


def split_sentences(text: str) -> List[List[str]]:
    """把整段文本切成句子，每句是一个词列表（忽略标点本身）。"""
    sentences: List[List[str]] = []
    for raw in _SENT_RE.findall(text):
        words = _WORD_RE.findall(raw)
        if words:
            sentences.append(words)
    return sentences


def normalize(sentences: Sequence[List[str]], lower: bool = False) -> List[List[str]]:
    if not lower:
        return [list(s) for s in sentences]
    return [[w.lower() for w in s] for s in sentences]


def build_chain(sentences: Sequence[List[str]], order: int = 1) -> Chain:
    """由句子列表构建状态 -> 候选后继词（保留重复以体现频次）。"""
    if order < 1:
        raise ValueError("order must be >= 1")
    chain: Chain = defaultdict(list)
    start_state = (START,) * order
    for words in sentences:
        state = start_state
        for word in words:
            chain[state].append(word)
            state = tuple((state + (word,))[-order:])
        chain[state].append(END)
    return dict(chain)


def train(text: str, order: int = 1, lower: bool = False) -> Chain:
    return build_chain(normalize(split_sentences(text), lower=lower), order=order)


def generate_sentence(chain: Chain, rng: random.Random, order: int = 1,
                      max_words: int = 30) -> List[str]:
    """从句首状态随机游走至句尾哨兵；超过 max_words 也会安全停止。"""
    if order < 1:
        raise ValueError("order must be >= 1")
    state = (START,) * order
    out: List[str] = []
    for _ in range(max_words):
        choices = chain.get(state)
        if not choices:
            break
        nxt = rng.choice(choices)
        if nxt == END:
            return out
        out.append(nxt)
        state = tuple((state + (nxt,))[-order:])
    return out


def generate_text(chain: Chain, rng: random.Random, sentences: int = 1,
                  order: int = 1, max_words: int = 30) -> str:
    lines = []
    for _ in range(sentences):
        words = generate_sentence(chain, rng, order=order, max_words=max_words)
        if words:
            lines.append(" ".join(words))
    return "\n".join(lines)


def vocabulary(chain: Chain) -> List[str]:
    vocab = {w for choices in chain.values() for w in choices if w not in (START, END)}
    return sorted(vocab)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zero-dependency Markov-chain text generator (stdlib only)."
    )
    parser.add_argument("source", help="training text file")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--sentences", type=int, default=3)
    parser.add_argument("--order", type=int, default=1, choices=(1, 2))
    parser.add_argument("--max-words", type=int, default=30)
    parser.add_argument("--lower", action="store_true", help="normalize to lowercase")
    args = parser.parse_args(argv)

    try:
        with open(args.source, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    chain = train(text, order=args.order, lower=args.lower)
    if not chain:
        print("error: no usable sentences found in source", file=sys.stderr)
        return 2
    rng = random.Random(args.seed)
    sys.stdout.write(generate_text(
        chain, rng, sentences=args.sentences, order=args.order, max_words=args.max_words
    ) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
