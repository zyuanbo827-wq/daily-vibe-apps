import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from tasksched import (
    CycleError,
    UnknownDependencyError,
    levels,
    normalize,
    schedule,
    topo_sort,
    main,
)


def chain_graph():
    return {
        "A": {"deps": [], "duration": 3},
        "B": {"deps": ["A"], "duration": 2},
        "C": {"deps": ["B"], "duration": 4},
    }


def diamond_graph():
    return {
        "A": {"deps": [], "duration": 1},
        "B": {"deps": ["A"], "duration": 3},
        "C": {"deps": ["A"], "duration": 5},
        "D": {"deps": ["B", "C"], "duration": 1},
    }


class TestNormalize(unittest.TestCase):
    def test_unknown_dependency_raises(self):
        with self.assertRaises(UnknownDependencyError):
            normalize({"B": {"deps": ["missing"]}})

    def test_negative_duration_raises(self):
        with self.assertRaises(ValueError):
            normalize({"A": {"deps": [], "duration": -1}})

    def test_default_duration_is_one(self):
        self.assertEqual(normalize({"A": {}})["A"], ([], 1))


class TestTopoSort(unittest.TestCase):
    def test_chain_order(self):
        self.assertEqual(topo_sort(chain_graph()), ["A", "B", "C"])

    def test_diamond_respects_deps_and_tie(self):
        order = topo_sort(diamond_graph())
        self.assertEqual(order, ["A", "B", "C", "D"])
        self.assertLess(order.index("A"), order.index("B"))
        self.assertLess(order.index("C"), order.index("D"))

    def test_deterministic_regardless_of_insertion(self):
        g1 = {"A": {"deps": []}, "B": {"deps": []}, "C": {"deps": ["A", "B"]}}
        g2 = {"C": {"deps": ["B", "A"]}, "B": {"deps": []}, "A": {"deps": []}}
        self.assertEqual(topo_sort(g1), topo_sort(g2))
        self.assertEqual(topo_sort(g1), ["A", "B", "C"])

    def test_empty_graph(self):
        self.assertEqual(topo_sort({}), [])

    def test_self_loop_is_cycle(self):
        with self.assertRaises(CycleError):
            topo_sort({"X": {"deps": ["X"]}})

    def test_two_node_cycle_raises(self):
        g = {"A": {"deps": ["B"]}, "B": {"deps": ["A"]}}
        with self.assertRaises(CycleError):
            topo_sort(g)


class TestLevels(unittest.TestCase):
    def test_chain_levels(self):
        self.assertEqual(levels(chain_graph()), [["A"], ["B"], ["C"]])

    def test_diamond_levels(self):
        self.assertEqual(levels(diamond_graph()), [["A"], ["B", "C"], ["D"]])

    def test_independent_tasks_one_level(self):
        g = {"Z": {"deps": []}, "A": {"deps": []}, "M": {"deps": []}}
        self.assertEqual(levels(g), [["A", "M", "Z"]])


class TestSchedule(unittest.TestCase):
    def test_chain_cumulative_times(self):
        s = schedule(chain_graph())
        self.assertEqual((s.items["A"].start, s.items["A"].finish), (0, 3))
        self.assertEqual((s.items["B"].start, s.items["B"].finish), (3, 5))
        self.assertEqual((s.items["C"].start, s.items["C"].finish), (5, 9))
        self.assertEqual(s.total_duration, 9)
        self.assertEqual(s.critical_path, ["A", "B", "C"])

    def test_diamond_starts_at_max_pred_finish(self):
        s = schedule(diamond_graph())
        self.assertEqual(s.items["D"].start, 6)
        self.assertEqual(s.items["D"].finish, 7)
        self.assertEqual(s.total_duration, 7)
        # 更长的 C 分支决定工期，是关键路径
        self.assertEqual(s.critical_path, ["A", "C", "D"])

    def test_single_node(self):
        s = schedule({"S": {"deps": [], "duration": 5}})
        self.assertEqual(s.total_duration, 5)
        self.assertEqual(s.critical_path, ["S"])

    def test_empty_schedule(self):
        s = schedule({})
        self.assertEqual(s.total_duration, 0)
        self.assertEqual(s.critical_path, [])

    def test_ordered_view_sorted_by_start(self):
        s = schedule(diamond_graph())
        names = [it.name for it in s.ordered()]
        self.assertEqual(names[0], "A")
        self.assertEqual(names[-1], "D")


class TestCli(unittest.TestCase):
    def _write(self, obj):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(obj, tmp)
        tmp.close()
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
        return tmp.name

    def test_order_command(self):
        path = self._write(diamond_graph())
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["order", path])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().splitlines(), ["A", "B", "C", "D"])

    def test_schedule_command_reports_critical_path(self):
        path = self._write(diamond_graph())
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["schedule", path])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("total duration: 7", out)
        self.assertIn("critical path: A -> C -> D", out)

    def test_cycle_file_returns_2(self):
        path = self._write({"A": {"deps": ["B"]}, "B": {"deps": ["A"]}})
        self.assertEqual(main(["order", path]), 2)

    def test_missing_file_returns_2(self):
        self.assertEqual(main(["order", "does-not-exist.json"]), 2)


if __name__ == "__main__":
    unittest.main()
