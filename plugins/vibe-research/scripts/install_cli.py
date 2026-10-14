#!/usr/bin/env python3
"""Install a stable cross-platform ``vr-workbench`` user command."""
import argparse
import json
import os
import stat
import sys
from pathlib import Path


def default_config_dir():
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "VibeResearch"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vibe-research"


def default_bin_dir():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "VibeResearch/bin"
    return Path.home() / ".local/bin"


def shell_quote(value):
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def launcher_source(config_file, fallback_root):
    return '''#!/usr/bin/env python3
import argparse,json,os,subprocess,sys
from pathlib import Path

CONFIG=Path(%s)
FALLBACK_ROOT=Path(%s)

def settings():
    try:
        data=json.loads(CONFIG.read_text(encoding="utf8"))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):
        return {}

def plugin_root(data):
    roots=[]
    for value in (os.environ.get("VIBE_RESEARCH_PLUGIN_ROOT"),data.get("plugin_root"),str(FALLBACK_ROOT)):
        if value: roots.append(Path(value).expanduser())
    roots.append(Path.home()/"plugins/vibe-research")
    cache=Path.home()/".codex/plugins/cache"
    if cache.is_dir():
        roots.extend(sorted(cache.glob("*/vibe-research/*"),key=lambda p:p.stat().st_mtime,reverse=True))
    seen=set()
    for root in roots:
        try: root=root.resolve()
        except OSError: continue
        if root in seen: continue
        seen.add(root)
        if (root/"scripts/workbench.py").is_file(): return root
    raise SystemExit("没有找到已安装的 Vibe Research 插件；请先安装或更新插件。")

def main():
    data=settings()
    parser=argparse.ArgumentParser(description="启动或复用 Vibe Research 本机工作台")
    parser.add_argument("--workspace")
    parser.add_argument("--port",type=int)
    parser.add_argument("--no-open",action="store_true")
    parser.add_argument("--show-config",action="store_true")
    args=parser.parse_args()
    workspace=Path(args.workspace or data.get("workspace") or Path.home()/"VibeResearch").expanduser().resolve()
    port=args.port or int(data.get("port",8766))
    root=plugin_root(data)
    if args.show_config:
        print(json.dumps({"workspace":str(workspace),"port":port,"plugin_root":str(root)},ensure_ascii=False,indent=2))
        return
    command=[sys.executable,str(root/"scripts/workbench.py"),"--workspace",str(workspace),"--port",str(port)]
    if args.no_open: command.append("--no-open")
    raise SystemExit(subprocess.call(command))

if __name__=="__main__": main()
''' % (repr(str(config_file)), repr(str(fallback_root)))


def main():
    parser = argparse.ArgumentParser(description="安装 vr-workbench 用户命令")
    parser.add_argument("--workspace", default=os.environ.get("VIBE_RESEARCH_WORKSPACE") or str(Path.home() / "VibeResearch"))
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--bin-dir")
    parser.add_argument("--config-dir")
    args = parser.parse_args()

    plugin_root = Path(__file__).resolve().parents[1]
    workspace = Path(args.workspace).expanduser().resolve()
    bin_dir = Path(args.bin_dir).expanduser().resolve() if args.bin_dir else default_bin_dir()
    config_dir = Path(args.config_dir).expanduser().resolve() if args.config_dir else default_config_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "launcher.json"
    config_file.write_text(json.dumps({"workspace": str(workspace), "port": args.port, "plugin_root": str(plugin_root)}, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    helper = bin_dir / "vr-workbench.py"
    helper.write_text(launcher_source(config_file, plugin_root), encoding="utf8")
    if os.name == "nt":
        command = bin_dir / "vr-workbench.cmd"
        python = str(Path(sys.executable).resolve()).replace("%", "%%")
        command.write_text('@echo off\r\n"' + python + '" "%~dp0vr-workbench.py" %*\r\n', encoding="utf8")
    else:
        command = bin_dir / "vr-workbench"
        command.write_text("#!/bin/sh\nexec " + shell_quote(Path(sys.executable).resolve()) + " " + shell_quote(helper) + ' "$@"\n', encoding="utf8")
        command.chmod(command.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    on_path = str(bin_dir) in os.environ.get("PATH", "").split(os.pathsep)
    print(json.dumps({"command": str(command), "workspace": str(workspace), "config": str(config_file), "on_path": on_path}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
