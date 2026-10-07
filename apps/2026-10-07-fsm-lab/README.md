# 2026-10-07 · fsm-lab —— 有限状态机实验台（DFA / NFA / 确定化）

一个小而完整的自动机实验台：DFA 逐字符模拟并输出状态轨迹；
带 epsilon 边的 NFA 用 epsilon 闭包与子集进行模拟；并通过
**子集构造（powerset construction）**把 NFA 确定化为等价 DFA。
机器用 JSON 定义，CLI 可运行输入串、转换 NFA、查看内置演示。

## 功能

- **DFA**：状态集、字母表、确定转移函数、起始与接受状态；
  `run` 返回（是否接受，状态轨迹）；转移缺失即进入死状态并拒绝；
  非法输入符号、起始/接受状态不合法均报错
- **NFA**：转移目标为状态集合，支持 epsilon 边（键 `""`）；
  - `epsilon_closure`：栈式求 epsilon 闭包
  - `move`：集合在某符号上的一步转移并集
  - `accepts`：每步做"move → 闭包"，集合为空即拒绝
- **确定化**：子集构造
  - 从起始状态的 epsilon 闭包出发，BFS 枚举可达状态子集
  - 每个子集是一个新 DFA 状态（确定性标签 `{q0,q1}`），
    含任一原接受状态即为接受状态
  - 空子集不生成转移（等价于隐式死状态）
- **JSON I/O**：`type` 为 `dfa`/`nfa`，样例见 sample_dfa.json、
  sample_nfa.json；非法 type 与缺字段报错

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置演示：DFA/NFA 模拟、确定化与等价性核对
python fsm_lab.py demo

# 在 JSON 机器上运行输入串（接受退出码 0，拒绝退出码 1）
python fsm_lab.py run sample_dfa.json 01
python fsm_lab.py run sample_nfa.json aab

# NFA 确定化为 DFA（输出 DFA JSON）
python fsm_lab.py convert sample_nfa.json
```

预置机器：二进制串以 1 结尾（DFA）、含子串 `ab`（NFA）、
语言 `{1,10}`（epsilon NFA）。

## 实现要点

1. **NFA 模拟的本质是集合运算**：NFA 在某一时刻可能处于多个状态，
  用"epsilon 闭包 → 读符号 move → 再闭包"保持当前状态集合，
  最后看集合与接受状态是否相交。
2. **子集构造把不确定性离线消除**：NFA 的每个状态子集对应 DFA 的
  一个状态，子集数量有上界（2^n），但只需枚举从起始闭包可达的
  子集；本例"含 ab"NFA 仅产生 4 个 DFA 状态。
3. **可哈希是工程细节**：状态子集必须用 `frozenset` 才能作为
  字典键与工作队列元素（这是开发中实际踩到并修复的 bug）。
4. **死状态的两种等价处理**：显式建死状态并自循环，或转移缺失即
  拒绝；DFA 采用后者，确定化时跳过空子集，输出更精简。
5. **等价性可验证**：对字母表上长度 ≤4 的全部串（含 epsilon NFA
  的样例集）逐一比较 NFA 与确定化 DFA 的判定，作为正确性证据。

## 测试

```bash
python -m unittest test_fsm_lab -v
```

共 19 个用例：DFA 判定/轨迹/非法符号/缺失转移/校验；NFA 接受、
非法符号、epsilon 闭包、epsilon 语言；确定化状态数、长度 ≤4
全串等价性穷举、epsilon NFA 确定化等价；JSON 装载与非法 type；
以及 demo、run（DFA/NFA）、convert、缺文件的 CLI 子进程冒烟。

开发中修复了两个真实缺陷：①起始子集未转 `frozenset` 导致
无法作为字典键；②`from_dict` 在校验 type 之前先访问字段，
非法 type 抛错类型不对。修复后全部通过。
