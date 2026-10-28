---
name: vibe-research
description: 在 Codex 中开始、继续和管理 Vibe Research 研究项目，使用统一工作台、可追溯研究图、多来源文献检索与精读；适用于用户说开始研究、继续研究或展示研究工具，不用于普通问答。
---

# Vibe Research

插件根目录是本技能目录的 `../..`。工具是 `<插件根>/runtime/bin/vr`，便携启动器是 `<插件根>/scripts/workbench.py`。以实际 skill 路径解析，不猜安装目录，不把研究数据写入插件缓存。

## 一个入口

用户第一次开始研究时，优先使用已明确选定的研究工作区。Windows 上读取 `%APPDATA%/VibeResearch/launcher.json` 中已安装入口的 workspace，避免每次聊天另建工作区。没有安装设置时，若当前目录已有 `outputs/projects.json`，它的父目录就是现有工作区，否则在用户当前工作目录的 `vibe-research-workspace` 建立独立工作区。若当前目录就是插件缓存或无法判断研究目录，询问一次目标文件夹。

先解析 Python 3.9+ 解释器：macOS/Linux 优先 `python3`，Windows 优先 `py -3`，也可使用可确认版本的 `python`。在有图形桌面的 Codex 项目对话中，优先运行 `<Python> <插件根>/scripts/companion.py --workspace <工作区>`：统一启动器会选择 macOS AppKit、Windows WebView2 或 Linux GTK/WebKitGTK 实现，启动或复用工作台，只确保悬浮“研究伴侣”存在，默认保持收起；不要同时主动打开工作台面板。用户点击伴侣才显示或收起独立的研究现场窗口，拖动伴侣可调整入口位置。研究现场不从 Codex 窗口复制坐标或宽度。每次开始或继续 Vibe Research 项目对话都执行一次，返回 `started: false` 代表已在运行，不重复创建。

伴侣预检失败、处于 Linux 纯终端/SSH 环境，或用户明确不要悬浮入口时，运行 `<Python> <插件根>/scripts/workbench.py --workspace <工作区> --no-open`，再按用户要求打开返回的本机地址。Windows 优先使用 Release 包内置程序；源码包没有预编译程序时仅在存在 .NET 8 SDK 的情况下首次构建。Linux 缺 GTK/WebKitGTK 时给出发行版安装提示，不擅自安装系统软件。默认端口 8766，遇到其他工作区占用时换端口，不结束未知服务。工作台有三步向导；已有项目直接恢复，不重复新建。不要把 ChatGPT Pets 说成可绑定自定义点击动作；当前 Pets 接口不能将角色点击改为工作台开关。

若用户要求命令行入口，可运行 `<Python> <插件根>/scripts/install_cli.py --workspace <工作区>` 安装 `vr-workbench` 用户命令。不要用固定任务卡片冒充常态入口：左侧栏收起时它不可见。悬浮伴侣只在项目对话实际开始或继续时检查并启动，不安装登录项，不虚构永久在线 agent；右键伴侣可退出。

用 `vr hub list --registry <工作区>/projects.json` 选择项目。研究库和工作进程使用本插件 bundled continuity skill 中的规则；同一未完成目标延续原编号，不因为新聊天或跨天重开。所有图状态修改通过 `vr --project <目录>` CLI，不能直接改数据库或 JSON。

## 来源与完整性

Windows 伴侣必须显示到用户当前桌面。Codex 的常规命令可能位于 `CodexSandboxDesktop`；启动器会拒绝在其中创建不可见窗口。遇到此提示时，用宿主获准的非沙箱命令在实际桌面启动，或让用户双击已安装的 `vr-companion.cmd`。不得通过切换桌面或更改安全设置绕过限制。用 `--status` 确认 `visible_to_user: true`，不能仅凭 `running: true` 宣称用户已看到入口。`--show`、`--hide`、`--reset-position` 支持明确控制并等待完成回执。不要把账户/目录权限错误当成来源网络失败。

