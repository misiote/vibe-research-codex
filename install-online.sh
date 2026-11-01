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
"$vr_python" -c 'import sys, urllib.request
with urllib.request.urlopen("https://raw.githubusercontent.com/misiote/vibe-research-codex/main/scripts/bootstrap.py", timeout=60) as response:
    data = response.read()
with open(sys.argv[1], "wb") as target:
    target.write(data)
' "$vr_bootstrap"

"$vr_python" "$vr_bootstrap" "$@"
