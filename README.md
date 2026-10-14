# Vibe Research for Codex

Vibe Research 把文献检索、全文精读、研究关系图、过程记录和研究交接放进同一个 Codex 项目。进入已绑定的研究项目后，助手会确保一个收起的悬浮研究伴侣存在；用户点击它时才展开工作台。

## 安装入口

| 平台 | 安装 | 悬浮入口实现 |
| --- | --- | --- |
| [macOS](#macos) | 双击 `安装Vibe Research.command` | AppKit + WebKit |
| [Windows](#windows) | 双击 `install-windows.cmd` | WinForms + WebView2 |
| [Linux](#linux) | 运行 `./install.sh` | GTK 3 + WebKitGTK |

完整说明见 [INSTALL.md](INSTALL.md)。三端共享研究库、工作台和启动协议，平台代码分别位于：

```text
plugins/vibe-research/scripts/companion/
├── macos/main.m
├── windows/Program.cs
└── linux/main.py
```

`plugins/vibe-research/scripts/companion.py` 是统一分发器，负责预检、启动、状态查询、展开/收起和退出。三端改动可以独立构建，研究数据格式不随桌面实现分叉。

## macOS

1. 下载并解压 GitHub Release 完整包。
2. 双击 `安装Vibe Research.command`。
3. 安装结束后用 `Command-Q` 完全退出 ChatGPT/Codex，再重新打开。
4. 打开插件目录，在来源 **Vibe Research** 下确认插件显示为已安装。
5. 把安装器显示的研究工作区（默认 `~/VibeResearch`）添加为 Codex 本地项目。
6. 在这个项目中新建聊天，点击插件默认提示，或发送“打开 Vibe Research 工作台”。
7. 插件接手对话后会唤起收起的研究伴侣；点击它打开工作台。

系统需要 Python 3.9+；首次构建悬浮入口需要 Xcode Command Line Tools 提供的 `clang`。

安装器会调用 Codex App 自带的 CLI，依次登记随包 marketplace、安装并启用 `vibe-research@vibe-research-local`，再建立默认研究工作区。Codex App 与 CLI 共用插件缓存，因此无需把脚本复制进 App 包。研究伴侣不是登录启动项，刚打开 App 时不会自行出现；它会在新的 Vibe Research 对话开始后由插件检查并唤起。

## Windows

1. 下载并解压 GitHub Release 完整包。
2. 双击 `install-windows.cmd`。
3. 重启 Codex，在 Vibe Research 项目中开始或继续对话。
4. 点击悬浮研究伴侣打开工作台。

Release 包预编译 x64 与 arm64 入口。系统需要 Python 3.9+ 和 Microsoft Edge WebView2 Runtime；Windows 10/11 通常已经具备 WebView2。直接使用源码且没有预编译程序时，需要 .NET 8 SDK 做首次构建。

## Linux

1. 下载并解压 GitHub Release 完整包。
2. 运行 `chmod +x install.sh && ./install.sh`。
3. 重启 Codex，在 Vibe Research 项目中开始或继续对话。
4. 点击悬浮研究伴侣打开工作台。

Debian/Ubuntu 的桌面依赖：

```bash
sudo apt install python3-cairo python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

纯终端、SSH 或没有图形桌面的主机会自动使用 `vr-workbench` 浏览器入口。WSLg 可使用 Linux 悬浮入口。

## 统一命令

macOS/Linux：

```bash
python3 plugins/vibe-research/scripts/companion.py --workspace ~/VibeResearch --check
python3 plugins/vibe-research/scripts/companion.py --workspace ~/VibeResearch
```

Windows：

```powershell
py -3 plugins\vibe-research\scripts\companion.py --workspace "$HOME\VibeResearch" --check
py -3 plugins\vibe-research\scripts\companion.py --workspace "$HOME\VibeResearch"
```

可追加 `--status`、`--toggle` 或 `--stop`。浏览器入口在三端均可使用：安装后运行 `vr-workbench`，Windows 也可运行 `vr-workbench.cmd`。

## 发布

`.github/workflows/build-companions.yml` 分别检查 macOS 和 Linux 实现、构建 Windows x64/arm64 程序，并组装包含三端代码的完整安装包。推送 `v*` 标签时，工作流会把 zip 附加到 GitHub Release。

macOS 伴侣已经过本机完整运行检查；Windows x64/arm64 由发布流程构建，Linux 入口由发布流程检查依赖与可执行性。首次迁移到新设备时，建议先建立一个空项目确认悬浮入口、工作台和本机数据库连接，再恢复正式研究项目。

## 数据边界

插件包不包含研究项目、数据库密钥、学校登录态或 Codex 对话。项目备份使用 `vr bundle create`；接收方恢复后先运行诊断和来源连接检查。数据库月预算是限制条件，不代表自动购买授权。
