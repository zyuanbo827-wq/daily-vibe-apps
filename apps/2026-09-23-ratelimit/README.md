# 2026-09-23 · ratelimit —— 四种限流算法实验台

零依赖的限流（rate limiting）算法对比工具：一次实现**令牌桶、固定窗口计数、
滑动窗口日志、滑动窗口计数**四种常见方案，统一 `try_acquire(now, tokens)`
接口，时钟由外部传入（测试完全确定）；附带突发场景对比与请求流回放 CLI，
输出逐请求放行/拒绝记录和拒绝率统计。

## 功能

- **TokenBucket 令牌桶**：按 `refill_rate`（令牌/秒）恒定补充，
  令牌数封顶 `capacity`；支持突发流量与一次消费多令牌；
  超过容量的请求直接拒绝，拒绝不产生部分扣减
- **FixedWindowCounter 固定窗口**：窗口按时间轴对齐（起点 0），
  窗口内计数、跨窗口重置；实现简单但窗口边界可能出现 2 倍突刺
- **SlidingWindowLog 滑动窗口日志**：用 deque 保留窗口内全部请求
  时间戳，每次请求先淘汰 `now-window` 之前的记录再计数；判定精确，
  代价是内存随请求数增长
- **SlidingWindowCounter 滑动窗口计数**：只保留当前窗口计数与上一
  窗口计数，按 `前窗口计数 × 前窗口剩余时间权重 + 当前计数` 估算；
  平滑且省内存，是前两者的折中
- **请求流回放**：文本文件每行 `timestamp` 或 `timestamp,tokens`，
  `#` 注释与空行忽略，时间戳非递减；可指定任意算法与参数，
  输出 `ALLOW/DENY` 时间线与汇总（放行、拒绝、拒绝率）

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置突发场景：四种算法并排对比
python ratelimit.py demo

# 回放请求流（默认 sliding-log，限额 5 / 窗口 10s）
python ratelimit.py replay sample_requests.txt --algo sliding-log \
    --limit 5 --window 10

# 令牌桶：容量 5、补充速率 0.5/s
python ratelimit.py replay sample_requests.txt --algo token-bucket \
    --limit 5 --window 10 --rate 0.5

# 标准输入回放
echo "0.0`n0.0`n0.0" | python ratelimit.py replay - --algo fixed-window --limit 2 --window 10
```

作为库使用：

```python
from ratelimit import TokenBucket, SlidingWindowLog

bucket = TokenBucket(capacity=5, refill_rate=0.5)
bucket.try_acquire(now=0.0)          # True
bucket.try_acquire(now=0.0, tokens=5)  # 突发多令牌
```

## 实现要点

- **时钟注入**：所有算法不直接读系统时钟，时间戳由参数传入，
  同一组用例结果完全确定，也便于回放任意历史请求流。
- **状态推进**：固定/滑动窗口计数器在跨窗口时对齐窗口起点；
  跨越两个及以上窗口时上一窗口计数清零（已无加权意义）。
- **加权估算公式**：
  `estimate = prev_count × (window - elapsed) / window + current_count`，
  `estimate + tokens ≤ limit` 才放行；demo 中跨窗口的突发会被它
  最保守地拒绝（时间线 `AAAAADADD`，其余算法为 `AAAAADAAA`），
  直观体现各算法的边界差异。
- **浮点容差**：令牌桶在剩余令牌恰好满足请求时加 `1e-9` 容差，
  避免浮点误差导致本该放行的请求被误拒。
- **参数校验**：容量/限额/窗口必须为正、时间戳不得倒退、
  请求令牌数必须为正，违规统一抛 `RateLimitError`。

## 测试

```bash
python -m unittest test_ratelimit -v
```

共 22 个用例：令牌桶的突发/补充/封顶/多令牌不部分扣减/超大请求/
时钟倒退，固定窗口的限额/重置/跨多窗口，滑动日志的限额与恰好过期
淘汰，滑动窗口计数器的加权公式（含 t=10 与 t=15 的估算值）与
跨窗口清零，事件解析的各种格式与错误，以及 demo / replay / stdin /
缺文件 / 坏数据的 CLI 子进程冒烟。

开发中修正了两处测试构造：①令牌桶补充用例对 t=3 时可用令牌总数
少算了一个（补充 2 个即可连续放行 2 次）；②样例请求流最初的
10.1/10.2 时刻窗口内仍有 5 个时间戳（早期请求未过淘汰边界），
已把突发时间戳前移到 0.0~0.4，使回放结果与注释场景一致。
