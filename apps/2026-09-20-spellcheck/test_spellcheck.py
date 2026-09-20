"""test_spellcheck.py -- spellcheck.py 的单元测试（标准库 unittest）。"""

import random
import subprocess
import sys
import unittest
from pathlib import Path

import spellcheck
from spellcheck import BKTree, Finding, SpellChecker, SpellError, levenshtein

APP_DIR = Path(__file__).resolve().parent
DICT = APP_DIR / "words_en.txt"


class TestLevenshtein(unittest.TestCase):
    def test_classic_examples(self):
        self.assertEqual(levenshtein("kitten", "sitting"), 3)
        self.assertEqual(levenshtein("saturday", "sunday"), 3)
        self.assertEqual(levenshtein("", "abc"), 3)
        self.assertEqual(levenshtein("abc", ""), 3)
        self.assertEqual(levenshtein("", ""), 0)

    def test_identity_and_single_edits(self):
        self.assertEqual(levenshtein("word", "word"), 0)
        self.assertEqual(levenshtein("word", "words"), 1)  # 插入
        self.assertEqual(levenshtein("word", "wod"), 1)    # 删除
        self.assertEqual(levenshtein("word", "w0rd"), 1)   # 替换

    def test_symmetric_and_triangle(self):
        for a, b in [("apple", "apply"), ("night", "nacht"), ("hello", "hallo")]:
            self.assertEqual(levenshtein(a, b), levenshtein(b, a))
        # 三角不等式
        x, y, z = "cat", "car", "bar"
        self.assertLessEqual(levenshtein(x, z),
                             levenshtein(x, y) + levenshtein(y, z))

    def test_unicode_code_points(self):
        self.assertEqual(levenshtein("测试", "测验"), 1)


class TestBKTree(unittest.TestCase):
    def test_build_and_membership(self):
        tree = BKTree(["apple", "apply", "orange"])
        self.assertEqual(len(tree), 3)
        self.assertIn("apple", tree)
        self.assertIn("APPLE", tree)  # 小写归一
        self.assertNotIn("banana", tree)

    def test_duplicates_ignored(self):
        tree = BKTree(["one", "one", "One"])
        self.assertEqual(len(tree), 1)

    def test_empty_word_and_tree(self):
        tree = BKTree()
        self.assertEqual(tree.query("anything", 2), [])
        with self.assertRaises(SpellError):
            tree.add("")
        with self.assertRaises(SpellError):
            tree.query("x", -1)

    def test_query_radius_zero(self):
        tree = BKTree(["spell", "shell", "spill"])
        self.assertEqual(tree.query("spell", 0), [("spell", 0)])

    def test_results_sorted(self):
        tree = BKTree(["spell", "spill", "shell", "spellcheck"])
        hits = tree.query("spell", 2)
        dists = [d for _, d in hits]
        self.assertEqual(dists, sorted(dists))

    def test_matches_brute_force(self):
        rng = random.Random(123)
        words = sorted({
            "".join(rng.choice("abcde") for _ in range(rng.randint(3, 7)))
            for _ in range(400)
        })
        tree = BKTree(words)
        self.assertEqual(len(tree), len(words))
        for radius in (1, 2):
            for _ in range(100):
                q = "".join(rng.choice("abcde") for _ in range(rng.randint(3, 7)))
                expected = sorted(
                    (w, d) for w in words
                    if (d := levenshtein(q, w)) <= radius
                )
                got = tree.query(q, radius)
                self.assertEqual(got, sorted(expected, key=lambda p: (p[1], p[0])))


class TestSpellChecker(unittest.TestCase):
    def setUp(self):
        self.checker = SpellChecker.from_file(str(DICT))

    def test_dictionary_loaded(self):
        self.assertGreater(len(self.checker), 200)

    def test_exact_word_case_insensitive(self):
        self.assertTrue(self.checker.is_word("The"))
        self.assertTrue(self.checker.is_word("because"))
        self.assertFalse(self.checker.is_word("becuase"))

    def test_suggestions(self):
        self.assertEqual(self.checker.suggest("speling", max_dist=2, limit=1),
                         ["spelling"])
        suggestions = self.checker.suggest("somethng", max_dist=2)
        self.assertIn("something", suggestions)
        self.assertEqual(self.checker.suggest("beutiful", max_dist=2, limit=1),
                         ["beautiful"])

    def test_no_suggestions_for_gibberish(self):
        self.assertEqual(self.checker.suggest("zzzzqqxx", max_dist=1), [])

    def test_check_text_clean(self):
        # 全部为词典内单词的句子
        findings = self.checker.check_text("a good morning to you")
        self.assertEqual(findings, [])

    def test_check_text_finds_typos_and_positions(self):
        findings = self.checker.check_text("this is a beutiful dayy")
        wrong = [f.word for f in findings]
        self.assertIn("beutiful", wrong)
        self.assertIn("dayy", wrong)
        dayy = next(f for f in findings if f.word == "dayy")
        self.assertEqual("this is a beutiful dayy"[dayy.start:dayy.end], "dayy")
        self.assertIn("day", dayy.suggestions)
        # 正确词不应被报出
        self.assertNotIn("this", wrong)

    def test_apostrophe_tokenized(self):
        # 词典没有 don't，应作为一个 token 报出
        findings = self.checker.check_text("dont go")
        self.assertEqual([f.word for f in findings], ["dont"])


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "spellcheck.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_suggest_hit(self):
        proc = self.run_cli("suggest", str(DICT), "speling", "--max-dist", "2")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("spelling", proc.stdout)

    def test_suggest_miss_exit_one(self):
        proc = self.run_cli("suggest", str(DICT), "zzqqxx", "--max-dist", "1")
        self.assertEqual(proc.returncode, 1)

    def test_check_clean_and_typo(self):
        ok = self.run_cli("check", str(DICT), "good morning")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("未发现拼写问题", ok.stdout)

        bad = self.run_cli("check", str(DICT), "a beutiful morning")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("beutiful", bad.stdout)
        self.assertIn("beautiful", bad.stdout)

    def test_missing_dict_exit_two(self):
        proc = self.run_cli("suggest", "no-such-dict.txt", "word")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
