# text-stats · 2026-09-03

零依赖文本统计小工具（Python 标准库）。

## 功能

- 字符数 / 词数 / 句数统计；
- 按平均阅读速度（200 wpm）估算阅读时长；
- 高频词 Top-N，默认过滤英文停用词；
- 支持词内连字符与撇号（`state-of-the-art`、`I'm` 视为一个词）；
- 提供可复用函数与命令行入口。

## 运行

```bash
# 单元测试
python -m unittest test_text_stats -v

# CLI 示例
python text_stats.py sample.txt
python text_stats.py sample.txt --top 5 --keep-stopwords
```

## 实现要点

- 正则 `[a-z0-9]+(?:['-][a-z0-9]+)*` 切词，兼顾缩写与连字符词；
- 句数按 `. ! ?` 序列切分并过滤空段；
- `collections.Counter.most_common` 取高频词；
- 统计逻辑与 CLI 分离，核心函数全部可单测。
