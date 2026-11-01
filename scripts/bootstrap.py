#!/usr/bin/env python3
# coding: utf-8
"""Download an immutable GitHub snapshot and run the user-level installer."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = 'misiote/vibe-research-codex'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'vibe-research-installer', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(100 * 1024 * 1024 + 1)
    if len(data) > 100 * 1024 * 1024:
        raise ValueError('下载超过大小限制。')
    return data


def unpack(data, destination):
    """Validate every member before extracting, including ZIP symlinks."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 5000 or sum(m.file_size for m in members) > 200 * 1024 * 1024:
            raise ValueError('安装包超过解压限制。')
        roots = set()
        for member in members:
            path = PurePosixPath(member.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in member.filename or ':' in member.filename or not path.parts:
                raise ValueError('安装包路径无效。')
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('安装包不允许符号链接。')
            roots.add(path.parts[0])
        if len(roots) != 1:
            raise ValueError('安装包根目录无效。')
        archive.extractall(destination)
    root = destination / roots.pop()
    plugin = root / 'plugins/vibe-research'
    for required in ['install.sh', 'install.ps1', '.agents/plugins/marketplace.json', 'plugins/vibe-research/scripts/install_modes.py']:
        if not (root / required).is_file():
            raise ValueError('安装包缺少文件：' + required)
    checks = json.loads((plugin / 'SHA256SUMS.json').read_text(encoding='utf8'))
    for name, digest in checks.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
            raise ValueError('校验清单路径无效。')
        if hashlib.sha256(plugin.joinpath(*path.parts).read_bytes()).hexdigest() != digest:
            raise ValueError('工具文件校验失败：' + name)
    return root


def default_directory():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'VibeResearch/installations'
    return Path.home() / '.local/share/vibe-research/installations'


def preflight():
    if sys.version_info < (3, 9):
        raise ValueError('需要 Python 3.9 或更高版本。')
    candidates = [shutil.which('codex')]
    if sys.platform == 'darwin':
        base = Path('/Applications/ChatGPT.app/Contents/Resources')
        candidates += [str(base / 'codex-cli/CodexCLI.app/Contents/MacOS/codex'), str(base / 'codex')]
    if os.name == 'nt':
        candidates += [str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/OpenAI/Codex/bin/codex.exe')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise ValueError('请先安装或更新 Codex，并确保 codex 可用；详见 INSTALL.md。')


def prepare_marketplace(codex, target):
    listing = json.loads(subprocess.check_output([codex, 'plugin', 'marketplace', 'list', '--json']))
    for item in listing.get('marketplaces', []):
        if item.get('name') != 'vibe-research-local' or Path(item['root']).resolve() == target.resolve():
            continue
        previous = Path(item['root'])
        catalog = json.loads((previous / '.agents/plugins/marketplace.json').read_text(encoding='utf8'))
        entries = catalog.get('plugins', [])
        manifest = json.loads((previous / 'plugins/vibe-research/.codex-plugin/plugin.json').read_text(encoding='utf8'))
        if len(entries) != 1 or entries[0].get('name') != 'vibe-research' or manifest.get('repository', '').removesuffix('.git') != 'https://github.com/' + REPOSITORY:
            raise ValueError('同名 marketplace 不是本仓库的独立来源；请先手动处理来源冲突。')
        print('更新本仓库的 marketplace 来源，研究数据保持原位。', flush=True)
        subprocess.run([codex, 'plugin', 'marketplace', 'remove', 'vibe-research-local'], check=True)
        return previous
    return None


def install(directory, workspace, ref='main', aliases=True):
    codex = preflight()
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / '.install-lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('已有安装正在进行。如上次安装被强制中断，请确认无安装进程后移除 ' + str(lock))
    try:
        print('1/4 获取 GitHub 版本…', flush=True)
        metadata = json.loads(fetch('https://api.github.com/repos/' + REPOSITORY + '/commits/' + urllib.parse.quote(ref, safe='')))
        commit = metadata.get('sha', '')
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('GitHub 返回的版本标识无效。')
        print('2/4 下载并校验 ' + commit[:12] + '…', flush=True)
        data = fetch('https://codeload.github.com/' + REPOSITORY + '/zip/' + commit)
        with tempfile.TemporaryDirectory(prefix='.download-', dir=str(directory)) as temp:
            extracted = unpack(data, Path(temp))
            # Keep existing installations intact. Only reuse an identical source snapshot.
            target = directory / commit
            if target.exists():
                identical = all((target / p.relative_to(extracted)).is_file() and (target / p.relative_to(extracted)).read_bytes() == p.read_bytes() for p in extracted.rglob('*') if p.is_file())
                if not identical:
                    raise ValueError('同版本安装目录包含修改；为保留文件，请使用 --install-dir 选择新目录。')
            else:
                extracted.rename(target)
        print('3/4 安装 Codex 插件与工作台入口…', flush=True)
        env = dict(os.environ, VIBE_RESEARCH_WORKSPACE=str(Path(workspace).expanduser().resolve()), VIBE_RESEARCH_PYTHON=sys.executable)
        if os.name == 'nt':
            command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(target / 'install.ps1')]
        else:
            command = ['sh', str(target / 'install.sh')]
        previous = prepare_marketplace(codex, target)
        try:
            subprocess.run(command, env=env, check=True)
        except (OSError, subprocess.CalledProcessError):
            if previous:
                subprocess.run([codex, 'plugin', 'marketplace', 'remove', 'vibe-research-local'], env=env)
                subprocess.run([codex, 'plugin', 'marketplace', 'add', str(previous)], env=env)
            raise
        print('4/4 配置显式命令入口…', flush=True)
        alias_status = 'skipped'
        if aliases:
            result = subprocess.run([sys.executable, str(target / 'plugins/vibe-research/scripts/install_modes.py'), '--install'], env=env)
            alias_status = 'installed' if result.returncode == 0 else 'conflict'
            if result.returncode:
                print('插件已安装；短入口注册失败，已有技能保持不变。请从插件技能菜单使用入口。', file=sys.stderr)
        receipt = {'repository': REPOSITORY, 'commit': commit, 'source': str(target), 'workspace': env['VIBE_RESEARCH_WORKSPACE'], 'aliases': alias_status}
        (directory / 'installed.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print('\n安装完成。请完全退出并重启 Codex，再将研究工作区添加为本地项目：\n' + receipt['workspace'])
        print('工作台终端入口：vr-workbench（Windows 为 vr-workbench.cmd）。')
        return receipt
    finally:
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-dir', default=str(default_directory()))
    parser.add_argument('--workspace', default=os.environ.get('VIBE_RESEARCH_WORKSPACE', str(Path.home() / 'VibeResearch')))
    parser.add_argument('--ref', default='main', help='GitHub branch, tag or commit; resolved to an immutable commit before download')
    parser.add_argument('--no-aliases', action='store_true')
    args = parser.parse_args()
    try:
        install(args.install_dir, args.workspace, args.ref, not args.no_aliases)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print('安装未完成：' + str(exc) + '\n请按 README / INSTALL.md 的手动安装方式重试。', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
