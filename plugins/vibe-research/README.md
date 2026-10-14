# Vibe Research 0.4.0

在 Codex 安装本插件后，新聊天说“打开 Vibe Research 工作台”即可由 skill 识别。研究数据存放在用户选择的工作区，与插件缓存分开；升级或卸载插件不删除研究库。

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

设置页提供 WoS、Scopus、Unpaywall 和校园资源的本机配置与按需引导。WoS、Scopus 已进入持久分页检索；Unpaywall 会在候选出现 DOI 后加入开放全文定位任务。未拿到本人 key 或机构权益前保留为待配置，不宣称授权通过。登录、验证码和权限申请由本人在官方页面完成。每库每月 50 元只是预算约束，插件不采购或续费。

## 项目、备份与升级

研究项目有独立 UUID、研究图和工作历史。Codex 原生项目映射使用实际 list_projects 返回值；本插件不能自行调用不可用的宿主建项目 API。没有匹配项目时，在 Codex 添加研究工作区后关联即可。

升级前 `vr --project <项目> bundle create <外部备份.zip>`；恢复到不存在的新目录，核验 doctor 后再恢复工作。备份包含研究库、活动库、检索队列和附件，不含工程源码、外部文件、凭据或 Codex 任务。格式版本 1，不支持的版本明确拒绝，不直接试改旧库。升级插件会替换工具载荷，不搬移项目数据。

`vr --project <项目> integrations diagnostics <新文件.json>` 导出白名单诊断，不含题目、查询、路径、原始错误、IP 或凭据。分享前请本人查看；不会自动上传。

复制 zip 到另一机器，解压后可通过随包安装器添加 marketplace。`SHA256SUMS.json` 校验工具文件；科研结论仍需原文和独立审阅。macOS、Windows 和 Linux 使用彼此隔离的桌面入口；首次迁移到新设备时先用空项目确认入口、工作台和本机数据库连接，再恢复正式研究项目。

社区文献技能的来源与许可见 runtime/skills/LICENSE.md 和 runtime/docs/COMMUNITY_SKILLS.md。未安装的运行时、未批准的机构权限以及宿主能力不会因插件安装而自动获得。

## 三类研究专家

科研精读专家把论文主张还原成可证伪命题，逐项检查证据链、质量维度、适用范围和未排除解释，并保存复现细节。研究关系专家记录检索覆盖，把可见进展组织成路线、争议和边界，再与本地研究图建立有依据的桥接。科研写作编辑负责所有面向人的正式文档定稿；它只能改善结构与文字，不能提高证据强度或抹去未知。
