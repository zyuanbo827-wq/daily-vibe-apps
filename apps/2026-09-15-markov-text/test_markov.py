import io
import os
import random
import tempfile
import unittest
from contextlib import redirect_stdout

from markov import (
    END,
    START,
    build_chain,
    generate_sentence,
    generate_text,
    normalize,
    split_sentences,
    train,
    vocabulary,
    main,
)


class TestTokenize(unittest.TestCase):
    def test_split_sentences_on_punctuation(self):
        sents = split_sentences("Hello world. How are you! Really?")
        self.assertEqual(sents, [
            ["Hello", "world"],
            ["How", "are", "you"],
            ["Really"],
        ])

    def test_ignore_punctuation_tokens(self):
        self.assertEqual(split_sentences("a, b; c: d."), [["a", "b", "c", "d"]])

    def test_no_words(self):
        self.assertEqual(split_sentences("... !!!"), [])

    def test_normalize_lower(self):
        sents = split_sentences("Hello World.")
        self.assertEqual(normalize(sents, lower=True), [["hello", "world"]])
        self.assertEqual(normalize(sents, lower=False), [["Hello", "World"]])


class TestChain(unittest.TestCase):
    def test_order1_transitions_with_frequency(self):
        chain = build_chain([["a", "b"], ["a", "c"]], order=1)
        self.assertEqual(chain[(START,)], ["a", "a"])
        self.assertEqual(chain[("a",)], ["b", "c"])
        self.assertEqual(chain[("b",)], [END])

    def test_order2_states(self):
        chain = build_chain([["the", "cat", "sat"]], order=2)
        self.assertEqual(chain[(START, START)], ["the"])
        self.assertEqual(chain[(START, "the")], ["cat"])
        self.assertEqual(chain[("the", "cat")], ["sat"])
        self.assertEqual(chain[("cat", "sat")], [END])

    def test_invalid_order_raises(self):
        with self.assertRaises(ValueError):
            build_chain([["a"]], order=0)

    def test_vocabulary_excludes_sentinels(self):
        chain = train("a b c.")
        self.assertEqual(vocabulary(chain), ["a", "b", "c"])


class TestGenerate(unittest.TestCase):
    def test_linear_chain_reproduces_sentence(self):
        chain = build_chain([["the", "cat", "sat"]], order=1)
        out = generate_sentence(chain, random.Random(0))
        self.assertEqual(out, ["the", "cat", "sat"])

    def test_seed_is_deterministic(self):
        text = "the quick brown fox jumps. the quick red fox runs. the slow brown fox rests."
        chain = train(text, order=2)
        a = generate_text(chain, random.Random(42), sentences=4, order=2)
        b = generate_text(chain, random.Random(42), sentences=4, order=2)
        self.assertEqual(a, b)
        self.assertTrue(a)

    def test_generated_words_in_vocabulary(self):
        chain = train("alpha beta gamma. alpha gamma beta. beta alpha gamma.")
        vocab = set(vocabulary(chain))
        for _ in range(20):
            words = generate_sentence(chain, random.Random(_), order=1)
            self.assertTrue(set(words) <= vocab)

    def test_max_words_caps_chain_without_end(self):
        # 构造一个永远到不了 END 的自循环链
        chain = {(START,): ["x"], ("x",): ["x"]}
        out = generate_sentence(chain, random.Random(0), order=1, max_words=7)
        self.assertEqual(out, ["x"] * 7)

    def test_empty_chain(self):
        self.assertEqual(generate_sentence({}, random.Random(0)), [])
        self.assertEqual(generate_text({}, random.Random(0)), "")

    def test_generate_text_line_count(self):
        chain = train("one two three. one three two.")
        text = generate_text(chain, random.Random(1), sentences=3)
        self.assertEqual(len([ln for ln in text.splitlines() if ln]), 3)


class TestCli(unittest.TestCase):
    def _write(self, text):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write(text)
        tmp.close()
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
        return tmp.name

    CORPUS = ("the river flows east. the wind blows north. "
              "the river meets the sea. the wind carries rain.")

    def test_cli_generates_requested_sentences(self):
        path = self._write(self.CORPUS)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main([path, "--seed", "3", "--sentences", "3", "--order", "2"])
        self.assertEqual(rc, 0)
        lines = [ln for ln in buf.getvalue().splitlines() if ln]
        self.assertEqual(len(lines), 3)

    def test_cli_empty_source_returns_2(self):
        path = self._write("... !!!")
        self.assertEqual(main([path]), 2)

    def test_cli_missing_file_returns_2(self):
        self.assertEqual(main(["no-such-file.txt"]), 2)


if __name__ == "__main__":
    unittest.main()
