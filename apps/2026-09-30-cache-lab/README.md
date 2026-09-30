# 2026-09-30 · cache-lab —— LRU / LFU 缓存算法实验台

零依赖的缓存淘汰算法实现与对比工具：手写**双向链表**完成 O(1) 的
LRU（最近最少使用）与 LFU（最不经常使用，频率分桶 + minFreq），
支持容量淘汰、TTL 过期（惰性删除、时钟可注入）、命中统计；
附带命令工作流回放（同时比较两种算法命中率）与确定性 Zipf 负载 demo。

## 功能

- **LRUCache**：一条双向链表维护访问顺序，前端为最近访问；
  `get` 命中即摘除并提到前端，容量满时从尾部淘汰；更新已有键
  同样重置访问时间
- **LFUCache**：每个频率一条双向链表（`freq -> list`），节点记录
  访问频率；`get` 时从旧频率桶摘除、加入 `freq+1` 桶前端，
  维护 `min_freq`；容量满时淘汰 `min_freq` 桶尾部（同频内最久未用），
  桶空则删除并更新 `min_freq`
- **TTL**：`set(key, value, ttl=N)` 设置过期时刻；访问时惰性检查，
  过期键当场摘除（计入 miss、不计入容量淘汰）；时钟函数可注入，
  测试完全确定
- **统计**：hits / misses / evictions / size / hit_ratio
- **工作流回放**：文本命令 `set k v [ttl=N]`、`get k`、`delete k`，
  `#` 注释与空行忽略；同一工作流分别用 LRU/LFU 回放并对比
- **Zipf 负载生成**：按 Zipf 分布（偏斜度可调）生成 get/set 混合
  请求，种子可复现，用于观察不同算法在热点负载下的命中率差异

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# Zipf 负载对比（10000 请求 / 键空间 200 / 容量 50）
python cache_lab.py demo --requests 10000 --capacity 50 --key-space 200

# 回放命令文件
python cache_lab.py replay sample_workload.txt --capacity 3

# 标准输入
echo "set a 1`nget a" | python cache_lab.py replay - --capacity 2
```

作为库使用：

```python
from cache_lab import LRUCache, LFUCache

c = LRUCache(capacity=128)
c.set("user:1", {...}, ttl=60)
c.get("user:1")
c.stats()
```

## 实现要点

1. **为什么手写链表**：LRU/LFU 都要求在 O(1) 内完成"定位 + 摘除 +
   重排"。哈希表定位节点，双向链表 O(1) 摘除（节点自带 prev/next），
   哨兵节点让首尾操作无需判空。
2. **LFU 的 O(1) 关键**：频率分桶后，淘汰不需要全局扫描，直接取
   `min_freq` 桶；提升频率时若旧桶变空且等于 `min_freq`，
   `min_freq` 取剩余桶的最小键；新插入的键令 `min_freq=1`。
3. **同频平局**：频率桶内仍按 LRU 排列（新提升的节点放前端），
   淘汰取桶尾，因此 LFU 在同频率上退化为 LRU，行为可预期。
4. **TTL 与时钟注入**：过期判断统一走 `self._now()`，测试用
   FakeClock 手动推进时间，不依赖真实 sleep；过期释放的容量不增加
   eviction 计数，语义上区别于容量淘汰。
5. **demo 实测**：Zipf（skew=1.0）下 LFU 命中率 70.81%、LRU 68.95%；
   热点稳定时 LFU 略优，但在热点随时间轮换的负载下 LFU 会被旧热键
   长期占座，LRU 对近期变化更敏感——这是两者选型的核心权衡。

## 测试

```bash
python -m unittest test_cache_lab -v
```

共 27 个用例：LRU 的未命中默认值/更新/淘汰顺序/更新重置时效/删除清空；
LFU 的频率淘汰/同频 LRU 平局/更新加频/min_freq 推进；TTL 的到期、
过期释放容量、LFU 过期与非法 ttl；构造参数校验；命令解析（含 ttl=）
与回放统计；Zipf 负载形状与确定性；以及 demo/replay/stdin/缺文件/
零容量/坏命令的 CLI 子进程冒烟。

开发中修正两处测试构造：①样例工作流实际含 7 个 get（最初误按 8
断言）；②Zipf 确定性用例漏传必填的 key_space 参数。
