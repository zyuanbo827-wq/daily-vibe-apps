"""test_merkle_tree.py -- merkle_tree.py 的单元测试（标准库 unittest）。"""

import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from merkle_tree import (MerkleTree, file_blocks, leaf_hash, node_hash,
                         verify_proof)

APP_DIR = Path(__file__).resolve().parent
SAMPLE = APP_DIR / "sample_ledger.txt"


class TestTree(unittest.TestCase):
    def setUp(self):
        self.items = [f"tx-{i}".encode() for i in range(5)]
        self.tree = MerkleTree(self.items)

    def test_deterministic_root(self):
        self.assertEqual(MerkleTree(self.items).root, self.tree.root)

    def test_root_changes_with_data(self):
        changed = self.items.copy()
        changed[2] = b"tx-X"
        self.assertNotEqual(MerkleTree(changed).root, self.tree.root)

    def test_single_leaf(self):
        t = MerkleTree([b"only"])
        self.assertEqual(t.root, leaf_hash(b"only"))
        self.assertEqual(len(t.levels), 1)

    def test_odd_size_duplicates_last(self):
        a, b, c = (leaf_hash(x) for x in (b"a", b"b", b"c"))
        expected = node_hash(node_hash(a, b), node_hash(c, c))
        self.assertEqual(MerkleTree([b"a", b"b", b"c"]).root, expected)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            MerkleTree([])

    def test_proof_length(self):
        for n in (1, 2, 3, 4, 5, 8):
            t = MerkleTree([str(i).encode() for i in range(n)])
            expected = 0 if n == 1 else math.ceil(math.log2(n))
            self.assertEqual(len(t.proof(0)), expected)

    def test_index_bounds(self):
        with self.assertRaises(IndexError):
            self.tree.proof(99)


class TestProofs(unittest.TestCase):
    def test_all_leaves_verify(self):
        for n in (1, 2, 3, 5, 8):
            items = [f"item-{i}".encode() for i in range(n)]
            t = MerkleTree(items)
            for i, data in enumerate(items):
                self.assertTrue(
                    verify_proof(data, t.proof(i), t.root_hex), (n, i))

    def test_tampered_leaf_fails(self):
        items = [b"a", b"b", b"c", b"d"]
        t = MerkleTree(items)
        self.assertFalse(verify_proof(b"tampered", t.proof(0), t.root_hex))

    def test_wrong_position_fails(self):
        items = [b"a", b"b", b"c", b"d"]
        t = MerkleTree(items)
        self.assertFalse(verify_proof(items[0], t.proof(1), t.root_hex))

    def test_foreign_leaf_fails(self):
        t = MerkleTree([b"a", b"b"])
        self.assertFalse(verify_proof(b"zzz", t.proof(0), t.root_hex))


class TestFileBlocks(unittest.TestCase):
    def test_blocking_roundtrip(self):
        data = SAMPLE.read_bytes()
        blocks = file_blocks(str(SAMPLE), 40)
        self.assertTrue(len(blocks) > 1)
        self.assertEqual(b"".join(blocks), data)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        self.assertEqual(file_blocks(path, 16), [b""])

    def test_bad_block_size(self):
        with self.assertRaises(ValueError):
            file_blocks(str(SAMPLE), 0)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "merkle_tree.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("detected", proc.stdout)

    def test_root_and_verify(self):
        root_proc = self.run_cli("root", str(SAMPLE), "--block", "40")
        self.assertEqual(root_proc.returncode, 0, root_proc.stderr)
        root = root_proc.stdout.strip()
        self.assertEqual(len(root), 64)

        ok = self.run_cli("verify", str(SAMPLE), root, "--block", "40")
        self.assertEqual(ok.returncode, 0)
        self.assertIn("OK", ok.stdout)

        bad = self.run_cli("verify", str(SAMPLE), "0" * 64,
                           "--block", "40")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("MISMATCH", bad.stdout)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("root", "no.bin")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
