# 2026-09-29 · consistent-hash —— 一致性哈希环

零依赖的一致性哈希（Consistent Hashing）实现：标准库 `hashlib` +
`bisect` 构建带**虚拟节点**的哈希环，支持节点增删、键归属查询、
分布统计，以及增删节点时的**键迁移计划**，并验证一致性哈希最关键的
单调性（加节点只把键迁到新节点、删节点只影响该节点上的键）。

## 功能

- **哈希环**：每个物理节点生成 `replicas` 个虚拟节点（默认 150），
  虚拟键为 `node#i`，md5 哈希后插入有序环；查询键时顺时针找到第一个
  虚拟节点，环尾回绕到环首（`bisect_right` + 回绕）
- **节点维护**：`add_node / remove_node`，重复添加、删除不存在的
  节点、虚拟节点哈希冲突均会报错
- **键分配**：`get_node(key)` 查询归属；`assign(keys)` 给出
  节点 -> 键列表；`distribution_table` 输出键数与占比
- **迁移计划**：
  - `plan_add_node(node, keys)`：记录加节点前后的归属变化，
    返回迁移三元组 `(key, old, new)` 与新分配
  - `plan_remove_node(node, keys)`：下线节点，返回键的去向及
    各接收节点的数量
- **可插拔哈希函数**：构造器接受任意 `str -> int` 哈希函数，
  测试中用 FNV-1a 验证

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置演示：三节点分布 -> 加 node-D（迁移报告）-> 下线 node-B（去向统计）
python consistent_hash.py demo --keys 10000 --replicas 150

# 统计键文件在节点间的分布（每行一个键，# 注释/空行忽略）
python consistent_hash.py dist sample_keys.txt \
    --nodes cache-1,cache-2,cache-3

# 标准输入
echo "a`nb" | python consistent_hash.py dist - --nodes x,y
```

作为库使用：

```python
from consistent_hash import make_ring

ring = make_ring(["A", "B", "C"], replicas=150)
ring.get_node("user:1001")
moved, assignment = ring.plan_add_node("D", keys)
```

## 实现要点

1. **为什么需要虚拟节点**：物理节点直接上环时，环上位置分布不均，
   节点数少的情况下负载倾斜明显；每个物理节点放 150 个虚拟节点后，
   demo 中 5000 个键的节点占比落在 21%~35%，方差显著缩小。
2. **查询复杂度**：环用有序 list + `bisect` 维护，查询 O(log N)，
   增删节点为 O(replicas × log N)；适合节点不频繁变动的缓存/分片场景。
3. **单调性验证**：加节点时，任意键的新归属要么不变、要么等于新节点，
   老节点之间零迁移——demo 输出"其余节点间迁移 0 个"；删节点时，
   迁移集合恰好等于该节点原有的全部键，其余节点的键原地不动。
4. **加了再删可完全还原**：`add D` 后 `remove D`，所有键的归属与
   操作前逐键一致（虚拟节点按相同哈希重建，环位置确定）。
5. **哈希空间**：默认 md5 取 128 bit 整数，2^128 的环上 150×节点数
   个虚拟节点发生碰撞的概率可忽略；一旦碰撞直接报错而非静默覆盖。

## 测试

```bash
python -m unittest test_consistent_hash -v
```

共 19 个用例：空环/非法副本数/增删环大小/重复与缺失节点/单节点全量
拥有/构造确定性/自定义哈希函数；键恰好分配一次、计数求和与占比合计、
虚拟节点下的均衡区间；加节点单调性、删节点局部影响、加后删除完全还原、
迁移计划与环实际状态一致；以及 demo/dist/stdin/缺文件/非法参数的
CLI 子进程冒烟。本轮实现与测试一次跑通，未发现需要修复的缺陷。
