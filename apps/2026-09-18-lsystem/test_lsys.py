"""test_lsys.py -- lsys.py 的单元测试（标准库 unittest）。"""

import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import lsys

APP_DIR = Path(__file__).resolve().parent


class TestRewrite(unittest.TestCase):
    def test_single_rewrite(self):
        self.assertEqual(lsys.rewrite_once("F", {"F": "F-F++F-F"}), "F-F++F-F")

    def test_unknown_char_preserved(self):
        self.assertEqual(lsys.rewrite_once("A", {"B": "C"}), "A")
        self.assertEqual(lsys.rewrite_once("FX", {"X": "X+YF+"}), "FX+YF+")

    def test_iteration_is_parallel(self):
        # 同一轮内新产生的 F 不会被再次替换
        out = lsys.rewrite("F", {"F": "FF"}, 2)
        self.assertEqual(out, "FFFF")

    def test_koch_snowflake_length(self):
        p = lsys.PRESETS["koch-snowflake"]
        self.assertEqual(len(lsys.rewrite(p.axiom, p.rules, 0)), 7)
        # 3 个 F，每个替换为 8 字符，4 个 + 保留
        self.assertEqual(len(lsys.rewrite(p.axiom, p.rules, 1)), 3 * 8 + 4)

    def test_iteration_bounds(self):
        with self.assertRaises(lsys.LSystemError):
            lsys.rewrite("F", {"F": "FF"}, -1)
        with self.assertRaises(lsys.LSystemError):
            lsys.rewrite("F", {"F": "FF"}, lsys.MAX_ITERATIONS + 1)

    def test_brackets_stay_balanced(self):
        p = lsys.PRESETS["plant"]
        for n in range(4):
            s = lsys.rewrite(p.axiom, p.rules, n)
            self.assertEqual(s.count("["), s.count("]"), f"n={n} 括号不平衡")


class TestTurtle(unittest.TestCase):
    def test_forward_east(self):
        paths = lsys.interpret("F", 90.0)
        self.assertEqual(paths, [[(0.0, 0.0), (1.0, 0.0)]])

    def test_heading(self):
        paths = lsys.interpret("F", 90.0, heading=90.0)
        self.assertAlmostEqual(paths[0][-1][0], 0.0)
        self.assertAlmostEqual(paths[0][-1][1], 1.0)

    def test_square_closes(self):
        paths = lsys.interpret("F+F+F+F", 90.0)
        self.assertEqual(lsys.segment_count(paths), 4)
        end = paths[0][-1]
        self.assertAlmostEqual(end[0], 0.0, places=9)
        self.assertAlmostEqual(end[1], 0.0, places=9)

    def test_pen_up_splits_path(self):
        paths = lsys.interpret("FfF", 90.0)
        self.assertEqual(len(paths), 2)
        self.assertEqual(lsys.segment_count(paths), 2)
        # 抬笔那一段没有点：两条子路径之间存在空隙
        self.assertAlmostEqual(paths[0][-1][0], 1.0)
        self.assertAlmostEqual(paths[1][0][0], 2.0)

    def test_branch_stack_restores_state(self):
        # 主干向东，分枝向上后弹栈，继续向东
        paths = lsys.interpret("F[+F]F", 90.0)
        self.assertEqual(lsys.segment_count(paths), 3)
        trunk = [p for p in paths if len(p) == 2 and abs(p[-1][1]) < 1e-9]
        self.assertEqual(len(trunk), 2)  # 分枝前、后的两段主干

    def test_unbalanced_brackets(self):
        with self.assertRaisesRegex(lsys.LSystemError, r"\] 多于 \["):
            lsys.interpret("F]", 90.0)
        with self.assertRaisesRegex(lsys.LSystemError, r"\[ 多于 \]"):
            lsys.interpret("[F", 90.0)

    def test_control_chars_ignored(self):
        # dragon 公理 FX 中 X 不产生线段
        self.assertEqual(lsys.segment_count(lsys.interpret("FX", 90.0)), 1)

    def test_bad_angle_and_step(self):
        with self.assertRaises(lsys.LSystemError):
            lsys.interpret("F", 0.0)
        with self.assertRaises(lsys.LSystemError):
            lsys.interpret("F", 90.0, step=0)


