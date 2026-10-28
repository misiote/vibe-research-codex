---
name: engineering
description: Vibe Research Engineering 显式模式入口，研究实施与开发协同。
---

# Engineering

本目录 `../..` 是插件根；CLI 为 `<插件根>/runtime/bin/vr`。这是宿主技能命令入口，不在自由文本中匹配斜杠关键词。

先执行 `vr mode enter engineering --workspace <工作区> --session <当前对话ID>`，有 CODEX_THREAD_ID 时可省略 session。工作区优先当前目录已有的 outputs/projects.json 的父目录，否则当前工作目录下 vibe-research-workspace。不得用全局默认 session，也不修改其他对话模式。返回已有项目就续接；新任务可加 --fresh。

若用户已指定正式研究项目，用 --research-project 关联。否则读取 hub list 选择已有项目；用户需要新项目时用项目向导。加载 research-engineering-expert，关联代码、工作包和实验，先观察再行动，不从其他对话继承活动项目。

图形桌面仅用 scripts/companion.py --workspace 确保研究伴侣存在，不主动展开。若当前对话仅切换模式，简短报告选定模式；有需求则继续完成。

Brainstorming 与 Engineering 均为独立登记项目。跨模式转化用 giver 派生新分支与新项目；不要复用来源或既有目标。使用 `vr giver --workspace <工作区> branch <新分支> --from <来源项目或分支> --mode <目标模式>`，或工作台转化入口；需要版本管理时读取 giver 技能。

## 阶段管理

恢复项目、保存实质里程碑或目标改变时，主 agent 读取 [项目与分支管理流](../vibe-research/references/management-flow.md)，用 `vr workflow assess` 评估是否建议转换、派生、切换或保存版本；用 `workflow record` 保留用户选择与执行回执。用户已明确授权时直接执行，同一目标不重复询问；一次性报告不默认派生项目。普通问答和界面维护不启动此流程。
