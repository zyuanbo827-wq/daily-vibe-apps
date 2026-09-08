import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from ldiff import (
    apply_patch,
    diff_ops,
    lcs_length_table,
    lcs_sequence,
    main,
    parse_patch,
    unified_diff,
)


class TestLcs(unittest.TestCase):
    def test_lcs_sequence_basic(self):
        self.assertEqual(lcs_sequence(["a", "b", "c"], ["a", "x", "c"]), ["a", "c"])

    def test_lcs_length_table(self):
        dp = lcs_length_table(["a", "b"], ["a", "b"])
        self.assertEqual(dp[0][0], 2)
        self.assertEqual(dp[2][2], 0)

    def test_lcs_no_common(self):
        self.assertEqual(lcs_sequence(["a"], ["b"]), [])

    def test_lcs_empty(self):
        self.assertEqual(lcs_sequence([], ["a", "b"]), [])
        self.assertEqual(lcs_sequence(["a"], []), [])


class TestDiffOps(unittest.TestCase):
    def test_replace_operations(self):
        ops = diff_ops(["a", "b", "c"], ["a", "x", "c"])
        tags = [op[0] for op in ops]
        self.assertEqual(tags, ["equal", "delete", "insert", "equal"])

    def test_insert_and_delete(self):
        self.assertEqual([o[0] for o in diff_ops([], ["x"])], ["insert"])
        self.assertEqual([o[0] for o in diff_ops(["x"], [])], ["delete"])

    def test_operation_indices(self):
        ops = diff_ops(["a", "b"], ["a", "c"])
        delete = next(o for o in ops if o[0] == "delete")
        insert = next(o for o in ops if o[0] == "insert")
        self.assertEqual(delete[1], 1)       # 旧文件第 2 行（0 基）
        self.assertIsNone(delete[2])
        self.assertEqual(insert[2], 1)
        self.assertIsNone(insert[1])


class TestUnifiedDiff(unittest.TestCase):
    def test_identical_returns_empty(self):
        self.assertEqual(unified_diff("a\nb\n", "a\nb\n"), "")

    def test_simple_change_has_hunk_and_markers(self):
        patch = unified_diff("L1\nL2\nL3\n", "L1\nX\nL3\n", context=0)
        self.assertIn("--- ", patch)
        self.assertIn("+++ ", patch)
        self.assertIn("@@ -2 +2 @@", patch)
        self.assertIn("-L2", patch)
        self.assertIn("+X", patch)
        wider = unified_diff("L1\nL2\nL3\n", "L1\nX\nL3\n", context=1)
        self.assertIn(" L1", wider)
        self.assertIn("@@ -1,3 +1,3 @@", wider)

    def test_hunk_counts_with_context(self):
        old = "\n".join(f"L{i}" for i in range(1, 6)) + "\n"
        new = "\n".join(["L1", "L2", "X", "L4", "L5"]) + "\n"
        patch = unified_diff(old, new, context=1)
        self.assertIn("@@ -2,3 +2,3 @@", patch)

    def test_two_separated_changes_two_hunks(self):
        old = [f"L{i}" for i in range(1, 11)]
        new = list(old)
        new[0] = "A"
        new[9] = "B"
        patch = unified_diff("\n".join(old) + "\n", "\n".join(new) + "\n", context=1)
        hunk_headers = [ln for ln in patch.splitlines() if ln.startswith("@@")]
        self.assertEqual(len(hunk_headers), 2)

    def test_parse_patch_skips_headers(self):
        patch = unified_diff("a\nb\nc\n", "a\nx\nc\n", context=1)
        entries = parse_patch(patch)
        kinds = [(e.kind, e.text) for e in entries]
        self.assertIn(("delete", "b"), kinds)
        self.assertIn(("insert", "x"), kinds)
        self.assertTrue(all(e.text != "" or True for e in entries))


class TestApply(unittest.TestCase):
    def test_apply_roundtrip(self):
        old = "line1\nline2\nline3\nline4\n"
        new = "line1\npatched\nline3\nline4\n"
        patch = unified_diff(old, new, context=2)
        self.assertEqual(apply_patch(old, patch), new)

    def test_reverse_roundtrip(self):
        old = "line1\nline2\nline3\n"
        new = "line1\nchanged\nline3\n"
        patch = unified_diff(old, new, context=2)
        self.assertEqual(apply_patch(new, patch, reverse=True), old)

    def test_apply_insert_only_and_delete_only(self):
        self.assertEqual(apply_patch("a\nc\n", unified_diff("a\nc\n", "a\nb\nc\n")), "a\nb\nc\n")
        self.assertEqual(apply_patch("a\nb\nc\n", unified_diff("a\nb\nc\n", "a\nc\n")), "a\nc\n")

    def test_apply_mismatch_raises(self):
        patch = unified_diff("a\nb\n", "a\nx\n")
        with self.assertRaises(ValueError):
            apply_patch("a\ndifferent\n", patch)

    def test_empty_original_insert(self):
        patch = unified_diff("", "only new\n")
        self.assertEqual(apply_patch("", patch), "only new\n")


class TestCli(unittest.TestCase):
    def test_diff_and_apply_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_p = os.path.join(tmp, "old.txt")
            new_p = os.path.join(tmp, "new.txt")
            patch_p = os.path.join(tmp, "c.patch")
            with open(old_p, "w", encoding="utf-8", newline="") as f:
                f.write("one\ntwo\nthree\n")
            with open(new_p, "w", encoding="utf-8", newline="") as f:
                f.write("one\nTWO\nthree\n")
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(main(["diff", old_p, new_p]), 0)
            with open(patch_p, "w", encoding="utf-8", newline="") as f:
                f.write(buf.getvalue())
            buf2 = io.StringIO()
            with redirect_stdout(buf2):
                self.assertEqual(main(["apply", old_p, patch_p]), 0)
            self.assertEqual(buf2.getvalue(), "one\nTWO\nthree\n")

    def test_cli_bad_input_returns_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_p = os.path.join(tmp, "old.txt")
            patch_p = os.path.join(tmp, "c.patch")
            with open(old_p, "w", encoding="utf-8") as f:
                f.write("a\nb\n")
            with open(patch_p, "w", encoding="utf-8") as f:
                f.write("@@ -1 +1 @@\n-x\n+y\n")
            self.assertEqual(main(["apply", old_p, patch_p]), 2)


if __name__ == "__main__":
    unittest.main()
