# huffman-codec · 2026-09-05

零依赖 **Huffman（哈夫曼）压缩编解码器**（Python 标准库），支持文件压缩、还原与压缩率统计。

## 功能

- 字符频率统计 + 最小堆构建 Huffman 树，同频按固定次序平局，**结果确定可复现**；
- 生成无前缀变长码：高频字符码长更短；
- 比特级打包（位补齐），文件自带 JSON 码表头，**解码端无需原始文本**；
- 支持空文本、单字符、多行文本与 Unicode（含 emoji）；
- 损坏 / 截断数据抛 `ValueError`；
- CLI 三个子命令：`encode` / `decode` / `stats`。

## 文件格式

```text
[4 字节大端：码表头长度 N][N 字节 UTF-8 JSON：{"pad":补齐位,"codes":{字符:码}}][压缩比特主体]
```

## 运行

```bash
# 单元测试（16 个用例）
python -m unittest test_huffman -v

# 查看码表与压缩率（内置 roundtrip 自检）
python huffman.py stats sample.txt

# 压缩 / 还原文件
python huffman.py encode sample.txt -o sample.huf
python huffman.py decode sample.huf -o restored.txt
```

## 实现要点

- `heapq` 维护频率优先队列，堆元素带递增 `order`，消除同频歧义；
- 编码：字符→比特串→每 8 位切一个字节，记录末尾补齐位数；
- 解码：重建"码→字符"反查表，逐位匹配即输出，残留位判定为损坏；
- 压缩率统计把码表头体积也计入，数字真实不虚报。
