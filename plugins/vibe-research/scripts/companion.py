#!/usr/bin/env python3
"""Launch the native Vibe Research companion for the current desktop OS."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--title", default="Vibe Research · 研究现场")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--stop", action="store_true")
    mode.add_argument("--toggle", action="store_true")
    return parser.parse_args()


def host_platform():
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return "unsupported"


def process_alive(pid):
    if not isinstance(pid, int) or pid <= 1:
        return False
    if sys.platform == "win32":
        import ctypes

        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return False
        ctypes.windll.kernel32.CloseHandle(process)
        return True
    try:
        os.kill(pid, 0)
    except PermissionError:
        return None
    except OSError:
        return False
    return True


def load_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def run(command, **kwargs):
    return subprocess.run(command, text=True, capture_output=True, **kwargs)


def check_host(plugin, host):
    if host == "macos":
        source = plugin / "scripts" / "companion" / "macos" / "main.m"
        clang = shutil.which("clang")
        ok = source.is_file() and bool(clang)
        return {
            "ok": ok,
            "platform": host,
            "entry": str(source),
            "detail": "AppKit/WebKit 与 clang 已就绪" if ok else "需要 macOS clang（安装 Xcode Command Line Tools）",
        }
    if host == "linux":
        source = plugin / "scripts" / "companion" / "linux" / "main.py"
        python = os.environ.get("VR_COMPANION_PYTHON") or shutil.which("python3") or sys.executable
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return {
                "ok": False,
                "platform": host,
                "entry": str(source),
                "detail": "未检测到 Linux 图形桌面；CLI/SSH 环境请使用浏览器工作台",
            }
        completed = run([python, str(source), "--check"])
        detail = completed.stdout.strip() if completed.returncode == 0 else completed.stderr.strip()
        return {"ok": completed.returncode == 0, "platform": host, "entry": str(source), "detail": detail}
    if host == "windows":
        rid = windows_rid()
        packaged = windows_packaged_binary(plugin, rid)
        dotnet = shutil.which("dotnet")
        ok = packaged.is_file() or bool(dotnet)
        detail = (
            "已找到随包研究伴侣"
            if packaged.is_file()
            else "可用 .NET 8 SDK 首次构建研究伴侣"
            if dotnet
            else "安装包缺少对应 Windows 伴侣；请使用 GitHub Release 完整包，或安装 .NET 8 SDK"
        )
        return {"ok": ok, "platform": host, "entry": str(packaged), "runtime": rid, "detail": detail}
    return {"ok": False, "platform": host, "detail": "此系统尚未提供悬浮研究伴侣"}


def build_macos_app(source, app_path):
    output = app_path / "Contents" / "MacOS" / "VibeResearchCompanion"
    resources = app_path / "Contents" / "Resources"
    output.parent.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    module_cache = output.parent / "module-cache"
    module_cache.mkdir(parents=True, exist_ok=True)
    environment["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
    completed = run(
        ["clang", str(source), "-O", "-fobjc-arc", "-framework", "Cocoa", "-framework", "QuartzCore", "-framework", "WebKit", "-o", str(output)],
        env=environment,
    )
    if completed.returncode:
        detail = completed.stderr.strip().splitlines()
        raise RuntimeError("研究伴侣编译失败：" + (detail[-1] if detail else "clang 返回错误"))
    plist = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\"><dict>
<key>CFBundleDevelopmentRegion</key><string>zh_CN</string>
<key>CFBundleExecutable</key><string>VibeResearchCompanion</string>
<key>CFBundleIdentifier</key><string>local.viberesearch.companion</string>
<key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
<key>CFBundleName</key><string>Vibe Research Companion</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.4.1</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSMinimumSystemVersion</key><string>12.0</string>
<key>LSUIElement</key><true/>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>\n"""
    (app_path / "Contents" / "Info.plist").write_text(plist, encoding="utf-8")


def windows_rid():
    machine = platform.machine().lower()
    return "win-arm64" if machine in {"arm64", "aarch64"} else "win-x64"


