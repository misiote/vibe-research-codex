# Vibe Research for Codex

> [!WARNING]
> **平台可用性：目前仅 macOS 已完成实际安装与运行验证。**
> **Windows 和 Linux 尚未完成实际验证，可能无法正常安装或运行，暂不保证可用。** 下方保留的安装脚本与说明仅供尝试；构建或自动化检查通过不代表对应平台已验证可用。

在 Codex 中组织研究构想、文献证据、开发实验与版本历史。Vibe Research 提供本地工作台、悬浮研究伴侣和研究技能；研究数据保存在你选择的工作区，与插件代码分开。

## 安装与首次启动

### 一条命令安装（推荐）

预先安装 Codex 与 Python 3.9+，然后在终端运行。无需 Git、手动解压或复制插件文件。

**macOS（已验证）；Linux（未验证，可能不可用）：**

```bash
curl -fsSL https://raw.githubusercontent.com/misiote/vibe-research-codex/main/install-online.sh -o /tmp/vibe-research-install.sh && sh /tmp/vibe-research-install.sh
```

**Windows PowerShell（未验证，可能不可用）：**

```powershell
Invoke-WebRequest -UseBasicParsing https://raw.githubusercontent.com/misiote/vibe-research-codex/main/install-online.ps1 -OutFile "$env:TEMP\vibe-research-install.ps1"; if ($?) { powershell -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\vibe-research-install.ps1" }
```

安装器从 GitHub 将 `main` 解析为确定的提交，下载该版本、校验工具文件，安装 Codex 插件、工作台命令与五个短入口。安装结束会显示研究工作区位置；完全重启 Codex，把该目录添加为本地项目，即可开始使用。无需管理员权限；不会自动安装系统依赖或重启 App。

默认源码保存在 `~/.local/share/vibe-research/installations`，Windows 为 `%LOCALAPPDATA%\VibeResearch\installations`；研究数据默认在 `~/VibeResearch`。再次运行同一命令可更新，旧源码与研究数据保留。短入口有同名冲突时保留原技能，并提示使用插件技能菜单。

