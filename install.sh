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

if ! "$vr_python" "$vr_share_root/plugins/vibe-research/scripts/companion.py" --workspace "${VIBE_RESEARCH_WORKSPACE:-$HOME/VibeResearch}" --check; then
  echo "悬浮研究伴侣尚未就绪；浏览器工作台仍可使用。按 INSTALL.md 补齐本系统依赖后重试。" >&2
fi

echo "Vibe Research 已安装。重启 ChatGPT/Codex 后可点击插件默认提示；终端可运行 vr-workbench。"
