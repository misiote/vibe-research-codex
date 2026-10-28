# Vibe Research 0.10.1

在 Codex 安装本插件后，新聊天说“打开 Vibe Research 工作台”即可由 skill 识别。研究数据存放在用户选择的工作区，与插件缓存分开；升级或卸载插件不删除研究库。

macOS Release 安装器会调用 Codex App 自带的 CLI 登记 marketplace，并安装、启用本插件。安装后必须用 `Command-Q` 完全退出并重新打开 App，再把默认 `~/VibeResearch` 工作区添加为本地项目，在该项目的新聊天中运行插件默认提示。研究伴侣在插件开始处理对话后出现，不是登录启动项。

在 Vibe Research 项目对话中，插件优先唤起一个收起的悬浮“研究伴侣”。点击伴侣会显示一个独立的研究现场窗口，再次点击收起；它不复用 Codex 窗口，也不依赖左侧栏或右侧栏的宽度。拖动伴侣可以调整入口位置，位置会在本机保存。Agent 每次开始或继续项目对话时只做幂等检查，不主动展开工作台，也不会重复启动按钮。右键伴侣可退出。

三端共用 `scripts/companion.py`，平台代码彼此隔离，便于单独构建和验收：

| 平台 | 用户入口 | 平台实现 | 运行要求 |
| --- | --- | --- | --- |
| macOS | `python3 scripts/companion.py --workspace <工作区>` | `scripts/companion/macos/main.m` | AppKit、WebKit、`clang` |
| Windows | `py -3 scripts\companion.py --workspace <工作区>` | `scripts/companion/windows/` | Release 包内置程序；WebView2 Runtime |
| Linux | `python3 scripts/companion.py --workspace <工作区>` | `scripts/companion/linux/main.py` | GTK 3、Cairo、WebKitGTK 4.1、图形桌面 |

用 `--check` 做本机预检，`--status` 查看状态，`--toggle` 展开或收起，`--stop` 退出。Linux 的纯终端或 SSH 环境会明确退回浏览器工作台。Windows 的 GitHub Release 完整包包含 x64/arm64 预编译伴侣；源码安装且没有预编译文件时，可用 .NET 8 SDK 首次构建。ChatGPT Pets 的点击动作不能由插件重绑定，因此研究伴侣是独立的项目入口，不会修改用户已有宠物。CLI 可安装固定命令：

```bash
python3 scripts/install_cli.py --workspace <研究工作区>
vr-workbench
```

Windows 使用 `py -3 scripts\install_cli.py --workspace <研究工作区>`，随后运行 `vr-workbench.cmd`。命令只在调用时启动或复用本机服务，不安装系统登录项，也不声称助手在后台持续研究。

## 本机运行

Python 3.9 或以上，无额外依赖即可运行工作台、图和元数据检索。macOS、Linux 使用 `python3`，Windows 使用 `py -3` 或 `python`。启动器优先选择 Codex bundled runtime；仍缺少 PDF 依赖时，可在工作台设置中一键准备独立运行时，随后重启工作台。

三端均从上表的统一入口检查并唤起研究伴侣。`python3 scripts/workbench.py --workspace <研究工作区> --no-open` 返回普通浏览器入口；Windows 可将 `python3` 换为 `py -3`。首次三个步骤创建项目；已有项目读取历史继续。端口冲突时使用 `--port`，不会结束其他服务。

`python3 runtime/bin/vr --project <项目> integrations setup --provider openalex` 使用终端不回显输入；Windows 可将 `python3` 换为 `py -3`。macOS 默认系统钥匙串；Linux 和 Windows 优先使用环境变量，也可明确选择本机凭据文件。该文件不进入研究备份，但 Windows 的 `chmod 600` 不等同于 ACL 隔离，应依赖用户目录权限并避免共享账户。钥匙串失败不会自动降级为明文。已有明文不会自动迁移或删除。

## 机构数据库

数据库向导支持机构网页入口、校园 VPN 和 API Institutional Token 的分层配置。Scopus 请求会绕过应用层全局代理并使用系统网络路由，避免全局代理遮蔽校园 VPN；机构账号和验证码始终留在官方页面。

设置页提供 WoS、Scopus、Unpaywall 和校园资源的本机配置与按需引导。WoS、Scopus 已进入持久分页检索；Unpaywall 会在候选出现 DOI 后加入开放全文定位任务。未拿到本人 key 或机构权益前保留为待配置，不宣称授权通过。登录、验证码和权限申请由本人在官方页面完成。每库每月 50 元只是预算约束，插件不采购或续费。

## 项目、备份与升级

研究项目有独立 UUID、研究图和工作历史。Codex 原生项目映射使用实际 list_projects 返回值；本插件不能自行调用不可用的宿主建项目 API。没有匹配项目时，在 Codex 添加研究工作区后关联即可。

升级前 `vr --project <项目> bundle create <外部备份.zip>`；恢复到不存在的新目录，核验 doctor 后再恢复工作。备份包含研究库、活动库、检索队列和附件，不含工程源码、外部文件、凭据或 Codex 任务。格式版本 1，不支持的版本明确拒绝，不直接试改旧库。升级插件会替换工具载荷，不搬移项目数据。

