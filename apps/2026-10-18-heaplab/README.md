# 2026-10-18 · heaplab —— 二叉堆实验台

零依赖的二叉堆实验台：手写数组存储的小顶堆/大顶堆（上浮下沉、
线性 heapify），堆排序、流式 top-k、多路有序归并、双堆维护
数据流中位数，并附带 CLI。

## 功能

- **BinaryHeap**：`push` / `pop` / `peek` / `heapify`，
  支持 `key` 函数（传 `-x` 即大顶堆）
- **堆排序**：先 heapify 再逐个弹顶，O(n log n)，支持逆序
- **top-k**：
  - 前 k 大：容量 k 的小顶堆，比堆顶大才替换
  - 前 k 小：容量 k 的大顶堆，比堆顶小才替换
  - 只需 O(k) 额外空间、一遍扫描，O(n log k)，适合海量数据
- **merge_sorted**：多路有序序列归并，用最小堆每路取队首
- **RunningMedian**：大顶堆存较小一半、小顶堆存较大一半，
  每次 O(log n) 插入、O(1) 读中位数

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置演示
python heaplab.py demo

# 堆排序（--desc 降序），文件参数可省略则读标准输入
python heaplab.py sort sample_numbers.txt

# 前 k 小（默认）/ 前 k 大（--largest）
python heaplab.py topk 5 sample_numbers.txt
python heaplab.py topk 3 --largest sample_numbers.txt

# 逐元素输出运行中位数
python heaplab.py median sample_numbers.txt
```

作为库使用：

```python
from heaplab import BinaryHeap, heapsort, top_k_largest, running_median
h = BinaryHeap.heapify([9, 4, 7, 1])
h.pop()                          # 1
heapsort([3, 1, 2], reverse=True)  # [3, 2, 1]
top_k_largest(range(1000000), 3)    # 只占 O(3) 空间
running_median([2, 1, 5])          # [2, 1.5, 2]
```

## 实现要点

1. **数组即完全二叉树**：下标 i 的父节点是 `(i-1)//2`、
  左右孩子是 `2i+1`、`2i+2`；末尾追加后 `sift up`，
  弹出堆顶后用末元素补位再 `sift down`。
2. **线性 heapify**：从最后一个非叶子节点 `n//2-1` 向前逐层
  下沉，比逐个 push 的 O(n log n) 更优，整体只需 O(n)。
3. **top-k 用"对侧"的堆**：求最大 k 个反而用小顶堆看住门槛——
  堆顶始终是当前 top-k 中最小的，新来的更大才替换；数据流式到达
  时无需全部保存，是数据库 `ORDER BY ... LIMIT k` 的常用思路。
4. **双堆中位数**：两个堆规模差不超过 1，较小半区元素数不少
  于较大半区；奇数个时中位数是小半区堆顶，偶数个时取两堆顶
  均值，避免了每次重新排序。
5. **key 复用**：大顶堆不是另写一套比较，而是把 key 取负，
  比较逻辑与小顶堆完全共用。

## 测试

```bash
python -m unittest test_heaplab -v
```

共 23 个用例：弹堆顺序、heapify、大顶堆、key 堆、空堆异常；
升序/降序堆排序、空与重复元素、20 组随机数据与内置 sorted 对账；
top-k 大/小、k=0、k 超长、k 为负、key 版本；多路归并、含空序列、
中位数已知向量 `[2,1,5,7,2,0,5] → [2,1.5,2,3.5,2,2,2]`、
空中位数；以及 demo、sort、topk、median 的 CLI 子进程冒烟。
全部一次通过。