def windows_packaged_binary(plugin, rid):
    return plugin / "scripts" / "companion" / "windows" / "publish" / rid / "VibeResearchCompanion.exe"


def build_windows_app(plugin, runtime, rid):
    packaged = windows_packaged_binary(plugin, rid)
    if packaged.is_file():
        return packaged
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError("安装包缺少对应 Windows 研究伴侣。请改用 GitHub Release 完整包，或安装 .NET 8 SDK 后重试。")
    project = plugin / "scripts" / "companion" / "windows" / "VibeResearchCompanion.csproj"
    digest = hashlib.sha256(project.read_bytes()).hexdigest()[:16]
    output = runtime / "bin" / digest / rid
    binary = output / "VibeResearchCompanion.exe"
    if binary.is_file():
        return binary
    completed = run(
        [
            dotnet,
            "publish",
            str(project),
            "-c",
            "Release",
            "-r",
            rid,
            "--self-contained",
            "true",
            "-p:PublishSingleFile=true",
            "-p:IncludeNativeLibrariesForSelfExtract=true",
            "-o",
            str(output),
        ]
    )
    if completed.returncode or not binary.is_file():
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError("Windows 研究伴侣构建失败：" + (detail.splitlines()[-1] if detail else "dotnet 返回错误"))
    return binary


def ensure_workbench(plugin, workspace, port):
    completed = run(
        [sys.executable, str(plugin / "scripts" / "workbench.py"), "--workspace", str(workspace), "--port", str(port), "--no-open"]
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "工作台服务启动失败")
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("工作台启动器没有返回地址")
    return lines[-1]


