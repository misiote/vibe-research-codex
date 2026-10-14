---
name: vibe-research
description: 在 Codex 中开始、继续和管理 Vibe Research 研究项目，使用统一工作台、可追溯研究图、多来源文献检索与精读；适用于用户说开始研究、继续研究或展示研究工具，不用于普通问答。
---

# Vibe Research

插件根目录是本技能目录的 `../..`。工具是 `<插件根>/runtime/bin/vr`，便携启动器是 `<插件根>/scripts/workbench.py`。以实际 skill 路径解析，不猜安装目录，不把研究数据写入插件缓存。

## 一个入口

用户第一次开始研究时，优先使用已明确选定的研究工作区；若当前目录已有 `outputs/projects.json`，它的父目录就是现有工作区，否则在用户当前工作目录的 `vibe-research-workspace` 建立独立工作区。若当前目录就是插件缓存或无法判断研究目录，询问一次目标文件夹。

先解析 Python 3.9+ 解释器：macOS/Linux 优先 `python3`，Windows 优先 `py -3`，也可使用可确认版本的 `python`。在有图形桌面的 Codex 项目对话中，优先运行 `<Python> <插件根>/scripts/companion.py --workspace <工作区>`：统一启动器会选择 macOS AppKit、Windows WebView2 或 Linux GTK/WebKitGTK 实现，启动或复用工作台，只确保悬浮“研究伴侣”存在，默认保持收起；不要同时主动打开工作台面板。用户点击伴侣才显示或收起独立的研究现场窗口，拖动伴侣可调整入口位置。研究现场不从 Codex 窗口复制坐标或宽度。每次开始或继续 Vibe Research 项目对话都执行一次，返回 `started: false` 代表已在运行，不重复创建。

伴侣预检失败、处于 Linux 纯终端/SSH 环境，或用户明确不要悬浮入口时，运行 `<Python> <插件根>/scripts/workbench.py --workspace <工作区> --no-open`，再按用户要求打开返回的本机地址。Windows 优先使用 Release 包内置程序；源码包没有预编译程序时仅在存在 .NET 8 SDK 的情况下首次构建。Linux 缺 GTK/WebKitGTK 时给出发行版安装提示，不擅自安装系统软件。默认端口 8766，遇到其他工作区占用时换端口，不结束未知服务。工作台有三步向导；已有项目直接恢复，不重复新建。不要把 ChatGPT Pets 说成可绑定自定义点击动作；当前 Pets 接口不能将角色点击改为工作台开关。

若用户要求命令行入口，可运行 `<Python> <插件根>/scripts/install_cli.py --workspace <工作区>` 安装 `vr-workbench` 用户命令。不要用固定任务卡片冒充常态入口：左侧栏收起时它不可见。悬浮伴侣只在项目对话实际开始或继续时检查并启动，不安装登录项，不虚构永久在线 agent；右键伴侣可退出。

用 `vr hub list --registry <工作区>/projects.json` 选择项目。研究库和工作进程使用本插件 bundled continuity skill 中的规则；同一未完成目标延续原编号，不因为新聊天或跨天重开。所有图状态修改通过 `vr --project <目录>` CLI，不能直接改数据库或 JSON。

## 来源与完整性

首次检索或上次受阻时检查 integrations 状态并按需联网复测。新项目向导会对所选来源做真实只读预检并检查 PDF 精读环境。公开来源优先；每数据库每月 50 元上限不是采购授权。缺少个人 key 时引导用户在工作台来源卡片中保存，命令行 setup 仅作备用；不得让用户在聊天粘贴凭据。macOS 默认钥匙串。WoS/Scopus 的 key、机构 entitlement 和执行主机网络分别核验；Unpaywall 仅随 DOI 候选做开放全文定位。机构 SSO 由用户在官方页面完成，浏览器登录不代表脚本有 API 权限。

综述和缺口判断使用 retrieval 持久覆盖队列；不要将 search 的首个成功回退冒充多来源完成。等待项保留查询与游标；只有实际运行 worker 才承诺后台续查。候选导入后必须用 `reading triage` 留下初筛理由；一旦判为 `valuable`，同一轮立即获取全文并执行系统精读，不等待用户再次点名。全文暂不可得时保留为“有价值 · 待获取全文”，恢复时优先检查 `reading queue`。候选、初筛价值、全文、原文匹配、解释审阅、复现实验分别标注，不能把“有价值”自动写成已验证证据。

## 与 Codex 项目关联

有 list_projects 工具时读取真实本地项目，仅将目录确实包含研究库的项目通过 hub bind-codex 关联。没有匹配项目时指导用户在 Codex 中把研究工作区添加为本地项目，然后重新读取；不编辑 Codex 私有状态文件，不臆造宿主项目 ID。绑定不会扩大沙箱权限。

用户明确请求专家团时，可按文献、实验、分析、独立审查分工使用宿主子代理；主会话是唯一 vr 正式状态提交者。没有子代理能力时说明并顺序执行，不伪称独立评审。

论文全文精读读取同级 `research-reading-expert`；方向版图、研究路线和本地图桥接读取 `research-landscape-expert`。所有面向人的正式报告在科学内容审阅后读取 `research-writing-editor` 定稿。写作编辑不能修改数字、引文、证据方向、覆盖范围或研究状态；内容缺口退回对应专家。

## 长期恢复与交付

读 `<插件根>/skills/vibe-research-continuity/SKILL.md` 决定续接、暂停和新目标。备份恢复默认暂停，不隐式运行旧任务。新环境先运行 `doctor` 和 `integrations check`；网络测试按需进行，不能把离线校验当作权限验收。