`vr --project <项目> integrations diagnostics <新文件.json>` 导出白名单诊断，不含题目、查询、路径、原始错误、IP 或凭据。分享前请本人查看；不会自动上传。

复制 zip 到另一机器，解压后可通过随包安装器添加 marketplace。`SHA256SUMS.json` 校验工具文件；科研结论仍需原文和独立审阅。macOS、Windows 和 Linux 使用彼此隔离的桌面入口；首次迁移到新设备时先用空项目确认入口、工作台和本机数据库连接，再恢复正式研究项目。

社区文献技能的来源与许可见 runtime/skills/LICENSE.md 和 runtime/docs/COMMUNITY_SKILLS.md。未安装的运行时、未批准的机构权限以及宿主能力不会因插件安装而自动获得。

## 三类研究专家

科研精读专家把论文主张还原成可证伪命题，逐项检查证据链、质量维度、适用范围和未排除解释，并保存复现细节。研究关系专家记录检索覆盖，把可见进展组织成路线、争议和边界，再与本地研究图建立有依据的桥接。科研写作编辑负责所有面向人的正式文档定稿；它只能改善结构与文字，不能提高证据强度或抹去未知。

## 0.6.0 · 分层阅读与轻量研究

- 文献选择概要、粗读、精读。用户选择优先，按任务建议深度；笔记与审阅证据分开。
- 工作区“快速开始”进入 Lightning 草稿，无需主题；本机草稿保留到主动丢弃，不登记项目。Codex 根据草稿任务执行关键词图、写作、slides、阅读、历史或方向比较，工作台不自带后台模型。
- 项目“研究历史”按 Global/Local 展示已检方向或局部路线，保留日期精度、来源与覆盖；与操作日志分开。
- 项目“方向决策”比较候选假设、增量、证据、硬约束、最小实验和停止条件；给出区间与权重敏感性，不自动修改假设状态。

CLI：`reading plan/depth/note`、`lightning start/list/show/packet/update/discard/export --workspace <目录>`、`history packet/show/add`、`direction packet/evaluate/save/list`。结构可由 packet 读取。

## 0.7.0 · Research modes

Lightning、Brainstorming、Engineering 提供一致图标入口及独立宿主技能命令。启用技能后在 Codex 斜杠菜单选择同名项（也可 `$lightning`、`$brainstorming`、`$engineering`）；这些是宿主显式分发的技能入口，不是自由文本关键词识别，也不是新增的 Codex 内建执行模式。首次安装后新开聊天或重载宿主发现技能；实际菜单名称遵循宿主显示。

- Lightning：独立草稿箱，打开即编辑，保存后持久化；无需研究主题。
- Brainstorming：独立登记项目与研究视野、研究脉络、方向研判、方案规划模块。各模块可独立开展，uses 引用具体输入版本；被引用内容更新后提示复核。没有草稿箱，不自动登记工程项目。工程交接是可检查的材料，不自动执行。
- Engineering：本地 Git、VS Code/Cursor 与 SSH Remote；GitHub 提交/PR/CI、W&B 与 MLflow 的运行状态和选定指标。适配器独立返回快照，通过提交版本关联；某服务失败不阻断其他观察。GitLab 当前仅地址跳转。认证使用已有 gh/SSH 或本机环境变量，不写入项目。按需同步，不是持续监控。
- 科研工作包具有研究问题、验收标准、协议、停止条件、状态和验收依据；通用实验可用 profile=generic，旧项目继续使用默认 MARL 协议。远程运行、配置上传或发布不因环境关联而发生。
- 研究历史以 topic/subtopic/aliases 为索引，Global/Local 不再依赖图节点。联网检索逐源进入持久候选队列，来源限制和待补页保留，候选经阅读后才组织成事件。

CLI 新入口：`mode catalog/enter/status`（对话 ID 隔离）、`brainstorm start/list/show/update/packet/handoff --workspace ...`、`engineering link/task/show/sync`、`history search --topic ... [--scope local --subtopic ...] [--aliases ...] [--background]`。Engineering sync 仅本地，显式 --network 才读取远端。SSH 使用已有 Host 别名、BatchMode 与严格主机验证；MLflow 可引用用户既有 SSH 隧道地址。

科研方案参考来自 K-Dense-AI/scientific-agent-skills 的 MIT 许可 research-grants，固定提交、文件哈希和许可证位于 skills/research-admin-expert/references/upstream。参考中的机构规则需要按当前项目正式要求重新核对。

短命令：Codex 默认给插件技能加 `vibe-research:` 命名空间。需要原生 `/lightning`、`/brainstorming`、`/engineering` 短入口时，运行 `python3 scripts/install_modes.py --install`，在公开的个人技能目录注册三个显式别名；如有同名的其他技能会拒绝覆盖。别名只在显式调用时加载，最终显示和补全遵循宿主技能菜单，不是自定义内建执行模式。升级后重跑安装器刷新别名；可用 --plugin-root 指向稳定的个人插件源码目录。

