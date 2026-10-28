"""Recoverable, idempotent cross-mode transfers. Originals remain canonical and intact."""
import hashlib
import json
import uuid
from pathlib import Path
from . import brainstorm, engineering, hub, filelock
from .store import Store, ResearchError, atomic, dumps, now


def project(workspace, ident):
    row=next((r for r in hub.entries(Path(workspace)/'projects.json') if r['id']==ident and r['lifecycle']=='active'),None)
    if not row:raise ResearchError('请选择已登记的活动 Engineering 项目')
    return row


def report(store):
    """Deterministic factual progress packet; no inferred scientific support."""
    labels={'planned':'计划中','working':'进行中','blocked':'受阻','completed':'已完成','abandoned':'已终止','draft':'待开展','running':'运行中','failed':'失败','observed':'已采集','unavailable':'待检查','not_checked':'未读取'}
    state=engineering.snapshot(store)
    nodes=store.rows('nodes')
    question=store.db.execute("SELECT value FROM meta WHERE key='question'").fetchone()[0]
    lines=['# 研究进展回顾','','研究问题：'+question,'','来源修订：'+str(store.revision()),'','## 实施与验收']
    for n in state['tasks']:
        d=n['data'];lines+=['','### '+n['id']+' · '+n['title'],'状态：'+labels.get(d['execution_status'],d['execution_status']),'验收标准：'+d['acceptance'],'评估协议：'+d['protocol'],'停止条件：'+d['stop_rule']]
        for u in d.get('updates',[]):lines.append(u['at']+' · '+u['state']+' · '+u['note']+' · 依据 '+', '.join(u.get('evidence',[])))
    if not state['tasks']:lines.append('尚无已登记工作包。')
    lines+=['','## 实验、结果与失败记录']
    for n in state['experiments']:lines.append('- '+n['id']+' · '+n['title']+' · '+labels.get(n['status'],n['status']))
    if not state['experiments']:lines.append('尚无已归档实验结果。')
    lines+=['','## 开发环境快照']
    for n in state['observations']:
        lines.append('- '+n['id']+' · '+n['title'])
        for name,o in n['data']['observations'].items():
            lines.append('  '+name+'：'+labels.get(o['status'],o['status'])+' · '+o['checked_at'])
            for run in o.get('data',{}).get('runs',[]):
                lines.append('  运行 '+str(run.get('id',''))+' · '+str(run.get('state',''))+' · 快照指标 '+json.dumps(run.get('metrics',{}),ensure_ascii=False)+' · 版本 '+str(run.get('commit') or '未记录'))
    lines+=['','## 待核对事项','工程完成、远端运行状态与科学结论分别核对；本回顾仅整理登记记录，不将未完成实验或外部指标视为经验证结论。']
    snapshot_nodes=[{**n,'data':{k:v for k,v in n['data'].items() if k!='source_snapshot'}|{'snapshot_reference':n['id']}} if n['data'].get('source_type')=='mode_transfer' else n for n in nodes]
    return {'revision':store.revision(),'question':question,'nodes':snapshot_nodes,'edges':store.rows('edges'),
            'branches':store.rows('branches'),'members':store.rows('members'),'engineering':{k:v for k,v in state.items() if k!='transfers'},'markdown':'\n'.join(lines)}


def preview(workspace, spec):
    if not isinstance(spec,dict):raise ResearchError('转化规范需为 JSON 对象')
    if spec.get('target') or (spec.get('direction')=='abstract' and spec.get('board')):raise ResearchError('转化始终新建独立项目与分支，不再复用已有目标')
    if spec.get('direction')=='promote':
        board=brainstorm.show(workspace,spec.get('board'))
        if spec.get('expected_updated_at') and spec['expected_updated_at']!=board['updated_at']:raise ResearchError('来源主题已变化，请重新预览')
        if not board.get('project'):raise ResearchError('来源主题缺少独立项目登记')
        idea=spec.get('idea') or board['modules'].get('directions',{}).get('content') or board['modules'].get('proposal',{}).get('content') or board['context']
        if not isinstance(idea,str) or not idea.strip():raise ResearchError('请先形成构想或填写要落实的想法')
        if spec.get('environment'):engineering.environment(spec['environment'])
        return {'direction':'promote','topic':board['topic'],'source':board,'idea':idea,'note':'保存分叉点，创建独立 Engineering 项目和 giver 分支；原 Brainstorming 项目保留。'}
    if spec.get('direction')=='abstract':
        row=project(workspace,spec.get('project'))
        if row.get('mode','engineering')!='engineering':raise ResearchError('来源应为 Engineering 项目')
        store=Store(row['root'])
        try:
            packet=report(store)
            if spec.get('source_revision') is not None and spec['source_revision']!=packet['revision']:raise ResearchError('来源已有更新，请重新预览')
        finally:store.db.close()
        return {'direction':'abstract','project':row,'packet':packet,'note':'从当前工程版本派生独立 Brainstorming 项目与分支，保留完整研究数据和来源。'}
    raise ResearchError('direction 为 promote/abstract')


def transfer(workspace,spec):
    from . import giver
    allowed={'direction','request_id','board','project','topic','idea','acceptance','protocol','stop_rule','environment','expected_updated_at','source_revision','branch'}
    if not isinstance(spec,dict) or set(spec)-allowed:raise ResearchError('转化规范包含无效字段；目标始终为新项目')
    try:key=str(uuid.UUID(spec['request_id']))
    except (KeyError,ValueError,TypeError,AttributeError):raise ResearchError('转化需 request_id UUID')
    # Complete retries must use exactly the original request, even after the source has changed.
    journal=Path(workspace)/'.vibe-research/transfers'/(key+'.json');fingerprint=hashlib.sha256(dumps(spec).encode()).hexdigest()
    journal.parent.mkdir(parents=True,exist_ok=True)
    with journal.with_suffix('.lock').open('a') as lock:
        filelock.flock(lock,filelock.LOCK_EX)
        if journal.exists():
            old=json.loads(journal.read_text())
            if old['fingerprint']!=fingerprint:raise ResearchError('同一转化请求不能改变内容')
            if old.get('result'):return old['result']
        if journal.exists():packet=json.loads(journal.read_text())['packet']
        else:
            packet=preview(workspace,spec);atomic(journal,dumps({'fingerprint':fingerprint,'packet':packet}))
        promote=spec['direction']=='promote';mode='engineering' if promote else 'brainstorming'
        source=packet['source']['project'] if promote else spec['project']
        branch=spec.get('branch') or mode+'/'+key[:12]
        result=giver.fork(workspace,source,branch,mode=mode,title=spec.get('topic') or (packet['topic'] if promote else packet['project']['name']),request_id=key,idea=packet.get('idea'),plan={k:spec[k] for k in ('acceptance','protocol','stop_rule','environment') if spec.get(k)})
        result.update(direction=spec['direction'],transfer=key,source_project=source)
        atomic(journal,dumps({'fingerprint':fingerprint,'result':result}));return result
