# Vibe Research 跨平台安装

## 在线安装（推荐）

先安装支持 `codex plugin` 的 Codex 和 Python 3.9+。macOS / Linux 运行：

```bash
curl -fsSL https://raw.githubusercontent.com/misiote/vibe-research-codex/main/install-online.sh -o /tmp/vibe-research-install.sh && sh /tmp/vibe-research-install.sh
```

Windows PowerShell 运行：

```powershell
Invoke-WebRequest -UseBasicParsing https://raw.githubusercontent.com/misiote/vibe-research-codex/main/install-online.ps1 -OutFile "$env:TEMP\vibe-research-install.ps1"; if ($?) { powershell -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\vibe-research-install.ps1" }
```

这会下载完整源码到用户目录，调用随包安装器，再注册五个显式短入口；不需要 Git。结束后重启 Codex，将显示的研究工作区添加为本地项目。默认源码位置为 `~/.local/share/vibe-research/installations/<提交>`，Windows 为 `%LOCALAPPDATA%\VibeResearch\installations\<提交>`。工作区默认 `~/VibeResearch`，与源码目录分开。

安装器先检查 Codex / Python，再直接从 Codeload 下载指定分支、标签或提交的 ZIP；**不调用 GitHub REST API，不需要 GitHub Token**，因此不会因 API 查询版本的限流而中断。源码包包含提交标识时记录该提交；没有标识时按压缩包 SHA-256 保存，不冒充已解析提交。所有下载仍须通过解压路径和插件 SHA-256 校验。

**源码获取顺序：HTTPS → SSH。** Codeload 返回 HTTP 错误或网络不可达时，安装器尝试用本机 Git / OpenSSH 从 `git@github.com:misiote/vibe-research-codex.git` 获取同一个版本，并生成 ZIP，经过相同校验后安装。SSH 复用已有密钥、ssh-agent 与 SSH Host 配置，使用 `BatchMode=yes`、严格主机校验和连接超时；不索取密钥，不修改 `.ssh`，不自动接受未知主机。缺少 Git / SSH、密钥未授权或 GitHub 主机尚未受信任时，会分别显示 HTTPS 与 SSH 的失败原因。文件校验失败不会绕过校验或触发另一种下载方式。

最初下载安装入口和引导脚本仍需访问 `raw.githubusercontent.com`；下载源码优先访问 `codeload.github.com`，失败后使用已有 GitHub SSH 连接。若这些入口均不可达，请手动下载完整源码包或通过已有 Git / SSH 环境获取仓库，再运行随包安装器。

下载后的脚本可附加选项：

```bash
sh /tmp/vibe-research-install.sh --workspace ~/Research --no-aliases
sh /tmp/vibe-research-install.sh --ref main --install-dir ~/.local/share/vibe-research/installations
```

Windows 在 `-File` 后的脚本路径后追加同样选项。`--ref` 可指定分支、标签或提交；`--no-aliases` 跳过用户级短命令注册。在线安装自动使用找到的 Python；手动安装可通过 `VIBE_RESEARCH_PYTHON` 指定解释器。

若已通过本仓库手动安装，在线安装会核对原来源仅包含 Vibe Research，再更新其登记位置；不删除原源码和研究数据。遇到同名混合来源时会停止并提示处理，不移除其他插件来源。

再次执行在线命令会安装当前版本；保留旧源码和研究工作区，并在安装根目录写入 `installed.json` 记录本次提交与路径。安装失败时不要删除研究工作区；按错误提示补齐依赖后重试。已有源码被修改时不会覆盖，可用新的 `--install-dir`。若安装进程被强制终止，确认进程已退出后再清理报错指定的 `.install-lock` 目录。

系统依赖仍按下面的平台说明准备。安装器不会自动获取管理员权限、安装 Python / Codex、处理机构授权或重启应用。`vr-workbench` 的 bin 目录不在 PATH 时，按安装输出加入 PATH；也可直接调用输出的完整命令路径。

### 旧下载目录导致来源失效

如果报错包含 `vibe-research-local` 和 `marketplace root does not contain a supported manifest`，通常是旧安装目录被移动、删除或解压不完整。当前在线安装器会识别这条失效登记，通过 Codex CLI 移除它，再继续安装；不会删除旧目录、研究数据或其他插件。重新运行上面的在线安装命令即可。下载入口会为引导脚本使用独立请求参数，减少旧脚本缓存导致修复未生效的情况。

