---
name: brainstorming
description: Vibe Research Brainstorming 显式模式入口，研究构想与方案规划。
---

# Brainstorming

macOS 使用安装器记录的解释器：读取 `~/.config/vibe-research/launcher.json` 中的 `python` 与 `workspace`（设置过 `XDG_CONFIG_HOME` 时使用对应配置目录），以该绝对路径替换下文所有 Python 命令的解释器。不要调用系统 `python3` 开发工具占位程序；专用运行时无需 Homebrew 或 Command Line Tools。


本目录 `../..` 是插件根；CLI 为 `<插件根>/runtime/bin/vr`。这是宿主技能命令入口，不在自由文本中匹配斜杠关键词。

先执行 `vr mode enter brainstorming --workspace <工作区> --session <当前对话ID>`，有 CODEX_THREAD_ID 时可省略 session。工作区优先当前目录已有的 outputs/projects.json 的父目录，否则当前工作目录下 vibe-research-workspace。不得用全局默认 session，也不修改其他对话模式。返回已有项目就续接；新任务可加 --fresh。

先以研究主题选择空间：`brainstorm list --workspace`；已有空间用 `mode enter brainstorming --board B编号`，新主题可用 `mode enter brainstorming --topic 主题`（同样传 workspace/session）。主题从用户需求中理解，必要时只问一句；不把完整需求机械当主题，不创建空白草稿。

以用户问题和已有研究材料开展讨论，默认把成果保存为 `notes` 研究笔记，不让用户先填写多个模块。研究历史与方向决策是 Brainstorming 内的独立视图，继续通过各自的研究 CLI 保存有来源的记录；也可根据需求调用阅读、版图、方案或写作技能。旧 landscape/history/directions/proposal/progress 记录保留为兼容内容，不要求依次完成。通过 `brainstorm packet B编号 --module notes --workspace ...` 读取空间，按需用 `brainstorm update --input JSON` 更新笔记，实际引用时记录 sources/uses 与版本。落地方案用 `brainstorm handoff` 产生交接材料，再按用户选择进入 Engineering；不使用 Lightning 草稿箱，不因切换视图创建或转化项目。

图形桌面仅用 scripts/companion.py --workspace 确保研究伴侣存在，不主动展开。若当前对话仅切换模式，简短报告选定模式；有需求则继续完成。

## 双向衔接

用 `bridge preview --workspace ... --input spec.json` 核对分叉点，再按用户授权执行 `bridge transfer`。direction=promote 使用来源 board，可带 idea、验收/协议/停止条件与 environment；direction=abstract 使用来源工程 project。转换始终新建独立项目与 giver 分支，不接受复用 target 或旧 board。request_id 为 UUID，失败重试沿用原编号和参数；expected_updated_at/source_revision 检查来源版本。按已授权的切换范围，用 mode enter 关联返回项目，仅影响当前对话。

保留来源研究数据与附件，转换只建立计划和快照；实验运行按任务授权另行执行。

Brainstorming 与 Engineering 均为独立登记项目。跨模式转化用 giver 派生新分支与新项目；不要复用来源或既有目标。使用 `vr giver --workspace <工作区> branch <新分支> --from <来源项目或分支> --mode <目标模式>`，或工作台转化入口；需要版本管理时读取 giver 技能。

## 阶段管理

恢复项目、保存实质里程碑或目标改变时，主 agent 读取 [项目与分支管理流](../vibe-research/references/management-flow.md)，用 `vr workflow assess` 评估是否建议转换、派生、切换或保存版本；用 `workflow record` 保留用户选择与执行回执。用户已明确授权时直接执行，同一目标不重复询问；一次性报告不默认派生项目。普通问答和界面维护不启动此流程。


## 项目开始前的全局配置检查

每次开始或恢复项目，先运行 `vr settings status --workspace <工作区>` 检查本机数据库配置与最近连接结果。`unverified` 只表示尚未联网验证，不能说成已可用；若有 `needs_auth`、`blocked` 或 `waiting`，询问用户是否现在补充配置，也允许使用其他来源继续。用户同意后进入统一工作台 `/settings?setup=1` 的全局配置引导，按对应数据库说明完成本机保存与验证；不让用户在聊天粘贴密钥。用户本次已选择稍后时，同一项目与配置状态下不重复询问。新鲜联网验证只在用户确认或明确要求检索所需来源时，通过 `vr settings check --workspace <工作区> --provider <来源>` 运行。设置不是项目模块，不写入研究图、研究分支或项目状态。
