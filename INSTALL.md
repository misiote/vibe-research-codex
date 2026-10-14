# Vibe Research 跨平台安装

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

安装器会使用 `/Applications/ChatGPT.app/Contents/Resources/codex`（或 `PATH` 中的 `codex`）登记随包 marketplace，并安装、启用 Vibe Research。安装完成后：

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

安装器先从 `PATH` 查找 `codex`，然后检查默认位置 `%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe`。Python 可由 `python` 或 `py -3` 提供。

GitHub Release 完整包内置 x64/arm64 研究伴侣；展开工作台依赖系统 WebView2 Runtime（Windows 10/11 通常已随 Edge 安装）。源码包缺少预编译程序时，可安装 .NET 8 SDK 让工具首次构建。首次迁移时先用空项目确认悬浮入口、工作台和本机数据库连接，再恢复正式研究数据。

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

## 分享研究项目

此安装包不包含你的研究项目、数据库凭据或 Codex 聊天记录。分享研究现场时，另用 `vr bundle create` 创建项目备份；接收方用 `vr bundle restore --destination <新目录>` 恢复。

项目 bundle 包含研究图、工作历史、检索队列和已登记附件，不包含外部代码仓库、数据库凭据或 Codex 任务。恢复后先运行 `doctor` 与连接检查，再继续工作。

## 更新与卸载

持续发布时建议把整个 marketplace 目录放到 GitHub 仓库。更新：

```text
codex plugin marketplace upgrade vibe-research-local
codex plugin add vibe-research@vibe-research-local
```

卸载：

```text
codex plugin remove vibe-research@vibe-research-local
codex plugin marketplace remove vibe-research-local
```

卸载插件不会删除使用者另行选择的研究工作区。
