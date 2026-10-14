#!/bin/sh
set -eu

vr_share_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v codex >/dev/null 2>&1; then
  vr_codex_bin=$(command -v codex)
elif [ -x "/Applications/ChatGPT.app/Contents/Resources/codex" ]; then
  vr_codex_bin="/Applications/ChatGPT.app/Contents/Resources/codex"
else
  echo "没有找到 Codex CLI。请先安装或更新 Codex，然后确认 codex 在 PATH 中。" >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  vr_python=python3
elif command -v python >/dev/null 2>&1; then
  vr_python=python
else
  echo "没有找到 Python 3.9+。请先安装 Python。" >&2
  exit 1
fi

"$vr_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else "需要 Python 3.9 或更高版本")'
"$vr_codex_bin" plugin marketplace add "$vr_share_root"
"$vr_codex_bin" plugin add vibe-research@vibe-research-local
"$vr_python" "$vr_share_root/plugins/vibe-research/scripts/install_cli.py" --workspace "${VIBE_RESEARCH_WORKSPACE:-$HOME/VibeResearch}"
vr_workspace=${VIBE_RESEARCH_WORKSPACE:-$HOME/VibeResearch}

if ! "$vr_python" "$vr_share_root/plugins/vibe-research/scripts/companion.py" --workspace "${VIBE_RESEARCH_WORKSPACE:-$HOME/VibeResearch}" --check; then
  echo "悬浮研究伴侣尚未就绪；浏览器工作台仍可使用。按 INSTALL.md 补齐本系统依赖后重试。" >&2
fi

echo "Vibe Research 已作为 Codex 插件安装并启用。"
echo "下一步："
echo "1. 用 Command-Q 完全退出 ChatGPT/Codex，再重新打开。"
echo "2. 在插件目录的 Vibe Research 来源中确认插件显示为已安装。"
echo "3. 把 $vr_workspace 添加为 Codex 本地项目，并在该项目中新建聊天。"
echo "4. 点击插件默认提示，或发送“打开 Vibe Research 工作台”。"
echo "研究伴侣会在这次对话开始后出现；终端也可运行 vr-workbench。"
