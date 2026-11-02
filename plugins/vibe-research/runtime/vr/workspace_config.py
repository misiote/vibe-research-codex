"""Workspace connection summaries. Credentials remain in the existing host store.

This module never opens or writes a research Store, board, or version tree.
"""
import json
from pathlib import Path
from . import connections, integrations, filelock
from .store import atomic, now


def path(workspace):
    return Path(workspace).expanduser().resolve() / '.vibe-research' / 'connection-checks.json'


def load(workspace):
    try:
        value = json.loads(path(workspace).read_text(encoding='utf8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def update(workspace, change):
    target = path(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.with_suffix('.lock').open('a') as lock:
        filelock.flock(lock, filelock.LOCK_EX)
        previous = load(workspace)
        change(previous)
        atomic(target, json.dumps(previous, ensure_ascii=False))


def record(workspace, result):
    # No keys, headers, query strings or raw upstream errors are persisted here.
    rows = {r['provider']: {'status': r['status'], 'checked_at': result['checked_at']}
            for r in result.get('providers', [])}
    update(workspace, lambda previous: previous.update(rows))


def invalidate(workspace, provider):
    update(workspace, lambda previous: previous.pop(provider, None))


def snapshot(workspace):
    data = connections.status()
    checks = load(workspace)
    for row in data['providers']:
        previous = checks.get(row['provider'], {})
        if not isinstance(previous, dict):
            previous = {}
        required = row['provider'] in ('wos', 'scopus', 'unpaywall')
        row['status'] = 'needs_auth' if required and not row['configured'] else previous.get('status', 'unverified')
        row['checked_at'] = previous.get('checked_at')
    return {**data, 'runtime': integrations.runtime_status(), 'checked_at': now(),
            'scope': 'workspace', 'note': '本机配置与最近连接结果；未验证不等于可用。联网检测仅在明确发起后运行。'}


def check(workspace, providers):
    result = integrations.preflight(providers)
    record(workspace, result)
    return result