若旧 manifest 仍存在但无法读取，或失效的是其他 marketplace，安装器会停止并显示原因，保留原配置。确认只是 Vibe Research 的旧登记时，也可手动运行 `codex plugin marketplace remove vibe-research-local` 后重试；这只移除来源登记，不删除研究工作区。

## 获取当前版本

推荐克隆 `main`，或在 GitHub 的 Code 菜单选择 Download ZIP 后完整解压：

```bash
git clone https://github.com/misiote/vibe-research-codex.git
cd vibe-research-codex
```

Release 附件对应其标签版本，可能早于 `main`；下载前请核对版本。源码包不保证包含 Windows 预编译伴侣。保留安装目录在固定位置：启动器优先使用该目录中的工具，短命令别名也指向此目录。

## 共同要求

- Python 3.9 或更高版本。
- Codex CLI 可以在终端中运行；安装器会调用 `codex plugin marketplace add` 和 `codex plugin add`。
- 解压整个压缩包，保持 `.agents/`、`plugins/` 与安装脚本的相对位置。
- 安装后重启 ChatGPT/Codex。插件详情提供“打开 Vibe Research 工作台”的默认提示。macOS、Windows 和有图形桌面的 Linux 会在 Vibe Research 项目对话中唤起收起的悬浮研究伴侣，点击后才显示工作台。
- 安装器同时创建 `vr-workbench`（Windows 为 `vr-workbench.cmd`）终端命令，默认工作区是用户主目录下的 `VibeResearch`。可在安装前设置 `VIBE_RESEARCH_WORKSPACE` 改变位置。

## macOS

双击 `安装Vibe Research.command`。如果 Gatekeeper 阻止运行，在 Finder 中右键该文件并选择“打开”。

也可在终端运行：

```bash
sh install.sh
```

安装器优先使用 `PATH` 中的 `codex`，随后检查当前 ChatGPT App 的 `Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`，并兼容旧版 `Contents/Resources/codex`。它会登记随包 marketplace，并安装、启用 Vibe Research。安装完成后：

1. 用 `Command-Q` 完全退出 ChatGPT/Codex，然后重新打开；只关闭窗口不足以重新载入插件。
2. 打开插件目录，选择来源 **Vibe Research**，确认 Vibe Research 显示为已安装。
3. 把默认研究工作区 `~/VibeResearch` 添加为 Codex 本地项目；设置过 `VIBE_RESEARCH_WORKSPACE` 时使用对应目录。
4. 在该项目中新建聊天。点击插件默认提示，或发送“打开 Vibe Research 工作台”。
5. 插件开始处理这次对话后，收起的研究伴侣才会出现；点击伴侣显示研究现场。

插件代码安装到 Codex 的本机缓存，研究数据保存在独立工作区。研究伴侣不作为系统登录项运行，也不会在尚未使用插件的普通聊天中出现。

## Linux

在解压目录运行：

```bash
chmod +x install.sh
./install.sh
```

悬浮入口需要 GTK 3 和 WebKitGTK。Debian/Ubuntu 可安装：

