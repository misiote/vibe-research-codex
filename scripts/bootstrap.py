#!/usr/bin/env python3
# coding: utf-8
"""Download a GitHub source snapshot without the REST API and run the user-level installer."""
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
    request = urllib.request.Request(url, headers={'User-Agent': 'vibe-research-installer', 'Accept': 'application/octet-stream'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(100 * 1024 * 1024 + 1)
    if len(data) > 100 * 1024 * 1024:
        raise ValueError('下载超过大小限制。')
    return data


def fetch_ssh(ref):
    git = shutil.which('git')
    if sys.platform == 'darwin' and git == '/usr/bin/git':
        developer = subprocess.run(['/usr/bin/xcode-select', '-p'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if developer.returncode:
            raise ValueError('此 Mac 没有 Git 开发工具；不会自动弹出安装窗口。请恢复 HTTPS 访问后重试。')
    if not git or not shutil.which('ssh'):
        raise ValueError('SSH 下载需要本机已安装 Git 和 OpenSSH。')
    if not ref or ref.startswith('-') or any(c in ref for c in ('\n', '\r', '\x00')):
        raise ValueError('SSH 下载的版本参数无效。')
    with tempfile.TemporaryDirectory(prefix='vibe-research-ssh-') as temp:
        root = Path(temp)
        checkout = root / 'repo'
        hooks = root / 'empty-hooks'
        hooks.mkdir()
        env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15')
        command = [git, '-c', 'core.hooksPath=' + str(hooks)]
        def run(arguments, **kwargs):
            try:
                return subprocess.run(command + arguments, env=env, check=True, stderr=subprocess.PIPE, timeout=120, **kwargs)
            except subprocess.CalledProcessError as exc:
                error = (exc.stderr or b'').decode('utf8', errors='replace').strip()
                raise ValueError('SSH/Git 获取失败：' + error) from exc
        run(['init', '--quiet', str(checkout)], stdout=subprocess.PIPE)
        run(['-C', str(checkout), 'remote', 'add', 'origin', 'git@github.com:' + REPOSITORY + '.git'], stdout=subprocess.PIPE)
        print('通过现有 SSH 配置获取 GitHub 源码（不弹出认证提示）…', flush=True)
        run(['-C', str(checkout), 'fetch', '--quiet', '--depth=1', 'origin', ref], stdout=subprocess.PIPE)
        archive_path = root / 'snapshot.zip'
        with archive_path.open('wb') as archive:
            run(['-C', str(checkout), 'archive', '--format=zip', 'FETCH_HEAD'], stdout=archive)
        if archive_path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError('SSH 安装包超过大小限制。')
        return archive_path.read_bytes()


def download_snapshot(ref):
    url = 'https://codeload.github.com/' + REPOSITORY + '/zip/' + urllib.parse.quote(ref, safe='')
    try:
        return fetch(url), 'https'
    except OSError as http_error:
        print('HTTPS 源码下载失败：' + str(http_error), flush=True)
        print('尝试使用 SSH；需要已有 GitHub SSH 授权与主机信任配置。', flush=True)
        try:
            return fetch_ssh(ref), 'ssh'
        except (OSError, ValueError, subprocess.TimeoutExpired) as ssh_error:
            raise ValueError('HTTPS 和 SSH 均未能获取源码。\nHTTPS：' + str(http_error) + '\nSSH：' + str(ssh_error) + '\n请检查网络和已有 SSH 配置，或手动下载安装。') from ssh_error


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


def marketplace_listing(codex):
    command = [codex, 'plugin', 'marketplace', 'list', '--json']
    try:
        return json.loads(subprocess.check_output(command, stderr=subprocess.PIPE))
    except subprocess.CalledProcessError as exc:
        # A deleted Downloads folder can make `list` fail before it emits JSON.
        # Repair only our exact stale registration, through the public Codex CLI.
        error = (exc.stderr or b'')
        if isinstance(error, bytes):
            error = error.decode('utf8', errors='replace')
        match = re.search(r'^- `vibe-research-local` at (.+): marketplace root does not contain a supported manifest\s*$', error, re.MULTILINE)
        if not match:
            raise ValueError('Codex 无法读取插件来源列表：\n' + error.strip()) from exc
        previous = Path(match.group(1))
        if (previous / '.agents/plugins/marketplace.json').exists():
            raise ValueError('旧来源的 manifest 仍存在但 Codex 无法读取；为保留配置，请先手动检查该来源：' + str(previous)) from exc
        print('检测到失效的 Vibe Research 旧来源：' + str(previous), flush=True)
        print('移除失效登记并重新安装；不删除旧目录、研究数据或其他插件。', flush=True)
        subprocess.run([codex, 'plugin', 'marketplace', 'remove', 'vibe-research-local'], check=True)
        # Do not restore the invalid registration if installation later fails.
        return json.loads(subprocess.check_output(command, stderr=subprocess.PIPE))


def prepare_marketplace(codex, target):
    listing = marketplace_listing(codex)
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
        print('1/4 准备 GitHub 源码下载（无需 API 或 Token）…', flush=True)
        print('2/4 下载并校验源码…', flush=True)
        data, transport = download_snapshot(ref)
        archive_sha256 = hashlib.sha256(data).hexdigest()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            # GitHub ZIP snapshots normally carry the git commit in their comment.
            archive_commit = archive.comment.decode('ascii', errors='replace').strip()
        commit = archive_commit if re.fullmatch(r'[0-9a-f]{40}', archive_commit) else None
        if re.fullmatch(r'[0-9a-fA-F]{40}', ref):
            if commit and commit != ref.lower():
                raise ValueError('下载源码的提交与指定版本不一致。')
            commit = ref.lower()
        snapshot = commit or 'archive-' + archive_sha256
        print('源码版本：' + (commit or '未提供提交标识，使用压缩包 SHA-256 ' + archive_sha256), flush=True)
        with tempfile.TemporaryDirectory(prefix='.download-', dir=str(directory)) as temp:
            extracted = unpack(data, Path(temp))
            # Keep existing installations intact. Only reuse an identical source snapshot.
            target = directory / snapshot
            if target.exists():
                identical = all((target / p.relative_to(extracted)).is_file() and (target / p.relative_to(extracted)).read_bytes() == p.read_bytes() for p in extracted.rglob('*') if p.is_file())
                if not identical:
                    raise ValueError('同版本安装目录包含修改；为保留文件，请使用 --install-dir 选择新目录。')
            else:
                extracted.rename(target)
        print('3/4 安装 Codex 插件与工作台入口…', flush=True)
        env = dict(os.environ, VIBE_RESEARCH_WORKSPACE=str(Path(workspace).expanduser().resolve()), VIBE_RESEARCH_PYTHON=sys.executable, VIBE_RESEARCH_CODEX=str(codex))
        if os.name == 'nt':
            command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(target / 'install.ps1')]
        else:
            command = ['sh', str(target / 'install.sh')]
        if sys.platform == 'darwin' and env.get('VIBE_RESEARCH_MANAGED_PYTHON') == '1':
            wheel = target / 'plugins/vibe-research/vendor/pypdf-6.21.4-py3-none-any.whl'
            print('从随包 wheel 准备 PDF 阅读依赖（不访问 PyPI）…', flush=True)
            subprocess.run([sys.executable, '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '--no-index', '--no-deps', str(wheel)], env=env, check=True, timeout=120)
            subprocess.run([sys.executable, '-I', '-c', 'import ssl,sqlite3,pypdf'], env=env, check=True, timeout=20)
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
        receipt = {'repository': REPOSITORY, 'commit': commit, 'requested_ref': ref, 'transport': transport, 'archive_sha256': archive_sha256, 'source': str(target), 'workspace': env['VIBE_RESEARCH_WORKSPACE'], 'aliases': alias_status}
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
    parser.add_argument('--ref', default='main', help='GitHub branch, tag or commit; downloaded directly without the REST API')
    parser.add_argument('--no-aliases', action='store_true')
    args = parser.parse_args()
    try:
        install(args.install_dir, args.workspace, args.ref, not args.no_aliases)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print('安装未完成：' + str(exc) + '\n请按 README / INSTALL.md 的手动安装方式重试。', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
