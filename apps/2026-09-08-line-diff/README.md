# line-diff · 2026-09-08

零依赖**行级 diff / patch 工具**（Python 标准库）：LCS 对齐、unified diff、补丁应用与反向回滚。

## 功能

- 最长公共子序列（LCS）动态规划对齐两个文本的行；
- 输出接近 git 的 **unified diff**：`---/+++` 文件头、`@@ -a,b +c,d @@` 块头、可配置上下文行数；
- `apply` 把补丁应用回原文，且**逐行校验**上下文，对不上时报错而不是静默改错；
- `reverse` 交换增删方向，实现从新版本回滚到旧版本；
- 纯函数核心（`diff_ops` / `unified_diff` / `apply_patch`）与 CLI 分离，便于测试复用。

## 运行

```bash
# 单元测试（19 个用例）
python -m unittest test_ldiff -v

# 生成 unified diff
python ldiff.py diff sample_old.py sample_new.py --context 2

# 生成补丁并应用 / 反向回滚
python ldiff.py diff sample_old.py sample_new.py > change.patch
python ldiff.py apply sample_old.py change.patch     # 得到新版本
python ldiff.py reverse sample_new.py change.patch   # 回到旧版本
```

## 实现要点

- LCS 用倒序 DP 表，回溯时同分数优先"删除"侧，保证结果确定；
- 每个操作带旧/新两侧 0 基行号，块头行列数按 `equal+delete`、`equal+insert` 分别统计；
- 离变更超过 `context` 行的相同行不进补丁，多处远距变更自动切成多个 hunk；
- 应用补丁时 `context/delete` 行必须与原文按序一致，否则抛 `ValueError`。
