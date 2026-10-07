"""test_fsm_lab.py -- fsm_lab.py 的单元测试（标准库 unittest）。"""

import itertools
import json
import subprocess
import sys
import unittest
from pathlib import Path

from fsm_lab import (DFA, FsmError, NFA, containing_ab_nfa,
                     epsilon_nfa, ending_one_dfa, from_dict)

APP_DIR = Path(__file__).resolve().parent
SAMPLE_DFA = APP_DIR / "sample_dfa.json"
SAMPLE_NFA = APP_DIR / "sample_nfa.json"


class TestDFA(unittest.TestCase):
    def setUp(self):
        self.dfa = ending_one_dfa()

    def test_accept_reject(self):
        self.assertTrue(self.dfa.run("1")[0])
        self.assertTrue(self.dfa.run("01")[0])
        self.assertFalse(self.dfa.run("10")[0])
        self.assertFalse(self.dfa.run("")[0])

    def test_trace(self):
        ok, trace = self.dfa.run("01")
        self.assertEqual(trace, ["q0", "q0", "q1"])

    def test_invalid_symbol(self):
        with self.assertRaises(FsmError):
            self.dfa.run("12")

    def test_missing_transition_is_dead(self):
        d = DFA(["s", "t"], ["a", "b"],
                {"s": {"a": "t"}}, "s", ["t"])
        ok, trace = d.run("b")
        self.assertFalse(ok)
        self.assertIn("(dead)", trace)

    def test_validation(self):
        with self.assertRaises(FsmError):
            DFA(["s"], ["a"], {}, "x", [])


class TestNFA(unittest.TestCase):
    def setUp(self):
        self.nfa = containing_ab_nfa()

    def test_accepts(self):
        for s in ("ab", "aab", "aba", "baba"):
            self.assertTrue(self.nfa.accepts(s), s)
        for s in ("ba", "bbb", "aaa", ""):
            self.assertFalse(self.nfa.accepts(s), s)

    def test_invalid_symbol(self):
        with self.assertRaises(FsmError):
            self.nfa.accepts("ac")

    def test_epsilon_closure(self):
        enfa = epsilon_nfa()
        self.assertEqual(enfa.epsilon_closure({"s"}), {"s", "b"})

    def test_epsilon_language(self):
        enfa = epsilon_nfa()
        self.assertTrue(enfa.accepts("1"))
        self.assertTrue(enfa.accepts("10"))
        self.assertFalse(enfa.accepts("01"))
        self.assertFalse(enfa.accepts("11"))


class TestDeterminize(unittest.TestCase):
    def test_state_count(self):
        det = containing_ab_nfa().determinize()
        self.assertEqual(len(det.states), 4)

    def test_equivalence_exhaustive(self):
        nfa = containing_ab_nfa()
        det = nfa.determinize()
        for length in range(5):
            for chars in itertools.product("ab", repeat=length):
                s = "".join(chars)
                self.assertEqual(nfa.accepts(s), det.run(s)[0], s)

    def test_epsilon_determinize(self):
        nfa = epsilon_nfa()
        det = nfa.determinize()
        for s in ("1", "10", "01", "11", ""):
            self.assertEqual(nfa.accepts(s), det.run(s)[0], s)


class TestJson(unittest.TestCase):
    def test_load_samples(self):
        dfa = from_dict(json.loads(SAMPLE_DFA.read_text(encoding="utf-8")))
        self.assertIsInstance(dfa, DFA)
        nfa = from_dict(json.loads(SAMPLE_NFA.read_text(encoding="utf-8")))
        self.assertIsInstance(nfa, NFA)

    def test_bad_type(self):
        with self.assertRaises(FsmError):
            from_dict({"type": "turing"})


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "fsm_lab.py"), *args],
            capture_output=True, text=True, timeout=60, cwd=APP_DIR,
        )

    def test_demo(self):
        proc = self.run_cli("demo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("AGREE", proc.stdout)

    def test_run_dfa(self):
        ok = self.run_cli("run", str(SAMPLE_DFA), "01")
        self.assertEqual(ok.returncode, 0)
        self.assertIn("accept", ok.stdout)
        no = self.run_cli("run", str(SAMPLE_DFA), "10")
        self.assertEqual(no.returncode, 1)
        self.assertIn("reject", no.stdout)

    def test_run_nfa(self):
        proc = self.run_cli("run", str(SAMPLE_NFA), "aab")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("accept", proc.stdout)

    def test_convert(self):
        proc = self.run_cli("convert", str(SAMPLE_NFA))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["type"], "dfa")
        self.assertEqual(len(data["states"]), 4)

    def test_missing_file_exit_two(self):
        proc = self.run_cli("run", "no.json", "x")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
