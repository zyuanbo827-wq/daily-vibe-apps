"""minisearch.py -- 零依赖倒排索引与迷你搜索引擎。

文档经分词后建立词项 -> 文档的倒排记录表，记录词频；支持
布尔 AND 查询与 TF-IDF 打分排名查询，可增删文档、JSON 序列化。
CLI 可对目录下 .txt 文件建库检索，也可运行内置演示。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

DEFAULT_STOPWORDS = frozenset()


def tokenize(text: str, stopwords: Sequence[str] = ()) -> List[str]:
    """小写化后按字母/数字串切词，去掉停用词与下划线。"""
    stops = frozenset(stopwords)
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in stops]


class InvertedIndex:
    def __init__(self, stopwords: Sequence[str] = DEFAULT_STOPWORDS):
        self.stopwords = frozenset(stopwords)
        self._docs: Dict[str, str] = {}                 # id -> 原文
        self._tokens: Dict[str, List[str]] = {}         # id -> 分词
        self._postings: Dict[str, Dict[str, int]] = {}  # term -> id -> tf

    # ------------------------------------------------------------------ #
    # 建库
    # ------------------------------------------------------------------ #
    def add(self, doc_id: str, text: str) -> None:
        if doc_id in self._docs:
            self.remove(doc_id)
        self._docs[doc_id] = text
        toks = tokenize(text, self.stopwords)
        self._tokens[doc_id] = toks
        for term, freq in Counter(toks).items():
            self._postings.setdefault(term, {})[doc_id] = freq

    def remove(self, doc_id: str) -> None:
        if doc_id not in self._docs:
            raise KeyError(doc_id)
        for term in set(self._tokens[doc_id]):
            posting = self._postings[term]
            del posting[doc_id]
            if not posting:
                del self._postings[term]
        del self._docs[doc_id]
        del self._tokens[doc_id]

    # ------------------------------------------------------------------ #
    # 统计与打分
    # ------------------------------------------------------------------ #
    @property
    def doc_count(self) -> int:
        return len(self._docs)

    def vocabulary(self) -> List[str]:
        return sorted(self._postings)

    def df(self, term: str) -> int:
        return len(self._postings.get(term, {}))

    def idf(self, term: str) -> float:
        df = self.df(term)
        if df == 0:
            return 0.0
        # 平滑版 idf：log((N + 1) / (df + 1)) + 1，保证为正
        return math.log((self.doc_count + 1) / (df + 1)) + 1.0

    def doc_text(self, doc_id: str) -> str:
        return self._docs[doc_id]

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def _query_terms(self, query: str) -> List[str]:
        return tokenize(query, self.stopwords)

    def search_and(self, query: str) -> List[str]:
        """所有查询词都出现的文档，按 id 升序。"""
        terms = self._query_terms(query)
        if not terms:
            return []
        result: Optional[set] = None
        for term in terms:
            ids = set(self._postings.get(term, {}))
            result = ids if result is None else result & ids
            if not result:
                return []
        return sorted(result)

    def search_rank(self, query: str,
                    top_k: int = 10) -> List[Tuple[str, float]]:
        """TF-IDF 打分：Σ (1+log tf) * idf，分数降序、id 升序破平。"""
        terms = set(self._query_terms(query))
        if not terms:
            return []
        scores: Dict[str, float] = {}
        for term in terms:
            idf = self.idf(term)
            for doc_id, tf in self._postings.get(term, {}).items():
                scores[doc_id] = scores.get(doc_id, 0.0) + \
                    (1.0 + math.log(tf)) * idf
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:top_k]

    # ------------------------------------------------------------------ #
    # 序列化
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {"stopwords": sorted(self.stopwords),
                "docs": dict(self._docs)}

    @classmethod
    def from_dict(cls, data: dict) -> "InvertedIndex":
        idx = cls(stopwords=data.get("stopwords", ()))
        for doc_id, text in sorted(data["docs"].items()):
            idx.add(doc_id, text)
        return idx

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def loads(cls, text: str) -> "InvertedIndex":
        return cls.from_dict(json.loads(text))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
DEMO_DOCS = {
    "d1": "the quick brown fox jumps over the lazy dog",
    "d2": "a fast brown hare leaps across the green field",
    "d3": "search engines build an inverted index from documents",
    "d4": "ranked retrieval uses tf idf term weighting to score documents",
    "d5": "boolean retrieval intersects postings for AND queries",
    "d6": "the fox and the dog rest under the tree after running",
}


def build_demo_index() -> InvertedIndex:
    idx = InvertedIndex(stopwords=("the", "a", "an", "and", "to"))
    for doc_id, text in DEMO_DOCS.items():
        idx.add(doc_id, text)
    return idx


def index_directory(directory: Path) -> InvertedIndex:
    idx = InvertedIndex()
    for path in sorted(directory.glob("*.txt")):
        idx.add(path.stem, path.read_text(encoding="utf-8"))
    if idx.doc_count == 0:
        raise SystemExit(2)
    return idx


def print_rank(ranked: List[Tuple[str, float]], idx: InvertedIndex) -> None:
    if not ranked:
        print("(no matches)")
    for doc_id, score in ranked:
        snippet = idx.doc_text(doc_id)
        if len(snippet) > 60:
            snippet = snippet[:60] + "..."
        print(f"{doc_id:>10}  {score:7.4f}  {snippet}")


def cmd_query(args: argparse.Namespace) -> int:
    idx = index_directory(Path(args.dir))
    if args.mode == "and":
        hits = idx.search_and(args.query)
        if not hits:
            print("(no matches)")
        for doc_id in hits:
            print(doc_id)
    else:
        print_rank(idx.search_rank(args.query, args.top), idx)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    idx = build_demo_index()
    print(f"indexed {idx.doc_count} docs, {len(idx.vocabulary())} terms\n")
    print('boolean AND  query="fox dog":')
    for doc_id in idx.search_and("fox dog"):
        print(f"  {doc_id}: {idx.doc_text(doc_id)}")
    print('\nranked  query="retrieval tf idf documents":')
    print_rank(idx.search_rank("retrieval tf idf documents", top_k=4), idx)
    print('\nrare term outranks common  query="fox":')
    print_rank(idx.search_rank("fox", top_k=3), idx)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="倒排索引迷你搜索引擎（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    pq = sub.add_parser("query", help="对目录下 .txt 文件建库并查询")
    pq.add_argument("query")
    pq.add_argument("--dir", required=True)
    pq.add_argument("--mode", choices=("rank", "and"), default="rank")
    pq.add_argument("--top", type=int, default=10)
    pq.set_defaults(func=cmd_query)

    pd = sub.add_parser("demo")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
