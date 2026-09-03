# daily-vibe-apps

> 每天一个小应用（Daily Vibe Coding Challenge）：由定时任务每天自动生成一个
> **可独立运行、经过验证**的小工具 / 小游戏 / 小可视化，按日期归档到 `apps/`。

## 规则（每日任务遵循）

1. 每个应用位于 `apps/YYYY-MM-DD-<slug>/`，自带 README，可独立运行；
2. 技术选型优先**零依赖**：Python 标准库（附 `unittest`）或单文件 HTML/CSS/JS；
   确需前端框架时使用 Vite，且必须 `npm run build` 通过；
3. Python 应用必须跑通单元测试；所有 commit 使用真实当前时间，不回改日期；
4. 每天分 2~4 个有意义的 conventional commits 提交，并更新下方索引表。

## 应用索引

| 日期 | 应用 | 技术 | 简介 |
|---|---|---|---|
| 2026-09-03 | [text-stats](./apps/2026-09-03-text-stats) | Python 标准库 | 文本统计：词数/句数/阅读时长/高频词，含 CLI 与单测 |

## 本地结构

```
daily-vibe-apps/
  apps/
    YYYY-MM-DD-slug/
      README.md
      ...源码与测试
```

## License

MIT
