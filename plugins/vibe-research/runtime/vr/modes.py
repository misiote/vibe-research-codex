"""Explicit conversation modes. No prompt classification or global active-project switch."""
import hashlib
import json
import os
from pathlib import Path
from .store import ResearchError, atomic, dumps, now
from . import lightning, filelock

MODES = {
    'lightning': {'icon': 'ϟ', 'title': 'Lightning', 'purpose': '即时探索与轻量创作',
                  'skills': [], 'depth': 'summary'},
    'brainstorming': {'icon': '✦', 'title': 'Brainstorming', 'purpose': '研究构想与方案规划',
                      'skills': ['research-direction-expert', 'research-admin-expert'], 'depth': 'skim'},
    'engineering': {'icon': '⌘', 'title': 'Engineering', 'purpose': '代码、实验与可复现结果',
                    'skills': ['research-engineering-expert'], 'depth': 'deep'},
}


def session_path(workspace, session):
    if not isinstance(session, str) or not session.strip() or len(session) > 200:
        raise ResearchError('需要当前对话的 session 标识；不能用全局默认会话')
    return Path(workspace).expanduser().resolve()/'.vibe-research'/'sessions'/(hashlib.sha256(session.encode()).hexdigest()+'.json')


def status(workspace, session):
    p = session_path(workspace, session)
    return json.loads(p.read_text(encoding='utf8')) if p.exists() else {'mode': None}


def enter(workspace, session, mode, request='', project=None, fresh=False, topic='', board=None):
    if mode not in MODES: raise ResearchError('模式为 lightning/brainstorming/engineering')
    if not isinstance(request, str) or len(request) > 200000: raise ResearchError('需求过长或格式无效')
    if project and mode != 'engineering': raise ResearchError('Brainstorming 通过独立主题项目续接；Engineering 使用 research-project')
    if project:
        from .store import Store
        store = Store(Path(project).expanduser().resolve())
        try:
            if not store.doctor()['ok']: raise ResearchError('工程项目完整性检查未通过')
        finally: store.db.close()
    p = session_path(workspace, session); p.parent.mkdir(parents=True, exist_ok=True)
    with p.with_suffix('.lock').open('a') as lock:
        filelock.flock(lock, filelock.LOCK_EX)
        old = status(workspace, session)
        same = old.get('mode') == mode and not fresh
        data = {'mode': mode, 'session': session, 'updated_at': now(), 'request': request,
                'project': str(Path(project).expanduser().resolve()) if project else old.get('project') if same else None,
                'skills': MODES[mode]['skills']}
        if mode == 'brainstorming':
            from . import brainstorm
            ident=board or (old.get('board') if same else None)
            if ident: data['space']=brainstorm.show(workspace,ident)
            elif topic: data['space']=brainstorm.write(workspace,topic=topic,context=request)
            if data.get('space'): data['board']=data['space']['id']
            data['modules']=brainstorm.MODULES
            data['next']='以研究主题创建或续接空间，按本次需求选择模块；无主题一次任务使用 Lightning。'
        elif mode == 'lightning':
            ident = old.get('draft') if same else None
            try: draft = lightning.show(workspace, ident) if ident else None
            except ResearchError: draft = None
            if not draft:
                draft = lightning.write(workspace, mode=mode, task='decision' if mode=='brainstorming' else 'writing', depth=MODES[mode]['depth'], body=request)
            data['draft'] = draft['id']
            data['task_packet'] = lightning.packet(workspace, draft['id'])
        else:
            data['next'] = '关联已有研究项目，或用项目向导创建；再使用 engineering link/task 和 experiment plan/ingest。'
        # Persist only routing state; the draft remains the single copy of its body/output.
        atomic(p, dumps({k:v for k,v in data.items() if k not in ('task_packet','space')}))
    return data


def current_session(explicit=None):
    value = explicit or os.environ.get('CODEX_THREAD_ID')
    if not value: raise ResearchError('未取得当前对话 ID；请显式传 --session，不创建全局模式')
    return value