```bash
sudo apt install python3-cairo python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

纯终端、SSH 或服务器环境继续使用 `vr-workbench` 浏览器入口。如果尚未安装 Codex CLI，可先按 OpenAI 官方说明安装。

## Windows 原生 PowerShell

双击 `install-windows.cmd`，或在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

安装器先从 `PATH` 查找 `codex`，然后检查默认位置 `%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe`。Python 可由 `python` 或 `py -3` 提供；也支持 `VIBE_RESEARCH_PYTHON` 指定解释器，并可检测 Codex 自带的 Python。解释器须为 3.9 或更高版本。

GitHub Release 完整包内置 x64/arm64 研究伴侣；展开工作台依赖系统 WebView2 Runtime（Windows 10/11 通常已随 Edge 安装）。源码包缺少预编译程序时，可安装 .NET 8 SDK 让工具首次构建。首次迁移时先用空项目确认悬浮入口、工作台和本机数据库连接，再恢复正式研究数据。

Windows 安装器还会创建 `vr-companion.cmd` 与 `vr.cmd`。在实际桌面的终端运行 `vr-companion.cmd` 可启动悬浮入口；点击展开/收起，按住拖动，右键重置位置或退出。`vr-companion.cmd --status` 的 `visible_to_user: true` 才表示入口位于当前用户桌面；Codex 隔离桌面中的启动会给出明确提示。`--show`、`--hide`、`--reset-position` 可控制已运行的入口。

Windows 工作台内置本地 PDF 阅读器，可翻页、缩放和查看本页文本；无需联网加载阅读器。新项目默认选择 arXiv、Crossref 和 OpenAlex，仍以实际连接检查结果为准。

## Windows + WSL

如果研究与 Codex 都在 WSL 内运行，按 Linux 方法安装，并把研究工作区放在 WSL 的 Linux 主目录，例如 `~/vibe-research-workspace`。WSLg 可使用 Linux 悬浮入口；没有图形桌面时使用浏览器入口。不要把同一个活动项目同时从 Windows 原生进程和 WSL 进程打开；跨环境接力请先暂停工作并使用项目 bundle。

## 第一次启动

安装器会建立默认研究工作区，并为新目录写入只启用 Vibe Research 的项目配置；已有 `.codex/config.toml` 时不会覆盖。工具代码和研究数据分离：更新或卸载插件不会删除另行选择的工作区。

也可以直接从终端进入：

```text
vr-workbench
```

它会启动或复用 `127.0.0.1:8766`，然后打开浏览器。`vr-workbench --no-open` 只启动并打印地址；`vr-workbench --show-config` 显示当前工作区。若终端尚未识别命令，请把安装器输出的 bin 目录加入 `PATH` 后重新打开终端。

首次数据库配置应在接收方自己的终端完成。macOS 默认使用系统钥匙串；Linux 与 Windows 优先使用环境变量，也可显式选择本机凭据文件。不要共享 API key、学校登录态或钥匙串内容。

## 可选：注册短命令

在仓库根目录执行，随后重启 App 或新建聊天：

```bash
python3 plugins/vibe-research/scripts/install_modes.py --install
```

Windows 将 `python3` 换成 `py -3`。这会注册 `/lightning`、`/brainstorming`、`/engineering`、`/giver`、`/vrpet` 五个显式原生 skill 入口；在命令/技能菜单中选择后输入需求。它们由 Codex 调度 skill，不是独立终端命令，也不依靠自由文本关键词分类。若宿主只显示带命名空间的名称，可从技能菜单选择对应入口。安装器遇到同名且不属于本插件的技能会拒绝覆盖。

## 分享研究项目

此安装包不包含你的研究项目、数据库凭据或 Codex 聊天记录。分享研究现场时，另用 `vr bundle create` 创建项目备份；接收方用 `vr bundle restore --destination <新目录>` 恢复。

完整迁移所有项目、Brainstorming 空间与 giver 版本关系时，请另外备份整个研究工作区；单项目 bundle 不等于整个工作区备份。

项目 bundle 包含研究图、工作历史、检索队列和已登记附件，不包含外部代码仓库、数据库凭据或 Codex 任务。恢复后先运行 `doctor` 与连接检查，再继续工作。

## 更新与卸载

在线安装用户直接重跑在线安装命令即可；也可用 `--ref` 安装指定版本。更新前建议备份研究工作区。

通过本仓库安装器安装的是**本地目录来源**。先备份研究工作区，在原安装目录更新后重跑安装器：

```bash
git pull --ff-only
sh install.sh
```

Windows 在更新后重跑 `install-windows.cmd`。ZIP 安装请将新包放到原固定目录，再运行安装器。重启 App，并在新聊天中核对插件版本；安装过短命令别名时重新执行下面的别名安装。

只有通过 `codex plugin marketplace add misiote/vibe-research-codex --ref main` 登记的 **Git 来源**，才用 `codex plugin marketplace upgrade vibe-research-local` 拉取远端快照，然后执行 `codex plugin add vibe-research@vibe-research-local`。仅登记 marketplace 不会创建 `vr-workbench` 或安装短命令别名；初次安装推荐使用完整安装器。

卸载：

```text
codex plugin remove vibe-research@vibe-research-local
codex plugin marketplace remove vibe-research-local
```

卸载插件不会删除使用者另行选择的研究工作区。

安装机制参考 [OpenAI 官方插件文档](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)。实际可用命令以本机 `codex plugin --help` 为准。
