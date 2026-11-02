#!/bin/sh
# Download the bootstrap first; never execute a partial network response.
set -eu
umask 077
unset VIBE_RESEARCH_MANAGED_PYTHON
if [ -n "${VIBE_RESEARCH_PYTHON:-}" ]; then
  vr_python=$VIBE_RESEARCH_PYTHON
elif [ "$(uname -s)" = Darwin ]; then
  vr_macos_major=$(sw_vers -productVersion | cut -d . -f 1)
  if [ "$vr_macos_major" -lt 12 ]; then
    echo "此安装包需要 macOS 12 或更高版本，以及可用的 Codex App。" >&2
    exit 1
  fi
  # macOS ships python3/git stubs that can open the developer tools installer.
  # Never probe those: use a checksum-pinned, relocatable private interpreter.
  case "$(uname -m)" in
    arm64) vr_arch=aarch64; vr_python_sha=fbf4afef53c2a6b72bb741bc06d5671a9dfaf87bd84e5aa73ac9b3d0d589f14e ;;
    x86_64) vr_arch=x86_64; vr_python_sha=a962e47df522889eaa7ff0d6a56203f1079f68aabb65ffdbe8455f362bc769f3 ;;
    *) echo "不支持此 Mac 架构。" >&2; exit 1 ;;
  esac
  export VIBE_RESEARCH_MANAGED_PYTHON=1
  vr_runtime_parent=${VIBE_RESEARCH_RUNTIME_DIR:-$HOME/.local/share/vibe-research/runtimes}
  vr_runtime="$vr_runtime_parent/cpython-3.12.16-20261026-$vr_arch"
  vr_python="$vr_runtime/python/bin/python3"
  if [ ! -x "$vr_python" ] || [ ! -f "$vr_runtime/.distribution-sha256" ] || [ "$(cat "$vr_runtime/.distribution-sha256")" != "$vr_python_sha" ]; then
    if [ -e "$vr_runtime" ]; then
      echo "专用运行时目录不完整或已修改，请保留原目录并设置新的 VIBE_RESEARCH_RUNTIME_DIR 后重试：$vr_runtime" >&2
      exit 1
    fi
    mkdir -p "$vr_runtime_parent"
    vr_runtime_lock="$vr_runtime.lock"
    if ! mkdir "$vr_runtime_lock" 2>/dev/null; then
      echo "另一个运行时安装正在进行。若上次被强制结束，请确认无安装进程后移除：$vr_runtime_lock" >&2
      exit 1
    fi
    vr_runtime_stage=$(mktemp -d "$vr_runtime_parent/.download.XXXXXXXX")
    trap 'rm -rf "$vr_runtime_stage"; rmdir "$vr_runtime_lock" 2>/dev/null || true' EXIT
    trap 'exit 130' HUP INT TERM
    echo "准备 Mac 专用 Python（无需 Homebrew、系统 Python 或开发工具）…"
    vr_python_url="https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.12.16%2B20261026-$vr_arch-apple-darwin-install_only.tar.gz"
    vr_runtime_download="$vr_runtime_parent/cpython-3.12.16-20261026-$vr_arch.tar.gz.part"
    vr_attempt=0
    vr_cached_sha=""
    if [ -f "$vr_runtime_download" ]; then
      vr_cached_sha=$(shasum -a 256 "$vr_runtime_download" | awk '{print $1}')
    fi
    if [ "$vr_cached_sha" != "$vr_python_sha" ]; then
    while ! curl --fail --location --progress-bar --show-error --connect-timeout 15 --max-time 300 --speed-time 60 --speed-limit 1024 --continue-at - --proto '=https' --proto-redir '=https' "$vr_python_url" -o "$vr_runtime_download"; do
      vr_attempt=$((vr_attempt + 1))
      if [ "$vr_attempt" -ge 3 ]; then
        echo "Python 下载未完成；已保留可续传文件，重新运行安装命令会继续下载。" >&2
        exit 1
      fi
      echo "下载中断，继续已有进度（$vr_attempt/3）…" >&2
    done
    fi
    if ! printf '%s  %s\n' "$vr_python_sha" "$vr_runtime_download" | shasum -a 256 -c -; then
      rm -f "$vr_runtime_download"
      echo "Python 下载校验失败，已移除不完整文件；不会运行未经校验的程序。" >&2
      exit 1
    fi
    tar -xzf "$vr_runtime_download" -C "$vr_runtime_stage"
    "$vr_runtime_stage/python/bin/python3" -I -c 'import ssl,sqlite3,ctypes,venv,zlib; import sys; assert sys.version_info[:2] == (3,12)'
    printf '%s\n' "$vr_python_sha" > "$vr_runtime_stage/.distribution-sha256"
    mv "$vr_runtime_stage" "$vr_runtime"
    rm -f "$vr_runtime_download"
    rmdir "$vr_runtime_lock"
    trap - EXIT HUP INT TERM
  fi
elif command -v python3 >/dev/null 2>&1; then
  vr_python=python3
elif command -v python >/dev/null 2>&1; then
  vr_python=python
else
  echo "此平台请先安装 Python 3.9+，然后重试。" >&2
  exit 1
fi
export VIBE_RESEARCH_PYTHON="$vr_python"
# Prevent unrelated user Python packages or environment settings from leaking in.
unset PYTHONHOME PYTHONPATH PYTHONPYCACHEPREFIX
export PYTHONNOUSERSITE=1
"$vr_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,9) else "需要 Python 3.9+")'
vr_bootstrap=$(mktemp "${TMPDIR:-/tmp}/vibe-research-install.XXXXXXXX")
trap 'rm -f "$vr_bootstrap"' EXIT
trap 'exit 130' HUP INT TERM
"$vr_python" -c 'import sys, time, urllib.request
with urllib.request.urlopen("https://raw.githubusercontent.com/misiote/vibe-research-codex/main/scripts/bootstrap.py?t=" + str(time.time_ns()), timeout=60) as response:
    data = response.read()
with open(sys.argv[1], "wb") as target:
    target.write(data)
' "$vr_bootstrap"

"$vr_python" "$vr_bootstrap" "$@"
