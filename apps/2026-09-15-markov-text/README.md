# markov-text · 2026-09-15

零依赖的**马尔可夫链文本生成器**（Python 标准库）：从语料学习词级转移概率，按种子确定性地生成新句子。

## 功能

- 正则切句（`. ! ?`）与分词（字母/数字/缩写），可选小写归一化；
- 支持 **1 阶 / 2 阶**词级马尔可夫链：状态为前 N 个词，候选后继按语料频次保留（重复即权重）；
- 句首/句尾哨兵 `^`/`$` 保证从句首开始、自然收束；
- 随机源外部注入 `random.Random(seed)`，**同种子、同语料、同参数必得同输出**；
- `max_words` 防止在无句尾的自循环链上无限游走；
- CLI 从文本文件训练并生成指定句数。

## 运行

```bash
# 单元测试（17 个用例）
python -m unittest test_markov -v

# 用内置小语料生成（1 阶 / 2 阶对比）
python markov.py sample_corpus.txt --seed 7 --sentences 4 --order 1
python markov.py sample_corpus.txt --seed 7 --sentences 4 --order 2
```

## 实现要点

- `build_chain` 用固定长度滑动窗口更新状态：`state = (state + word)[-order:]`，1、2 阶共用一份逻辑；
- 转移表是 `状态 -> 候选列表`，列表保留重复词，`rng.choice` 自然实现按频次采样，无需显式概率；
- 生成与训练解耦：链是普通字典，可序列化、可单测；生成函数不触碰全局随机状态；
- 到达句尾哨兵、走到未知状态或达到词数上限都会安全停止，不会死循环。
