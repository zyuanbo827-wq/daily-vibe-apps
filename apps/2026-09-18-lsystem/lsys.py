"""lsys.py -- 零依赖 L-system（ Lindenmayer 系统 ）分形生成器。

两阶段流水线：
  1. rewrite：按产生式规则对公理字符串做 N 次并行重写；
  2. interpret：用海龟绘图把指令串解释为二维路径（支持 + - 转向、
     [ ] 分支栈、f 抬笔移动），再渲染成 SVG 或 ASCII。

内置科赫雪花、谢尔宾斯基三角形、龙形曲线、分形灌木与植物等预设，
也可通过库 API / CLI 参数传入自定义规则。仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Path = List[Point]

MAX_ITERATIONS = 12


class LSystemError(ValueError):
    """参数或规则错误。"""


@dataclass(frozen=True)
class Preset:
    name: str
    axiom: str
    rules: Dict[str, str]
    angle: float
    heading: float = 0.0
    description: str = ""


PRESETS: Dict[str, Preset] = {
    "koch-snowflake": Preset(
        "koch-snowflake",
        "F++F++F",
        {"F": "F-F++F-F"},
        60.0,
        0.0,
        "科赫雪花（三次科赫曲线围成正三角形）",
    ),
    "koch-curve": Preset(
        "koch-curve",
        "F",
        {"F": "F+F-F-F+F"},
        90.0,
        0.0,
        "90 度科赫曲线（方波雪花边）",
    ),
    "sierpinski": Preset(
        "sierpinski",
        "F-G-G",
        {"F": "F-G+F+G-F", "G": "GG"},
        120.0,
        0.0,
        "谢尔宾斯基三角形（F、G 均前进）",
    ),
    "dragon": Preset(
        "dragon",
        "FX",
        {"X": "X+YF+", "Y": "-FX-Y"},
        90.0,
        0.0,
        "Heighway 龙形曲线（X/Y 为控制符号）",
    ),
    "bush": Preset(
        "bush",
        "F",
        {"F": "FF+[+F-F-F]-[-F+F+F]"},
        22.5,
        90.0,
        "随机感分形灌木（确定性规则）",
    ),
    "plant": Preset(
        "plant",
        "X",
        {"X": "F+[[X]-X]-F[-FX]+X", "F": "FF"},
        25.0,
        90.0,
        "带叶片分枝的分形植物",
    ),
}


# --------------------------------------------------------------------------- #
# 1. 字符串重写
# --------------------------------------------------------------------------- #
def rewrite_once(axiom: str, rules: Dict[str, str]) -> str:
    """对字符串做一次并行重写；无规则的字符原样保留。"""
    return "".join(rules.get(ch, ch) for ch in axiom)


def rewrite(axiom: str, rules: Dict[str, str], iterations: int) -> str:
    """重写 iterations 次。"""
    if iterations < 0 or iterations > MAX_ITERATIONS:
        raise LSystemError(f"迭代次数需在 0~{MAX_ITERATIONS} 之间，实际为 {iterations}")
    current = axiom
    for _ in range(iterations):
        current = rewrite_once(current, rules)
    return current


# --------------------------------------------------------------------------- #
# 2. 海龟解释
# --------------------------------------------------------------------------- #
def interpret(
    instructions: str,
    angle: float,
    step: float = 1.0,
    heading: float = 0.0,
    draw_chars: str = "FG",
    move_chars: str = "f",
) -> List[Path]:
    """把指令串解释为若干条不相连的子路径。

    + 左转 angle，- 右转 angle；[ 压栈，] 弹栈（位置与朝向）；
    draw_chars 中的字符前进并画线，move_chars 中的字符抬笔前进；
    其余字符（如 X、Y、A、B）仅参与重写，海龟忽略。
    """
    if angle <= 0 or angle >= 360:
        raise LSystemError(f"转角需在 (0, 360) 之间，实际为 {angle}")
    if step <= 0:
        raise LSystemError("步长必须为正数")

    x = y = 0.0
    direction = heading
    paths: List[Path] = [[(x, y)]]
    stack: List[Tuple[float, float, float]] = []

    def forward(draw: bool) -> None:
        nonlocal x, y
        rad = math.radians(direction)
        x += step * math.cos(rad)
        y += step * math.sin(rad)
        if draw:
            paths[-1].append((x, y))
        else:
            paths.append([(x, y)])

    for ch in instructions:
        if ch in draw_chars:
            forward(True)
        elif ch in move_chars:
            forward(False)
        elif ch == "+":
            direction += angle
        elif ch == "-":
            direction -= angle
        elif ch == "[":
            stack.append((x, y, direction))
            # 分枝独立成一条子路径，避免弹栈后用直线连回分枝点
            paths.append([(x, y)])
        elif ch == "]":
            if not stack:
                raise LSystemError("指令中 ] 多于 [，分支栈不匹配")
            x, y, direction = stack.pop()
            paths.append([(x, y)])
        # 其他控制字符忽略
    if stack:
        raise LSystemError("指令中 [ 多于 ]，分支栈不匹配")
    return [p for p in paths if len(p) > 1]


def segment_count(paths: Sequence[Path]) -> int:
    return sum(len(p) - 1 for p in paths)


def bounds(paths: Sequence[Path]) -> Tuple[float, float, float, float]:
    """返回 (minx, miny, maxx, maxy)。"""
    pts = [pt for path in paths for pt in path]
    if not pts:
        raise LSystemError("路径为空，无法计算边界")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def generate(
    preset: Preset,
    iterations: int,
    step: float = 1.0,
    draw_chars: str = "FG",
) -> List[Path]:
    """从预设一步到位生成路径。"""
    instructions = rewrite(preset.axiom, preset.rules, iterations)
    return interpret(
        instructions,
        preset.angle,
        step=step,
        heading=preset.heading,
        draw_chars=draw_chars,
    )


# --------------------------------------------------------------------------- #
# 3. 渲染：SVG
# --------------------------------------------------------------------------- #
def render_svg(
    paths: Sequence[Path],
    width: int = 800,
    height: int = 600,
    padding: int = 20,
    stroke_width: float = 1.5,
    color: str = "#2f6f4f",
) -> str:
    """把路径渲染为自包含 SVG 文档（自动等比缩放居中）。"""
    if width <= 0 or height <= 0:
        raise LSystemError("SVG 宽高必须为正整数")
    minx, miny, maxx, maxy = bounds(paths)
    world_w = max(maxx - minx, 1e-9)
    world_h = max(maxy - miny, 1e-9)
    scale = min((width - 2 * padding) / world_w, (height - 2 * padding) / world_h)

    def sx(x: float) -> float:
        return padding + (x - minx) * scale

    def sy(y: float) -> float:
        # SVG y 轴向下，世界 y 轴向上
        return height - padding - (y - miny) * scale

    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<g fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        'stroke-linecap="round" stroke-linejoin="round">',
    ]
    for path in paths:
        if len(path) < 2:
            continue
        d = [f"M{sx(path[0][0]):.2f},{sy(path[0][1]):.2f}"]
        for px, py in path[1:]:
            d.append(f"L{sx(px):.2f},{sy(py):.2f}")
        chunks.append(f'<path d="{" ".join(d)}"/>')
    chunks.append("</g></svg>")
    return "\n".join(chunks)


# --------------------------------------------------------------------------- #
# 4. 渲染：ASCII
# --------------------------------------------------------------------------- #
def render_ascii(paths: Sequence[Path], cols: int = 80, rows: int = 30) -> str:
    """把路径栅格化为 ASCII：字符格高约为宽的两倍，按段采样打点。"""
    if cols < 5 or rows < 5:
        raise LSystemError("ASCII 画布至少 5 列 5 行")
    minx, miny, maxx, maxy = bounds(paths)
    world_w = max(maxx - minx, 1e-9)
    world_h = max(maxy - miny, 1e-9)
    k = min((cols - 1) / world_w, 2 * (rows - 1) / world_h)

    grid = [[" "] * cols for _ in range(rows)]

    def mark(wx: float, wy: float) -> None:
        c = int(round((wx - minx) * k))
        r = int(round((maxy - wy) * k / 2))
        if 0 <= c < cols and 0 <= r < rows:
            grid[r][c] = "#"

    for path in paths:
        for (x1, y1), (x2, y2) in zip(path, path[1:]):
            seg_len = math.hypot(x2 - x1, y2 - y1)
            steps = max(2, int(math.ceil(seg_len * k / 2)))
            for i in range(steps + 1):
                t = i / steps
                mark(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)

    lines = ["".join(row).rstrip() for row in grid]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_rule(text: str) -> Tuple[str, str]:
    if "=" not in text:
        raise argparse.ArgumentTypeError(f"规则格式应为 X=替换串，实际为 {text!r}")
    left, right = text.split("=", 1)
    left, right = left.strip(), right.strip()
    if len(left) != 1:
        raise argparse.ArgumentTypeError("规则左部必须是单个字符")
    if not right:
        raise argparse.ArgumentTypeError("规则右部不能为空")
    return left, right


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="L-system 分形生成器（SVG / ASCII）")
    p.add_argument("preset", nargs="?", help="预设名，用 --list 查看")
    p.add_argument("-n", "--iterations", type=int, default=3, help="迭代次数（0~12）")
    p.add_argument("--angle", type=float, help="自定义转角（度）")
    p.add_argument("--axiom", help="自定义公理")
    p.add_argument("--rule", action="append", default=[], type=_parse_rule,
                   help="自定义规则，可重复，如 F=F+F-F")
    p.add_argument("--heading", type=float, default=0.0, help="初始朝向（度，默认 0=东）")
    p.add_argument("--step", type=float, default=1.0, help="海龟步长")
    p.add_argument("--draw-chars", default="FG", help="前进并画线的字符")
    p.add_argument("--ascii", action="store_true", help="输出 ASCII 图（默认）")
    p.add_argument("--cols", type=int, default=80, help="ASCII 列数")
    p.add_argument("--rows", type=int, default=30, help="ASCII 行数")
    p.add_argument("--svg", metavar="PATH", help="输出 SVG 文件路径")
    p.add_argument("--width", type=int, default=800, help="SVG 宽度")
    p.add_argument("--height", type=int, default=600, help="SVG 高度")
    p.add_argument("--list", action="store_true", help="列出内置预设后退出")
    return p


def resolve_preset(args: argparse.Namespace) -> Preset:
    if args.axiom:
        if not args.rule:
            raise LSystemError("自定义模式至少需要一条 --rule")
        angle = args.angle if args.angle is not None else 90.0
        return Preset("custom", args.axiom, dict(args.rule), angle, args.heading, "自定义")
    if not args.preset:
        raise LSystemError("未指定预设名；用 --list 查看可用预设，或用 --axiom/--rule 自定义")
    if args.preset not in PRESETS:
        raise LSystemError(f"未知预设 {args.preset!r}；用 --list 查看可用预设")
    preset = PRESETS[args.preset]
    if args.angle is not None or args.rule:
        preset = Preset(
            preset.name,
            args.axiom or preset.axiom,
            {**preset.rules, **dict(args.rule)},
            args.angle if args.angle is not None else preset.angle,
            args.heading if args.heading else preset.heading,
            preset.description,
        )
    return preset


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list:
        for name, p in PRESETS.items():
            print(f"{name:16s} angle={p.angle:<5} {p.description}")
        return 0
    try:
        preset = resolve_preset(args)
        paths = generate(preset, args.iterations, step=args.step,
                         draw_chars=args.draw_chars)
        if args.svg:
            svg = render_svg(paths, width=args.width, height=args.height)
            with open(args.svg, "w", encoding="utf-8", newline="\n") as f:
                f.write(svg)
            print(f"wrote {args.svg} ({segment_count(paths)} segments)")
        else:
            print(render_ascii(paths, cols=args.cols, rows=args.rows))
            print(f"# {preset.name} n={args.iterations} segments={segment_count(paths)}")
    except (LSystemError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
