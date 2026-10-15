"""Read-only connector probes with explicit evidence and scope."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from .store import ResearchError, Store, now, atomic, dumps
from .literature import Router, PROVIDERS, ALL_SOURCES, APIError, AuthenticationRequired, search_page
from . import request_gate

STATUSES = {'passed', 'partial', 'blocked', 'unverified'}


def item(name, status, level, evidence, next_step, **extra):
    return dict(name=name, status=status, level=level, evidence=evidence, next_step=next_step, checked_at=now(), **extra)


def command(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return -1, '命令不存在或超时'


def app_locations(name):
    return [str(p) for p in [Path('/Applications') / (name + '.app'), Path.home() / 'Applications' / (name + '.app')] if p.exists()]


def local_get(path):
    try:
        req = urllib.request.Request('http://127.0.0.1:23119' + path, headers={'Zotero-API-Version': '3'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as response:
            body = response.read(100000)
            return {'http': response.status, 'json_valid': isinstance(json.loads(body), (list, dict)) if path.startswith('/api') else True}
    except urllib.error.HTTPError as e:
        return {'http': e.code, 'error': 'HTTP ' + str(e.code)}
    except (OSError, ValueError, urllib.error.URLError) as e:
        reason = getattr(e, 'reason', e)
        return {'http': None, 'error': type(reason).__name__ + ': ' + str(reason)[:160]}


def runtime_status():
    available = importlib.util.find_spec('pypdf') is not None
    return {
        'python':sys.executable,
        'pypdf':available,
        'status':'ready' if available else 'needs_setup',
        'note':'PDF 文本提取已就绪。' if available else '当前 Python 缺少 pypdf；可先检索元数据，但 PDF 精读需要切换到 Codex bundled runtime 或安装 PDF 可选依赖。',
    }


def preflight(providers):
    """A real, non-importing probe for the onboarding wizard."""
    providers=list(dict.fromkeys(providers))
    if not providers or set(providers)-set(ALL_SOURCES):raise ResearchError('请选择有效来源进行预检')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='vr-preflight-') as directory:
        store=Store.init(Path(directory)/'probe','onboarding connection probe')
        try:
            router=Router(store,fresh=True,defer=True)
            for provider in providers:
                query='10.1038/nature12373' if provider=='unpaywall' else 'machine learning'
                try:
                    page=search_page(router,query,provider,size=1)
                    diagnostic=page.get('diagnostic') or {}
                    rows.append({'provider':provider,'status':'passed','message':'实际 API 查询通过；未导入任何文献。','diagnostic':diagnostic})
                except AuthenticationRequired as exc:
                    rows.append({'provider':provider,'status':'needs_auth','message':str(exc)})
                except request_gate.Deferred as exc:
                    rows.append({'provider':provider,'status':'waiting','message':str(exc),'next_retry':exc.until})
                except APIError as exc:
                    status='waiting' if exc.diagnostic.get('http')==429 or exc.diagnostic.get('http',0)>=500 else 'needs_auth' if exc.diagnostic.get('http') in (401,403) else 'blocked'
                    rows.append({'provider':provider,'status':status,'message':str(exc),'diagnostic':exc.diagnostic})
                except ResearchError as exc:
                    rows.append({'provider':provider,'status':'blocked','message':str(exc)})
                except (OSError,sqlite3.Error) as exc:
                    rows.append({'provider':provider,'status':'blocked','message':'本机预检环境不可用：'+type(exc).__name__+'；请检查运行账户及数据目录权限。'})
        finally:store.db.close()
    from .connections import status
    from . import network_access
    return {'checked_at':now(),'providers':rows,'connections':status(),'network_access':network_access.status(),'runtime':runtime_status(),
            'note':'这是用户触发的新手预检；执行真实只读查询，不导入文献，也不代表全文权限。'}


def check(store, network=False):
    rows = []
    health = store.doctor()
    rows.append(item('SQLite / 研究图', 'passed' if health['ok'] else 'blocked', 'integrity_checked',
                     '数据库、图快照、审计与附件哈希一致' if health['ok'] else '; '.join(health['errors']),
                     '继续通过 vr 修改研究状态；跨机器接力时另做 restore 验收'))
    available = runtime_status()['pypdf']
    fulltexts = sum(bool(n['data'].get('documents')) for n in store.rows('nodes') if n['kind'] == 'P')
    rows.append(item('PDF 精读', 'passed' if available else 'partial', 'runtime_available' if available else 'dependency_missing',
                     f'当前解释器：{sys.executable}；pypdf={available}；项目已保存 {fulltexts} 篇全文',
                     '原文匹配后仍需解释审阅；缺依赖时安装 .[pdf]'))
    canvas = store.root / 'research/research.canvas'
    paths = app_locations('Obsidian')
    try:
        graph = json.loads(canvas.read_text(encoding="utf8"))
        valid = all((store.root / 'research' / n['file']).is_file() for n in graph['nodes'] if n['type'] == 'file')
    except (OSError, KeyError, ValueError):
        valid = False
    rows.append(item('Obsidian', 'partial' if valid else 'blocked', 'projection_verified' if valid else 'projection_missing',
                     f'Canvas 文件与链接检查={valid}；常用应用目录发现={bool(paths)}；尚未验证在 Obsidian 内打开',
                     '用 Obsidian 打开 research 作为 vault，再查看 Canvas；也可直接查看 Progress.md'))
    rc, version = command(['git', '--version'])
    grc, gitroot = command(['git', '-C', str(store.root), 'rev-parse', '--show-toplevel'])
    exact = grc == 0 and Path(gitroot).resolve() == store.root
    rows.append(item('Git 项目版本管理', 'passed' if exact else 'partial' if rc == 0 else 'blocked',
                     'repository_detected' if exact else 'binary_only',
                     f'{version}; 独立项目仓库={exact}', '初始化项目仓库并保存快照；随后用新 clone 验证恢复'))
    rc, version = command(['java', '-version'])
    rows.append(item('OpenGuanDan 运行环境', 'partial' if rc == 0 else 'blocked', 'runtime_only' if rc == 0 else 'runtime_missing',
                     'Java 可运行，尚未验证掼蛋引擎' if rc == 0 else 'java 启动器未能启动可用运行时；尚未运行掼蛋环境',
                     '准备合适 JDK，固定引擎版本和 JAR 哈希，再跑合法出牌与 seed 重放测试'))
    rows.append(item('Kimi', 'partial' if shutil.which('kimi') else 'unverified', 'binary_only' if shutil.which('kimi') else 'not_probed',
                     '仅检查 PATH 中是否存在 kimi；未完成独立会话接力', '用 Kimi 从 status/trace 恢复，并在专用测试项目通过 CLI 完成一次读写'))
    if network:
        api, connector = local_get('/api/users/0/items?limit=1'), local_get('/connector/ping')
        ok = api.get('http') == 200 and api.get('json_valid')
        rows.append(item('Zotero', 'passed' if ok else 'blocked', 'api_read_verified' if ok else 'api_unavailable',
                         f"本地文献查询 API={api.get('http')}；Connector={connector.get('http')}；{api.get('error', '')}",
                         '先允许本机 API 读取，再验证文献查询；Connector 可达不代表文献读取或写入完成', probe={'api': api, 'connector': connector}))
        # Each provider is tested individually, so fallback cannot hide a broken provider.
        for provider in ALL_SOURCES:
            try:
                query='10.1038/nature12373' if provider=='unpaywall' else 'Guandan'
                result=search_page(Router(store,fresh=True),query,provider,size=1)
                cached = result.get('diagnostic',{}).get('cached', False)
                count = len(result['papers'])
                rows.append(item(provider, 'partial' if cached else 'passed', 'cache_read_verified' if cached else 'api_read_verified',
                                 f'标准化结果 {count} 条；缓存命中={cached}；本次不导入项目',
                                 '缓存命中不验证当前网络；引用展开与去重导入需另做验收', count=count, cached=cached, diagnostic=result.get('diagnostic',{})))
            except AuthenticationRequired as exc:
                rows.append(item(provider,'partial','needs_auth',str(exc),'从工作台本机配置凭据，再重新检测。'))
            except request_gate.Deferred as exc:
                rows.append(item(provider,'partial','waiting_rate_limit',str(exc),'等待到期后由在线检索执行器续查，或手动重新检测。',next_retry=exc.until))
            except APIError as exc:
                code=exc.diagnostic.get('http')
                if code==429:
                    rows.append(item(provider,'partial','waiting_rate_limit',str(exc),'等待服务端额度或本地冷却到期；配置免费 key 可提高稳定性。',
                                     diagnostic=exc.diagnostic,next_retry=time.time()+max(1,exc.diagnostic.get('retry_after_seconds',60))))
                elif code in (401,403):
                    rows.append(item(provider,'partial','needs_auth',str(exc),'核对本机凭据、机构 entitlement 与执行主机网络。',diagnostic=exc.diagnostic))
                else:
                    rows.append(item(provider,'blocked','api_unavailable',str(exc),'保留查询，等待服务恢复后重试。',diagnostic=exc.diagnostic))
            except ResearchError as exc:
                rows.append(item(provider, 'blocked', 'api_unavailable', str(exc), '429：按重试时间等待并配置免费 key；401/403：核对 key 与权限；网络错误：检查代理、DNS 和 TLS。运行 integrations setup 引导配置。', diagnostic=getattr(exc,'diagnostic',{})))
    else:
        rows.append(item('Zotero', 'unverified', 'not_probed', f'常用目录发现应用={bool(app_locations("Zotero"))}；本次未探测端口', '运行 vr integrations check --network'))
        for provider in ALL_SOURCES:
            rows.append(item(provider, 'unverified', 'not_probed', '本次未请求 API；已有书目不能证明连接可用', '运行 vr integrations check --network'))
    evidence_path = store.root / 'research/integration-evidence.json'
    if evidence_path.exists():
        records = json.loads(evidence_path.read_text(encoding="utf8"))
        for r in records:
            rows.append(dict(r, evidence_kind='operator_recorded', scope='由操作者记录的外部宿主检查；非 vr 内置自动探测'))
    result = {'generated_at': now(), 'network_requested': network, 'revision': store.revision(), 'items': rows,
              'note': '这是带时间戳的检查快照，不是实时监控。passed 仅表示所列 level；不保证所有读写流程已通过。'}
    atomic(store.root / 'research/integrations.json', dumps(result))
    publish_markdown(store, result)
    return result


def record(store, name, status, level, evidence, next_step):
    if status not in STATUSES or not all(v.strip() for v in (name, level, evidence, next_step)):
        raise ResearchError('必须提供有效状态、验证层级、证据与下一步')
    # Serialize external attestations with the same lock used for graph commands.
    from . import filelock as fcntl
    with open(store.home / 'lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = store.root / 'research/integration-evidence.json'
        rows = json.loads(path.read_text(encoding="utf8")) if path.exists() else []
        current = item(name, status, level, evidence, next_step, actor=os.environ.get('VR_ACTOR', 'local'))
        rows = [r for r in rows if r['name'] != name] + [current]
        atomic(path, dumps(rows))
    return current


def publish_markdown(store, result):
    labels = {'passed': '本项检查通过', 'partial': '部分验证', 'blocked': '当前受阻', 'unverified': '未验证'}
    lines = ['# 工具接入检查', '', '检查时间：' + result['generated_at'], '',
             '[[Progress|研究进展]] · [[Home|项目首页]]', '', result['note'], '',
             '| 工具 | 状态 | 验证层级 | 证据 | 下一步 |', '|---|---|---|---|---|']
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    for r in result['items']:
        lines.append('| ' + ' | '.join(cell(x) for x in (r['name'], labels[r['status']], r['level'], r['evidence'], r['next_step'])) + ' |')
    atomic(store.root / 'research/Integrations.md', '\n'.join(lines) + '\n')
