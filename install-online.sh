#!/bin/sh
# Download the bootstrap first; never execute a partial network response.
set -eu
if command -v python3 >/dev/null 2>&1; then
  vr_python=python3
elif command -v python >/dev/null 2>&1; then
  vr_python=python
else
  echo "请先安装 Python 3.9+，然后重试。" >&2
  exit 1
fi
"$vr_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,9) else "需要 Python 3.9+")'
vr_bootstrap=$(mktemp "${TMPDIR:-/tmp}/vibe-research-install.XXXXXXXX")
trap 'rm -f "$vr_bootstrap"' EXIT HUP INT TERM
if command -v curl >/dev/null 2>&1; then
  curl --fail --silent --show-error --location --connect-timeout 15 --max-time 60 https://raw.githubusercontent.com/misiote/vibe-research-codex/main/scripts/bootstrap.py --output "$vr_bootstrap"
elif command -v wget >/dev/null 2>&1; then
  wget -q --timeout=60 --tries=1 https://raw.githubusercontent.com/misiote/vibe-research-codex/main/scripts/bootstrap.py -O "$vr_bootstrap"
else
  echo "请安装 curl 或 wget，或使用 README 的手动下载方式。" >&2
  exit 1
fi
"$vr_python" "$vr_bootstrap" "$@"