网络无法访问 GitHub、Raw 或 Codeload 时，可使用下面的手动下载方式。更多选项见 [在线安装说明](INSTALL.md#在线安装推荐)。

### 手动下载安装

需要 Python 3.9+，以及支持 `codex plugin` 命令的 Codex。获取当前源码：

```bash
git clone https://github.com/misiote/vibe-research-codex.git
cd vibe-research-codex
```

也可在 GitHub 的 **Code → Download ZIP** 下载并完整解压，保留隐藏的 `.agents/` 目录。Release 附件对应其标签版本，可能早于当前 `main`；请核对版本后下载。

| 平台 | 可用性 | 在仓库根目录安装 | 悬浮研究伴侣依赖 |
| --- | --- | --- | --- |
| macOS | 已完成实际验证 | 双击 `安装Vibe Research.command`，或 `sh install.sh` | 首次构建需要 Xcode Command Line Tools 的 `clang` |
| Windows | **未验证，暂不保证可用** | 双击 `install-windows.cmd` | WebView2；源码无预编译伴侣时需要 .NET 8 SDK |
| Linux | **未验证，暂不保证可用** | `sh install.sh` | 图形桌面、GTK 3、Cairo、WebKitGTK 4.1；也可使用浏览器工作台 |

安装器登记本地 marketplace，安装并启用 `vibe-research@vibe-research-local`，创建默认工作区 `~/VibeResearch` 与终端入口 `vr-workbench`。安装前可用环境变量 `VIBE_RESEARCH_WORKSPACE` 指定工作区。请保留源码安装目录在固定位置，启动器会优先使用它。

1. 完全退出并重启 ChatGPT/Codex；macOS 使用 `Command-Q`。
2. 在插件目录的 **Vibe Research** 来源中确认插件已安装。
3. 将安装器显示的研究工作区添加为 Codex 本地项目，在其中新建聊天。
4. 选择插件，发送“打开 Vibe Research 工作台”。研究伴侣会以收起的按钮出现，点击后展开工作台。

终端也可运行 `vr-workbench`，默认浏览器地址为 `http://127.0.0.1:8766`。命令未找到时，把安装器输出的 bin 目录加入 `PATH`；`vr-workbench --show-config` 可核对实际工作区，`--no-open` 只启动服务并打印地址。平台依赖、更新、卸载与故障排查见 [INSTALL.md](INSTALL.md)。

### 显式命令入口

如需不带插件前缀的短入口，在仓库根目录执行，然后重启 App 或新建聊天：

```bash
python3 plugins/vibe-research/scripts/install_modes.py --install
```

Windows 将 `python3` 换为 `py -3`。该步骤注册 Codex 原生 skill 别名；在命令/技能菜单中选择对应入口后输入需求。同名的其他技能不会被覆盖。宿主也可能显示带 `vibe-research:` 命名空间的入口。

| 入口 | 用途 | 示例需求 |
| --- | --- | --- |
| `/lightning` | 即时探索与轻量创作 | 围绕多智能体协作生成关键词发散图 |
| `/brainstorming` | 研究构想与方案规划 | 比较两条研究路线，整理依据与下一步验证 |
| `/engineering` | 研究实施与开发协同 | 关联现有 Git 仓库，规划实验并记录运行结果 |
| `/giver` | 研究分支与版本管理 | 查看某个项目的版本树和最近变化 |
| `/vrpet` | 唤起悬浮研究伴侣 | 检查入口状态并显示按钮 |

这些是由 Codex 调度的显式技能入口。`/giver status` 等需求由 agent 调用本地研究 CLI 完成；它们不是系统终端中的 Git 命令。

## 三种工作模式

| 模式 | 组织方式 | 适用场景 |
| --- | --- | --- |
| **Lightning** | 无需研究主题；本机草稿，不登记正式研究项目 | 关键词图、阅读、材料整理、Slides 与讲稿等单次任务 |
| **Brainstorming** | 独立项目，保留研究图、文献、模块版本与工作历史 | 方向探索、方案论证、路线比较、阶段交流与学术材料 |
| **Engineering** | 独立项目，关联代码、环境、工作包与实验记录 | 实施研究方案、跟踪开发进展、实验验证与复现 |

Lightning 的草稿箱只属于 Lightning。Brainstorming 使用研究模块组织工作：研究版图、研究历史、方向决策、方案与进展材料；模块可显式关联上游材料，上游变化后提示重新核对。Engineering 以工作包连接研究问题、验收要求、实验协议、停止条件与证据。

工作台负责组织、展示和保存材料，生成与分析由 Codex 中的 agent 执行。“在 Codex 继续”用于交接当前需求；保存草稿本身不会启动模型。Slides 文件生成还取决于宿主可用的演示文稿工具，只有提纲时应明确标注。

## 文献、地图与研究决策

### 检索与分层阅读

在项目的**文献**页面提出主题、查询词和来源要求，先检索、初筛，再按需要选择阅读深度：

| 深度 | 主要产出 |
| --- | --- |
| 概要 | 研究问题、方法、主要结论与相关性判断 |
| 粗读 | 全文结构、实验设置、关键结果与明显限制 |
| 精读 | 主张与证据逐项核对、竞争解释、适用边界与复现细节 |

阅读计划与实际完成状态分开；只有摘要时不能声称已完成全文精读。文献列表可按时间、标题首字母或处理阶段排序。阶段优先级为精读、粗读、概要、未处理、初筛未通过；初筛未通过的文献默认从研究地图隐藏，仍可查看和追溯。

检索支持 arXiv、Crossref、OpenAlex、CORE，以及需要本人或机构授权的 WoS、Scopus 等来源。Unpaywall 用于 DOI 的开放全文定位。实际覆盖以连接检查和检索记录为准：`auto` 策略在首个来源成功后返回，并不表示完成了多来源检索。需要多来源覆盖时应明确指定并核对逐源记录。

在设置中配置数据库，首次使用先检查连接。密钥在本机终端或配置向导输入，不要发到聊天、提交仓库或放入研究附件；机构登录、验证码及权益申请由本人完成。预算限制不代表自动购买授权。

### 研究地图与历史

Brainstorming 和 Engineering 均可从项目导航进入**研究地图、文献、研究历史与方向决策**。

- 研究地图连接问题、文献、假设、实验和结果；力导向视图提供布局初始化，可找回拖远的节点。
- 按工作阶段查看时使用固定的 3D 分层布局，节点不随力导向移动；通过相机调整观察位置。
- 研究历史以**研究主题、子主题和别名**检索。Global 梳理方向的发展，Local 聚焦局部路线；时间轴保留来源、日期精度和检索覆盖范围。

研究历史用于学术路线演化；助手何时做过什么，另在工作历史中查看。

### 方向决策

围绕候选方向比较最接近工作、证据缺口、资源与时间约束，形成可证伪假设、最小区分实验和停止条件。评分与优先级需要结合证据和敏感性分析解释；推荐方向不等于假设已获支持。研究版图、阅读笔记和历史时间轴可作为决策依据，方案与阶段材料继续引用这些依据。

## Engineering：连接开发与实验

在 Engineering 项目中关联现有环境，再同步可核查的开发信息：

| 连接 | 可跟进的信息 |
| --- | --- |
| 本地 Git | 版本、工作区变化；VS Code / Cursor 打开入口 |
| GitHub | 使用已有 `gh` 授权核对提交、PR 与 CI 状态 |
| W&B | 使用本机配置读取运行状态与选定指标 |
| MLflow | 读取实验运行与指标，支持已建立隧道的本地服务地址 |
| SSH | 使用现有 SSH Host 配置检查远程 Git 状态 |

连接适配器独立运行，某项失败不阻断其他来源。登记地址不代表授权成功，同步状态不代表启动训练。远程同步需明确选择联网检查；SSH 不自动接受未知主机、不索取私钥，也不自动建立隧道。代码版本仍由 Git 管理，实验原始数据仍保留在对应系统中。

## giver：项目谱系与版本树

giver（GIt VibE Research）借鉴 Git 的分支、检查点与历史查看方式，管理研究路线和版本。Brainstorming 与 Engineering **相互转化时创建新的独立项目和分支**，保留来源关系；不会覆盖源项目。转换界面提供预览、完成反馈和目标项目入口。

### 找到想看的版本树

1. 打开 **giver**，先看到项目谱系目录。
2. 搜索项目名称、分支名或项目 ID，选择对应谱系；改名后的后续项目也可关联，同名的无关项目不会混为一棵树。
3. 在树与日志中定位分支、检查点和标签，按说明、版本标识或日期查找历史，查看变化与历史内容。
4. 从项目进入时定位到所属谱系。页面地址保留选择状态，可刷新或分享给同一工作台使用者。

浏览历史不会切换 agent 当前工作分支。需要继续某条路线时，明确要求切换；从历史版本开展另一条路线时，创建新分支。

| giver 操作 | 含义 |
| --- | --- |
| `init`、`status` | 初始化与查看研究版本状态 |
| `branch`、`switch` / `checkout` | 建立独立路线、切换工作目标 |
| `commit`、`log`、`tree` | 保存检查点、查看历史与项目谱系 |
| `diff`、`show`、`tag` | 比较变化、查看内容、标记里程碑 |
| `restore`、`reflog` | 恢复支持的模块版本、追溯引用变化 |

当前 `restore` 面向 Brainstorming 模块，以新版本恢复并保留恢复前检查点；从完整历史项目继续可使用 `branch --from`。giver 不提供分支合并，也不替代代码仓库的 Git；外部代码、远程进程和凭据不会随研究分支自动复制。

### Agent 何时提出管理建议

在恢复工作、目标变化、阶段完成或遇到阻碍时，agent 会结合当前上下文评估下一步：研究问题延续时留在原项目；方案准备实施时建议转为 Engineering；需要持续整理方向与阶段材料时可建议建立 Brainstorming；并行验证另一种方案时建议新分支。一次性汇报可在原项目完成。

结构调整先给出具体建议并征求选择；用户明确要求后直接执行。暂缓或拒绝会被记录，避免重复询问。实质性里程碑可保存本机检查点。这套流程在对话中执行，不代表存在后台模型或定时研究服务。

## 一个完整使用示例

1. 选择 `/brainstorming`，输入“比较多智能体协作中的通信压缩与角色分工，梳理已有证据和可验证问题”。建立独立主题项目。
2. 在文献页检索并初筛，对相关工作先做概要，再对关键论文粗读或精读；核对来源覆盖与全文可用性。
3. 在研究历史中选择 Global 查看方向发展，再以 Local 聚焦某条路线；将依据用于方向决策和研究方案。
4. 方案确定后使用转化入口创建 Engineering 分支，关联已有代码仓库、GitHub 与实验平台，建立可验收的工作包。
5. 阶段完成后保存 giver 检查点。若需独立的持续交流空间，从 Engineering 转为新的 Brainstorming 项目；通过 giver 查看二者的来源关系。

只需要一次关键词图或讲稿时，可直接选择 Lightning，不必建立项目。

## 数据、备份与维护

研究数据保存在独立工作区。归档或从入口移除不会自动停止训练、删除代码或结束远程进程；操作前按界面提示确认实际运行情况。Lightning 草稿可以主动丢弃。

单项目迁移使用研究 CLI 的 `bundle create` / `bundle restore`，恢复到新目录后先运行 `doctor` 并核对来源连接。bundle 包含研究图、工作历史、检索队列和已登记附件，不包含外部代码、凭据与 Codex 对话。保留所有项目、Brainstorming 空间和 giver 谱系时，应备份**整个工作区**。

从仓库根目录可查看本地 CLI 帮助：

```bash
python3 plugins/vibe-research/runtime/bin/vr --help
python3 plugins/vibe-research/runtime/bin/giver --help
python3 plugins/vibe-research/scripts/companion.py --workspace ~/VibeResearch --check
```

伴侣还支持 `--status`、`--toggle`、`--stop`。高级流程见 [Agent 管理流程](plugins/vibe-research/runtime/docs/AGENT_WORKFLOW.md)、[数据库连接](plugins/vibe-research/runtime/docs/DATABASE_CONNECTIONS.md) 和 [运行时说明](plugins/vibe-research/runtime/README.md)。更新与卸载见 [INSTALL.md](INSTALL.md#更新与卸载)。

源码仓库不包含使用者的研究项目、数据库密钥、聊天记录或本机验证材料。社区技能来源与许可见 [技能许可](plugins/vibe-research/runtime/skills/LICENSE.md) 和 [来源说明](plugins/vibe-research/runtime/docs/COMMUNITY_SKILLS.md)。

## 构建与发布

[跨平台工作流](.github/workflows/build-companions.yml) 检查运行时与平台入口，构建 Windows x64/arm64 伴侣并组装安装包；推送 `v*` 标签后发布对应 Release。源码版本、CI 构建产物和 Release 标签应分别核对。仅通过源码检查不代表已在所有桌面环境完成实际运行验证。