Windows 的 `py -3` 或 `python` 不可用时，可读取安装器的 `VIBE_RESEARCH_PYTHON` 设置，或检查 `%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。先确认版本再使用绝对路径，并追加 `-X utf8`。

首次检索或上次受阻时检查 integrations 状态并按需联网复测。新项目向导会对所选来源做真实只读预检并检查 PDF 精读环境。公开来源优先；每数据库每月 50 元上限不是采购授权。缺少个人 key 时引导用户在工作台来源卡片中保存，命令行 setup 仅作备用；不得让用户在聊天粘贴凭据。macOS 默认钥匙串。WoS/Scopus 的 key、机构 entitlement 和执行主机网络分别核验；Unpaywall 仅随 DOI 候选做开放全文定位。机构 SSO 由用户在官方页面完成，浏览器登录不代表脚本有 API 权限。

Scopus 机构接入先区分三类路径：机构网页入口只供浏览器使用；校园网或校园 VPN 由操作系统路由承载 API；Elsevier Institutional Token 与 API key 配套用于无法采用机构 IP 的获批场景。不要把 WebVPN URL 当成 API 代理，也不要接管机构账号、密码、验证码或浏览器 Cookie。若用户同时启用应用层全局代理和校园 VPN，Scopus API 绕过应用代理以使用系统校园路由，公开来源沿用用户网络设置；是否获得订阅权限仍以单条 API 查询为准。检测到隧道接口不能单独算通过。

综述和缺口判断使用 retrieval 持久覆盖队列；不要将 search 首个成功来源当作多来源完成。只有真实运行 worker 才承诺后台续查。文献先初筛价值，再按任务选择概要 summary、粗读 skim 或精读 deep，用户指定优先。用 `reading plan --task ...` 获得建议，`reading triage ... --depth ...` 保存；价值不自动等于精读。恢复时按 `reading queue` 返回的深度继续；粗读/精读缺全文保留待获取，概要可基于摘要并披露材料范围。三种阅读产物都不自动证明证据成立。

## 快速开始 · Lightning

用户只需关键词发散、讲稿/slides、学术材料或一次阅读时，使用 Lightning，不要求先给研究主题，不执行 init、hub create 或 work start。工作台 `/lightning` 有独立草稿箱；CLI `vr lightning start --workspace <工作区> [--input draft.json]` 创建空白或带任务的草稿，`list/show/packet/update/discard/export` 管理草稿。draft.json 字段为 title/task/depth/body/output；task 为 keywords/slides/writing/reading/history/decision。草稿保存到工作区 `.vibe-research/drafts`，不会进入 projects.json、研究图或工作历史；明确告知草稿保留到主动丢弃，不宣称无磁盘痕迹。

读取 `lightning packet --workspace <工作区> L编号` 调度相应技能，直接完成用户实际产物：关键词图使用可用图形/可视化工具，slides 使用可用演示文稿工具，方案撰写与阅读按选定深度执行。产物正文/文件位置写回草稿 output，不把仅有提纲说成已生成演示文件。页面是草稿编辑与交接入口，模型由 Codex 对话执行，不虚构点击即有后台 AI。用户需要持续追踪时再创建正式项目，草稿不自动转为研究证据。

## 研究历史与方向决策

发展史、方法谱系、转折点使用 `research-history-expert`；global 为已检方向全景，local 为指定主题下的子主题。`vr history packet/show/add` 与项目的 `/explore#history` 同步，事件按发表/发生时间排序，与工作日志分开。覆盖账本、精读、版图和写作共用来源。

选题、路线比较、下一步实验使用 `research-direction-expert`。`vr direction packet/evaluate/save` 比较证据、五维区间、资源硬约束与最小实验，项目 `/explore#direction` 显示结果。方向评价不自动修改假设状态；正式行动继续通过 decide，实验执行另按用户授权。

## 与 Codex 项目关联

有 list_projects 工具时读取真实本地项目，仅将目录确实包含研究库的项目通过 hub bind-codex 关联。没有匹配项目时指导用户在 Codex 中把研究工作区添加为本地项目，然后重新读取；不编辑 Codex 私有状态文件，不臆造宿主项目 ID。绑定不会扩大沙箱权限。

用户明确请求专家团时，可按文献、实验、分析、独立审查分工使用宿主子代理；主会话是唯一 vr 正式状态提交者。没有子代理能力时说明并顺序执行，不伪称独立评审。

三种文献阅读读取同级 `research-reading-expert`；方向版图、研究路线和本地图桥接读取 `research-landscape-expert`。所有面向人的正式报告在科学内容审阅后读取 `research-writing-editor` 定稿。写作编辑不能修改数字、引文、证据方向、覆盖范围或研究状态；内容缺口退回对应专家。

## 长期恢复与交付

读 `<插件根>/skills/vibe-research-continuity/SKILL.md` 决定续接、暂停和新目标。备份恢复默认暂停，不隐式运行旧任务。新环境先运行 `doctor` 和 `integrations check`；网络测试按需进行，不能把离线校验当作权限验收。

## 三种显式模式

Lightning、Brainstorming、Engineering 是三个独立的宿主技能入口，在斜杠菜单选择同名技能（也可 $lightning / $brainstorming / $engineering）调用。它们用 mode enter 记录当前对话的模式，互不切换其他对话；不要在普通消息中扫描关键词来模拟命令。原生技能菜单需要新聊天或重载后发现；未看见菜单时说明宿主发现状态，不声称新建了内建命令。

Lightning 保留临时草稿；Brainstorming 围绕研究主题建立独立登记项目；landscape/history/directions/proposal/progress 模块按显式版本引用协作，方案模块按需加载 research-admin-expert；Engineering 关联正式项目、代码环境、工作包与实验，使用 research-engineering-expert。用户可随任务改变模式，不把三种模式当作必须逐级通过的流程。

## 双向衔接

用 `bridge preview --workspace ... --input spec.json` 核对分叉点，再执行 `bridge transfer`。Brainstorming 和 Engineering 均有独立项目身份和研究库；两种转化始终创建新项目与新 giver 分支，不复用旧 target 或 board。direction=promote 使用来源 board，可带 idea、acceptance/protocol/stop_rule/environment；direction=abstract 使用来源 project，可带新项目 topic；可选 branch 指定新分支名。request_id 为 UUID，相同参数重试沿用原编号。expected_updated_at/source_revision 检查来源版本。

管理版本时使用 giver：init/status/branch/switch/checkout/commit/log/tree/diff/show/tag/restore/reflog。读取 giver 技能获取确定性 CLI；不提供分支合并或 cherry-pick。派生保留完整研究快照与登记附件，后续各自演进；科学支持状态不因转化升级。调用 vrpet 可直接确保悬浮研究伴侣按钮存在。

## 阶段管理

恢复项目、保存实质里程碑或目标改变时，主 agent 读取 [项目与分支管理流](references/management-flow.md)，用 `vr workflow assess` 评估是否建议转换、派生、切换或保存版本；用 `workflow record` 保留用户选择与执行回执。用户已明确授权时直接执行，同一目标不重复询问；一次性报告不默认派生项目。普通问答和界面维护不启动此流程。
