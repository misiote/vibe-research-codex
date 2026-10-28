---
name: brainstorming
description: Vibe Research Brainstorming 显式模式入口，研究构想与方案规划。
---

# Brainstorming

本目录 `../..` 是插件根；CLI 为 `<插件根>/runtime/bin/vr`。这是宿主技能命令入口，不在自由文本中匹配斜杠关键词。

先执行 `vr mode enter brainstorming --workspace <工作区> --session <当前对话ID>`，有 CODEX_THREAD_ID 时可省略 session。工作区优先当前目录已有的 outputs/projects.json 的父目录，否则当前工作目录下 vibe-research-workspace。不得用全局默认 session，也不修改其他对话模式。返回已有项目就续接；新任务可加 --fresh。

先以研究主题选择空间：`brainstorm list --workspace`；已有空间用 `mode enter brainstorming --board B编号`，新主题可用 `mode enter brainstorming --topic 主题`（同样传 workspace/session）。主题从用户需求中理解，必要时只问一句；不把完整需求机械当主题，不创建空白草稿。

模块为 landscape/history/directions/proposal/progress；用 `brainstorm packet B编号 --module ... --workspace ...` 读取任务与对应技能。它们各自维护内容、来源和版本，按本次需求选择，不要求固定流程。更新 `brainstorm update --input JSON` 只写当前模块，uses 显式记录参考模块的版本；输入变化时检查 needs_review 后再沿用结论。方案材料用 research-admin-expert。需要落地时 `brainstorm handoff` 产生交接材料，再按用户选择进入 Engineering。Brainstorming 不使用 Lightning 草稿箱，也不擅自登记正式工程项目。

图形桌面仅用 scripts/companion.py --workspace 确保研究伴侣存在，不主动展开。若当前对话仅切换模式，简短报告选定模式；有需求则继续完成。

## 双向衔接

用 `bridge preview --workspace ... --input spec.json` 核对分叉点，再按用户授权执行 `bridge transfer`。direction=promote 使用来源 board，可带 idea、验收/协议/停止条件与 environment；direction=abstract 使用来源工程 project。转换始终新建独立项目与 giver 分支，不接受复用 target 或旧 board。request_id 为 UUID，失败重试沿用原编号和参数；expected_updated_at/source_revision 检查来源版本。按已授权的切换范围，用 mode enter 关联返回项目，仅影响当前对话。

保留来源研究数据与附件，转换只建立计划和快照；实验运行按任务授权另行执行。

Brainstorming 与 Engineering 均为独立登记项目。跨模式转化用 giver 派生新分支与新项目；不要复用来源或既有目标。使用 `vr giver --workspace <工作区> branch <新分支> --from <来源项目或分支> --mode <目标模式>`，或工作台转化入口；需要版本管理时读取 giver 技能。

## 阶段管理

恢复项目、保存实质里程碑或目标改变时，主 agent 读取 [项目与分支管理流](../vibe-research/references/management-flow.md)，用 `vr workflow assess` 评估是否建议转换、派生、切换或保存版本；用 `workflow record` 保留用户选择与执行回执。用户已明确授权时直接执行，同一目标不重复询问；一次性报告不默认派生项目。普通问答和界面维护不启动此流程。
