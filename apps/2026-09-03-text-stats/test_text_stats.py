import unittest

from text_stats import (
    analyze,
    count_sentences,
    count_words,
    reading_time_minutes,
    top_words,
)


class TestCountWords(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(count_words("Hello, world! Foo-bar."), 3)

    def test_in_word_hyphen_and_apostrophe(self):
        self.assertEqual(count_words("state-of-the-art"), 1)
        self.assertEqual(count_words("I'm ready"), 2)

    def test_empty(self):
        self.assertEqual(count_words("  "), 0)


class TestCountSentences(unittest.TestCase):
    def test_multiple(self):
        self.assertEqual(count_sentences("Hi! How are you? I'm fine."), 3)

    def test_no_punctuation_counts_as_one(self):
        self.assertEqual(count_sentences("just one sentence"), 1)

    def test_empty(self):
        self.assertEqual(count_sentences(""), 0)


class TestReadingTime(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(reading_time_minutes(0), 0)
        self.assertEqual(reading_time_minutes(1), 1)
        self.assertEqual(reading_time_minutes(200), 1)
        self.assertEqual(reading_time_minutes(400), 2)


class TestTopWords(unittest.TestCase):
    def test_stopwords_removed(self):
        text = "The cat and the dog. A cat and a dog. Cat!"
        top = dict(top_words(text, 3))
        self.assertEqual(top["cat"], 3)
        self.assertEqual(top["dog"], 2)
        self.assertNotIn("the", top)
        self.assertNotIn("and", top)

    def test_keep_stopwords(self):
        top = dict(top_words("the the cat", 5, drop_stopwords=False))
        self.assertEqual(top["the"], 2)


class TestAnalyze(unittest.TestCase):
    def test_empty_text(self):
        stats = analyze("")
        self.assertEqual(stats.words, 0)
        self.assertEqual(stats.sentences, 0)
        self.assertEqual(stats.reading_minutes, 0)
        self.assertEqual(stats.top_words, [])

    def test_report_contains_sections(self):
        report = str(analyze("One two. Three four five!"))
        self.assertIn("words", report)


if __name__ == "__main__":
    unittest.main()