## 0.9.0 · giver 与独立项目

Brainstorming / Engineering 各自登记独立项目，双向转化始终新建项目与分支。giver 提供快照、提交历史、差异、标签和恢复，不提供分支合并。原生命令新增 giver、vrpet。输入框去除示例占位文字；空日期仅在实际输入时显示格式。

## 0.8.5 · 主题入口同步

Brainstorming 默认隐藏仅关联已归档/移除项目的主题，可勾选显示隐藏主题；恢复项目后自动重现。独立主题和仍关联活动项目的主题保持可见，全部内容保留。CLI `brainstorm list --include-hidden` 可列出隐藏主题。

## 0.8.4 · 归档确认

归档和移除入口不再要求先暂停工作或检索。确认框提示用户核对运行情况；操作仅整理入口，保留研究文件与原有工作状态，不停止实际进程。

## 0.8.3 · 工作台操作反馈

归档、移除及丢弃草稿使用页面内确认，兼容悬浮工作台；完成和失败即时提示。Codex 交接提供可选择的任务卡片与独立复制按钮，剪贴板被阻止时提示手动复制。

## 0.8.1 · 转化入口与结果反馈

模式转化入口置于内容区上方。提交时显示等待状态，完成后保留目标项目、工作包与进入入口；失败重试复用请求，视图刷新失败不误报转化失败。重新打开空间可查看已保存的关联。

## 0.8.0 · 双向衔接与研究地图（旧版衔接由 0.9.0 独立分支替代）

Brainstorming 与 Engineering 均独立登记。双向转化始终新建项目和 giver 分支，从明确的快照分叉；不复用已有目标，原项目继续保持独立。登记附件和研究图复制到新项目，各自保存版本与后续变化。

CLI `vr bridge preview --workspace ... --input spec.json` / `bridge transfer ...`。direction=promote 使用来源 board，可带 idea、acceptance/protocol/stop_rule、environment；direction=abstract 使用来源 project，可带新项目 topic；可选 branch 指定新分支。request_id 为 UUID，同参数重试不重复创建；不再接受既有 target 或目标 board。不自动执行实验或提高证据支持状态。

文献库支持发表时间新旧、标题 A–Z、处理阶段排序。阶段依照实际完成且全文版本有效的记录：精读、粗读、概要、未处理、初筛未纳入；选择阅读深度不会伪造完成状态。缺日期记录排在有日期之后。地图默认隐藏初筛未纳入论文及其连线，勾选可恢复；数据与来源均保留。

自由网络“重置布局”重新初始化力导向位置并回到可见范围；“总览”仅调整视野。“3D 阶段分层”使用固定空间坐标、透视投影和可旋转相机，不运行力导向；节点不能单独拖动，整体可以旋转/缩放。离开分层视图会恢复之前的网络坐标。


## giver · GIt VibE Research

`/giver` 为宿主原生技能入口，子命令调用确定性 CLI：`vr giver --workspace WORKSPACE status`。支持 init、branch、switch/checkout、commit、log/tree、diff、show、tag、restore、reflog；`runtime/bin/giver` 提供同一套独立 CLI。分支各有项目目录，切换只影响当前对话。提交包含完整研究快照和登记附件。restore 以新版本恢复指定 Brainstorming 模块；完整历史版本用 branch --from COMMIT 新建项目查看。

不提供 merge、cherry-pick、rebase 或远程 push/pull。科研路线保持独立，通过比较、明确引用和新派生项目承接成果。外部代码仓库与实际远程进程不因研究分支自动复制或停止。

固定工作台 `/giver` 提供分支树、提交图、版本比较和操作记录。`/vrpet` 直接确保悬浮研究伴侣存在，不主动展开工作台；短命令由 scripts/install_modes.py 显式注册，不匹配普通消息关键词。

## 0.10.0 · 阶段管理

主 agent 在任务边界用 `vr workflow assess --workspace WORKSPACE --input context.json` 评估管理动作；同一目标继续原分支，形成可实施方案才建议 Engineering，持续维护的回顾才建议 Brainstorming，一次性汇报保留在原项目。完成里程碑可保存本地 checkpoint。显式用户指令直接执行，agent 提出的转换/派生/切换才询问，一次一个建议；延后、拒绝、待答与已完成均持久记录，避免跨聊天重复提示。

`vr workflow record` 登记选择和真实执行回执，`vr workflow status --workspace WORKSPACE` 查看记录。评估不会自己创建项目或执行命令，也不注册后台定时任务。完整规则见 [项目与分支管理流](skills/vibe-research/references/management-flow.md)。

## 0.10.1 · 共用项目导航

Brainstorming 和 Engineering 的项目内统一提供概览、研究地图、文献、研究历史、方向决策与设置入口，另保留各自模式入口。跨视图保留项目身份，可返回同一个 Brainstorming 主题；选择项目后收起目录，避免导航被项目列表挤出首屏。未保存构想在离开时提示，取消后保留编辑。独立 watch 入口保留原有导航。
