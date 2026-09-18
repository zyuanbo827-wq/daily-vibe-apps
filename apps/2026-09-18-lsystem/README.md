# 2026-09-18 · lsystem —— L-system 分形生成器

零依赖的 Lindenmayer 系统（L-system）分形生成器：字符串重写 + 海龟绘图，
输出 **SVG 矢量图**或 **ASCII 字符画**。内置科赫雪花、谢尔宾斯基三角形、
龙形曲线、分形灌木与植物，也支持自定义公理与产生式规则。

## 功能

- 并行字符串重写（同一轮新产生的字符不会被立即再次替换），迭代次数 0~12
- 海龟解释器：`F/G` 前进画线、`f` 抬笔移动、`+/-` 转向、`[ ]` 分支栈
  （保存/恢复位置与朝向），其他字符（如 `X/Y`）仅作控制符号
- 渲染：
  - SVG：自动等比缩放居中、y 轴翻转、每个分枝独立 path，可直接浏览器打开
  - ASCII：按段采样栅格化，自动修正字符格 2:1 的宽高比并裁剪空白
- 6 个内置预设：`koch-snowflake`、`koch-curve`、`sierpinski`、`dragon`、
  `bush`、`plant`
- 支持自定义 `--axiom`、可重复的 `--rule X=替换串`、`--angle`、`--heading`

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
python lsys.py --list                       # 查看预设
python lsys.py dragon -n 10 --svg dragon.svg
python lsys.py koch-snowflake -n 3 --svg snow.svg --width 800 --height 800
python lsys.py dragon -n 5 --ascii --cols 60 --rows 24

# 自定义规则：90 度科赫曲线
python lsys.py --axiom F --rule F=F+F-F-F+F --angle 90 -n 3 --ascii
```

作为库使用：

```python
from lsys import PRESETS, generate, render_svg, render_ascii
paths = generate(PRESETS["koch-snowflake"], 3)
open("snow.svg", "w").write(render_svg(paths))
```

`samples/` 目录内附 4 张已生成的示例：科赫雪花（n=3，192 段）、
龙形曲线（n=11，2048 段）、谢尔宾斯基三角形（n=5，729 段）、
分形植物（n=5，1488 段，938 条分枝 path）。

## 实现要点

- `rewrite` 用字典逐字符映射完成并行重写，复杂度 O(输出长度)，
  并对迭代次数做上限保护，避免指数膨胀耗尽内存。
- `interpret` 维护海龟状态 `(x, y, 朝向)` 与一个 `(x, y, 朝向)` 栈：
  遇到 `[` 时把当前分枝独立成一条子路径，`]` 弹栈后另起子路径，
  避免弹栈瞬间用直线把分枝末端连回分枝点。
- `render_svg` 统一计算世界坐标到画布的缩放与平移，y 轴翻转，
  所有坐标保证落在 padding 内（有测试断言）。
- `render_ascii` 以不超过半个字符格的步长对每条线段采样打点，
  纵向坐标按 2:1 修正，使 ASCII 图案比例不失真。
- 段数可由产生式数学验证，测试中据此断言：
  科赫雪花 n 代段数为 `3·4ⁿ`，龙形曲线为 `2ⁿ`，
  谢尔宾斯基三角形为 `3^(n+1)`。

## 测试

```bash
python -m unittest test_lsys -v
```

共 30 个用例，覆盖重写语义与括号平衡、海龟转向/抬笔/分支栈、
各预设段数公式、SVG 结构与坐标边界、ASCII 输出，以及 CLI 的
预设列表、ASCII/SVG 输出、自定义规则和错误退出码（子进程冒烟）。
