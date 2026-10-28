---
name: lightning
description: Vibe Research Lightning 显式模式入口，即时探索与轻量创作。
---

# Lightning

本目录 `../..` 是插件根；CLI 为 `<插件根>/runtime/bin/vr`。这是宿主技能命令入口，不在自由文本中匹配斜杠关键词。

先执行 `vr mode enter lightning --workspace <工作区> --session <当前对话ID>`，有 CODEX_THREAD_ID 时可省略 session。工作区优先当前目录已有的 outputs/projects.json 的父目录，否则当前工作目录下 vibe-research-workspace。不得用全局默认 session，也不修改其他对话模式。返回已有草稿就续接；新任务可加 --fresh。

按返回 task_packet 和用户本次需求直接完成产物；不要求研究主题，不创建项目或工作记录。必要时才加载对应阅读、可视化或产物技能，结果与文件位置写回 lightning update 的 output。

图形桌面仅用 scripts/companion.py --workspace 确保研究伴侣存在，不主动展开。若当前对话仅切换模式，简短报告选定模式；有需求则继续完成。
