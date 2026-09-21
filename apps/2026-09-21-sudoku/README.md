# 2026-09-21 · sudoku —— 数独求解 / 校验 / 生成器

零依赖的数独工具集：MRV 启发式回溯求解、带上限的解计数（判定唯一解）、
以及「随机填满 + 挖洞保唯一」的题目生成器，附带 `solve / check / generate`
命令行，输入格式宽松（0、`.`、`_` 均可表示空格，宫线可写可不写）。

## 功能

- **求解**：回溯搜索，每步选择候选数最少的空格（MRV，Minimum Remaining
  Values），遇到死路立即剪枝；返回解棋盘且不修改输入
- **校验**：区分「合法且完成」「合法但未完成（给出空格数）」
  「行/列/宫冲突非法」三种状态
- **解计数**：`count_solutions(limit=2)` 找到指定数量解即停，
  用于 O(1) 量级的唯一性判定（不必枚举全部解）
- **生成**：随机化回溯先得到一个完整终盘，再按随机种子打乱的顺序挖洞，
  每挖一格验证解仍唯一，不唯一就回填；同一种子结果完全可复现
- **宽松解析**：`1-9` 为已知数，`0`/`.`/`_` 为空格，
  空格、`|`、`-`、`+`、换行等自动忽略，恰好收集 81 格

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 求解示例题
python sudoku.py solve sample_puzzle.txt

# 校验完成度
python sudoku.py check sample_puzzle.txt      # 合法但未完成 -> 退出码 1

# 生成唯一解题目（种子可复现，clues=保留已知格数）
python sudoku.py generate --seed 20260921 --clues 36

# 管道组合：生成 -> 求解 -> 校验
python sudoku.py generate --seed 3 --clues 45 | python sudoku.py solve - | python sudoku.py check -
```

作为库使用：

```python
from sudoku import parse, solve, count_solutions, generate, is_solved

puzzle = parse(open("sample_puzzle.txt").read())
solution = solve(puzzle)
assert count_solutions(puzzle, limit=2) == 1   # 唯一解
quiz = generate(seed=42, clues=40)             # 可复现的题面
```

## 实现要点

- **候选数**：由所在行、列、3x3 宫的已用数字集合做差集得到；
  MRV 让搜索始终先填约束最强的格子，经典难题也能在毫秒级完成。
- **不修改入参**：`solve` / `count_solutions` 内部深拷贝棋盘，
  调用方的题面保持原样（有专门的回归测试）。
- **唯一性保证**：生成挖洞时若 `count_solutions` 达到 2 就立即回填，
  因此产出的每道题都保证恰好一个解；已知格在解中保持不变。
- **参数边界**：`clues` 限制在 17~81（17 是唯一解数独已知数的理论下限），
  非法输入抛 `SudokuError`。
- **退出码约定**：solve 成功 0 / 无解 1 / 输入错误 2；
  check 完成 0 / 未完成或非法 1 / 输入错误 2。

## 测试

```bash
python -m unittest test_sudoku -v
```

共 24 个用例，覆盖：宽松解析与三种空格记号、格子数校验、
行/列/宫冲突检测、经典题解出且与标准答案逐格一致、输入不被修改、
**合法但无解的构造**、唯一解/多解/非法棋盘的解计数、
生成器的种子可复现性、已知格数量、解唯一性与已知格保持，
以及 solve/check/generate/stdin/缺文件的 CLI 子进程冒烟。

开发中修掉一个测试构造错误：最初的「多解」题面前两行在中列出现
同列重复（实际非法，计数为 0），已改为行/列/宫均无冲突的两行拉丁前缀。