def wait_for_pid(pid_file_path):
    for _ in range(50):
        try:
            pid = int(pid_file_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            time.sleep(0.1)
            continue
        if process_alive(pid) is not False:
            return pid
        time.sleep(0.1)
    return None


def launch_macos(plugin, runtime, url, title, ui_state_path, pid_file_path, log_path):
    source = plugin / "scripts" / "companion" / "macos" / "main.m"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    app_path = runtime / "bin" / digest / "Vibe Research Companion.app"
    binary = app_path / "Contents" / "MacOS" / "VibeResearchCompanion"
    if not binary.is_file():
        build_macos_app(source, app_path)
    launched = run(
        [
            "/usr/bin/open",
            "-n",
            str(app_path),
            "--args",
            "--url",
            url,
            "--title",
            title,
            "--ui-state",
            str(ui_state_path),
            "--pid-file",
            str(pid_file_path),
        ],
        stdin=subprocess.DEVNULL,
    )
    if launched.returncode:
        raise RuntimeError("研究伴侣未能交给 macOS 启动：" + (launched.stderr.strip() or str(log_path)))
    return str(app_path)


def cleanup_legacy_macos_companions():
    """Retire the pre-0.4 raw helper, which had no PID/lock protocol."""
    try:
        subprocess.run(
            ["/usr/bin/killall", "vr-companion"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def launch_linux(plugin, url, title, ui_state_path, pid_file_path, log_path):
    source = plugin / "scripts" / "companion" / "linux" / "main.py"
    python = os.environ.get("VR_COMPANION_PYTHON") or shutil.which("python3") or sys.executable
    check = run([python, str(source), "--check"])
    if check.returncode:
        raise RuntimeError(check.stderr.strip() or "Linux 研究伴侣依赖检查失败")
    log_handle = log_path.open("ab")
    subprocess.Popen(
        [python, str(source), "--url", url, "--title", title, "--ui-state", str(ui_state_path), "--pid-file", str(pid_file_path)],
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=log_handle,
        start_new_session=True,
        close_fds=True,
    )
    log_handle.close()
    return str(source)


def launch_windows(plugin, runtime, url, title, ui_state_path, pid_file_path, control_path, log_path):
    binary = build_windows_app(plugin, runtime, windows_rid())
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    log_handle = log_path.open("ab")
    subprocess.Popen(
        [str(binary), "--url", url, "--title", title, "--ui-state", str(ui_state_path), "--pid-file", str(pid_file_path), "--control-file", str(control_path)],
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=log_handle,
        creationflags=creationflags,
        close_fds=True,
    )
    log_handle.close()
    return str(binary)


def main():
    args = parse_args()
    plugin = Path(__file__).resolve().parents[1]
    workspace = Path(args.workspace).expanduser().resolve()
    runtime = workspace / ".vibe-research" / "companion"
    identity = hashlib.sha256(str(workspace).encode()).hexdigest()[:12]
    state_path = runtime / (identity + ".json")
    ui_state_path = runtime / (identity + ".ui.json")
    pid_file_path = runtime / (identity + ".pid")
    control_path = runtime / (identity + ".control")
    log_path = runtime / "companion.log"
    host = host_platform()
    state = load_state(state_path)
    try:
        pid_file_matches = int(pid_file_path.read_text(encoding="utf-8").strip()) == state.get("pid")
    except (OSError, ValueError):
        pid_file_matches = False
    alive = pid_file_matches and process_alive(state.get("pid")) is not False

    if args.check:
        result = check_host(plugin, host)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ok"] else 1
    if args.status:
        print(json.dumps({**state, "supported": host != "unsupported", "platform": host, "running": alive, "ui": load_state(ui_state_path)}, ensure_ascii=False))
        return 0
    if args.stop:
        if host == "macos":
            cleanup_legacy_macos_companions()
        if alive:
            os.kill(state["pid"], signal.SIGTERM)
        state_path.unlink(missing_ok=True)
        control_path.unlink(missing_ok=True)
        print(json.dumps({"running": False, "stopped": alive, "platform": host}, ensure_ascii=False))
        return 0
    if args.toggle:
        if not alive:
            raise RuntimeError("研究伴侣尚未运行。")
        if host == "windows":
            write_state(control_path, time.time_ns())
        else:
            os.kill(state["pid"], signal.SIGUSR1)
        time.sleep(0.45)
        print(json.dumps({"running": True, "pid": state["pid"], "platform": host, "ui": load_state(ui_state_path)}, ensure_ascii=False))
        return 0
    if host == "unsupported":
        raise RuntimeError("此系统尚未提供悬浮研究伴侣；工作台仍可在浏览器中使用。")

    if host == "macos":
        cleanup_legacy_macos_companions()

    readiness = check_host(plugin, host)
    if not readiness["ok"]:
        raise RuntimeError(readiness["detail"])
    url = ensure_workbench(plugin, workspace, args.port)
    if alive:
        state["checked_at"] = int(time.time())
        state["url"] = url
        write_state(state_path, state)
        print(json.dumps({"running": True, "started": False, "platform": host, "pid": state["pid"], "url": url}, ensure_ascii=False))
        return 0

    runtime.mkdir(parents=True, exist_ok=True)
    pid_file_path.unlink(missing_ok=True)
    control_path.unlink(missing_ok=True)
    if host == "macos":
        entry = launch_macos(plugin, runtime, url, args.title, ui_state_path, pid_file_path, log_path)
    elif host == "linux":
        entry = launch_linux(plugin, url, args.title, ui_state_path, pid_file_path, log_path)
    else:
        entry = launch_windows(plugin, runtime, url, args.title, ui_state_path, pid_file_path, control_path, log_path)
    pid = wait_for_pid(pid_file_path)
    if pid is None:
        raise RuntimeError("研究伴侣未确认启动，请查看 " + str(log_path))
    payload = {
        "pid": pid,
        "url": url,
        "workspace": str(workspace),
        "platform": host,
        "entry": entry,
        "started_at": int(time.time()),
        "checked_at": int(time.time()),
    }
    write_state(state_path, payload)
    print(json.dumps({"running": True, "started": True, "platform": host, "pid": pid, "url": url}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc))