class TestPresets(unittest.TestCase):
    def test_koch_snowflake_segments(self):
        p = lsys.PRESETS["koch-snowflake"]
        self.assertEqual(lsys.segment_count(lsys.generate(p, 0)), 3)
        self.assertEqual(lsys.segment_count(lsys.generate(p, 1)), 12)
        self.assertEqual(lsys.segment_count(lsys.generate(p, 2)), 48)
        # n=0 为闭合正三角形
        paths = lsys.generate(p, 0)
        end = paths[0][-1]
        self.assertAlmostEqual(end[0], 0.0, places=9)
        self.assertAlmostEqual(end[1], 0.0, places=9)

    def test_koch_curve_segments(self):
        p = lsys.PRESETS["koch-curve"]
        self.assertEqual(lsys.segment_count(lsys.generate(p, 0)), 1)
        self.assertEqual(lsys.segment_count(lsys.generate(p, 2)), 25)

    def test_sierpinski_segments(self):
        p = lsys.PRESETS["sierpinski"]
        self.assertEqual(lsys.segment_count(lsys.generate(p, 0)), 3)
        self.assertEqual(lsys.segment_count(lsys.generate(p, 1)), 9)

    def test_dragon_segments(self):
        p = lsys.PRESETS["dragon"]
        for n, expected in [(0, 1), (1, 2), (2, 4), (3, 8), (4, 16)]:
            self.assertEqual(lsys.segment_count(lsys.generate(p, n)), expected, f"n={n}")

    def test_bush_and_plant_generate(self):
        for name in ("bush", "plant"):
            paths = lsys.generate(lsys.PRESETS[name], 3)
            self.assertGreater(lsys.segment_count(paths), 10)
            minx, miny, maxx, maxy = lsys.bounds(paths)
            self.assertLess(minx, maxx)
            self.assertLess(miny, maxy)


class TestRendering(unittest.TestCase):
    def setUp(self):
        self.paths = lsys.generate(lsys.PRESETS["koch-snowflake"], 2)

    def test_svg_structure(self):
        svg = lsys.render_svg(self.paths, width=400, height=300)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("viewBox=\"0 0 400 300\"", svg)
        self.assertIn("<path", svg)
        self.assertTrue(svg.rstrip().endswith("</svg>"))

    def test_svg_coordinates_fit_canvas(self):
        import re
        svg = lsys.render_svg(self.paths, width=400, height=300, padding=20)
        # 直接从 path 数据里取坐标
        coords = [float(v) for pair in re.findall(r"[ML](-?[\d.]+),(-?[\d.]+)", svg)
                  for v in pair]
        xs, ys = coords[0::2], coords[1::2]
        self.assertGreaterEqual(min(xs), 19.9)
        self.assertLessEqual(max(xs), 380.1)
        self.assertGreaterEqual(min(ys), 19.9)
        self.assertLessEqual(max(ys), 280.1)

    def test_ascii_contains_marks(self):
        art = lsys.render_ascii(self.paths, cols=80, rows=30)
        self.assertIn("#", art)
        for line in art.splitlines():
            self.assertLessEqual(len(line), 80)

    def test_empty_paths_raise(self):
        with self.assertRaises(lsys.LSystemError):
            lsys.bounds([])

    def test_bad_canvas_size(self):
        with self.assertRaises(lsys.LSystemError):
            lsys.render_svg(self.paths, width=0, height=10)
        with self.assertRaises(lsys.LSystemError):
            lsys.render_ascii(self.paths, cols=3, rows=3)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_DIR / "lsys.py"), *args],
            capture_output=True, text=True, timeout=60,
        )

    def test_list_presets(self):
        proc = self.run_cli("--list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("dragon", proc.stdout)
        self.assertIn("koch-snowflake", proc.stdout)

    def test_ascii_output(self):
        proc = self.run_cli("dragon", "-n", "4", "--ascii")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("#", proc.stdout)
        self.assertIn("segments=16", proc.stdout)

    def test_custom_rules(self):
        proc = self.run_cli("--axiom", "F", "--rule", "F=F+F-F", "--angle", "90",
                            "-n", "1", "--ascii")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("#", proc.stdout)

    def test_svg_file_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "koch.svg")
            proc = self.run_cli("koch-snowflake", "-n", "3", "--svg", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(os.path.exists(out))
            content = Path(out).read_text(encoding="utf-8")
            self.assertIn("<svg", content)
            self.assertIn("</svg>", content)
            self.assertIn("192 segments", proc.stdout)

    def test_unknown_preset_exit_code(self):
        proc = self.run_cli("nope", "-n", "1")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("未知预设", proc.stderr)

    def test_custom_without_rule_fails(self):
        proc = self.run_cli("--axiom", "F", "-n", "1")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
