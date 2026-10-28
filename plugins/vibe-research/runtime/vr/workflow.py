"""Event-boundary advice and durable user choices; never executes project changes."""
import hashlib
import json
from pathlib import Path
from . import giver, brainstorm, filelock
from .store import ResearchError, atomic, dumps, now

EVENTS=('resume','milestone','goal_change','blocked','user_request')
INTENTS=('continue','implement','report','alternative')
DECISIONS=('presented','defer','decline','accept','applied','failed')

def path(workspace):return Path(workspace).resolve()/'.vibe-research/workflow/decisions.json'
def load(workspace):
    p=path(workspace)
    return json.loads(p.read_text()) if p.exists() else {'version':1,'choices':{},'history':[]}
def digest(value):return hashlib.sha256(dumps(value).encode()).hexdigest()[:24]

def evaluate(workspace,spec):
    allowed={'branch','session','event','intent','goal','reason','target','persistent','explicit','milestone'}
    if not isinstance(spec,dict) or set(spec)-allowed:raise ResearchError('管理评估字段无效')
    if spec.get('event') not in EVENTS or spec.get('intent','continue') not in INTENTS:raise ResearchError('管理事件或意图无效')
    for k in ('branch','session','goal','reason','target','milestone'):
        if k in spec and (not isinstance(spec[k],str) or len(spec[k])>2000):raise ResearchError('管理上下文需为有限长度文本')
    for k in ('persistent','explicit'):
        if k in spec and type(spec[k]) is not bool:raise ResearchError('管理开关需为布尔值')
    if not spec.get('goal','').strip():raise ResearchError('需要稳定的当前目标名称')
    state=giver.load(workspace)
    selected=spec.get('branch') or state['sessions'].get(spec.get('session'))
    if not selected:return {'action':'continue','delivery':'none','reason':'尚未明确项目；先依据用户指定项目选择，不推测最近分支。'}
    branch=giver.resolve(state,selected);b=state['branches'][branch];project=giver.row(workspace,b['project'])
    if project['lifecycle']!='active':return {'action':'continue','delivery':'none','reason':'项目不在活动入口；不自动恢复、切换或派生。'}
    snapshot=giver.capture(workspace,project['id']);dirty=giver.changes(giver.object_data(workspace,state,b['head']),snapshot)
    source=digest({'head':b['head'],'snapshot':snapshot})
    intent=spec.get('intent','continue');reason=spec.get('reason','').strip();explicit=spec.get('explicit',False)
    action='continue';delivery='none';target=None;facts=[]
    if (intent!='continue' or spec.get('target')) and not reason:raise ResearchError('结构调整需说明任务意图与具体依据，不接受关键词命中')
    if spec.get('target'):
        target=giver.resolve(state,spec['target']);target_row=giver.row(workspace,state['branches'][target]['project'])
        if target_row['lifecycle']!='active':raise ResearchError('目标分支已归档或移除，不能自动选择')
        if target!=branch:
            if not spec.get('session'):raise ResearchError('切换建议需要当前对话 session')
            action='switch';facts=['目标分支已存在；无需再创建项目。']
    elif intent=='implement' and b['mode']=='brainstorming':
        board=brainstorm.show(workspace,project['board'])
        usable=[k for k in ('directions','proposal') if board['modules'].get(k,{}).get('content','').strip()]
        stale=[k for k in usable if board['modules'][k]['needs_review']]
        if stale:
            action='review_inputs';facts=['候选方案依赖已变化：'+', '.join(stale)+'；先复核，再决定实施。']
        elif usable:
            action='convert';target='engineering';facts=['已有可实施的方向或方案材料：'+', '.join(usable)]
        else:facts=['尚未形成可实施方案；继续澄清构想，不为了切换模式创建空项目。']
    elif intent=='report' and b['mode']=='engineering':
        if spec.get('persistent') or explicit:
            action='convert';target='brainstorming';facts=['需要独立持续维护的方案或进展材料；工程数据保留在来源项目。']
        else:facts=['一次性汇报可直接从当前工程项目整理，不必派生项目。']
    elif intent=='alternative':
        action='branch';target=b['mode'];facts=['用户任务需要保留现有路线，同时探索独立替代方案。']
    if action in ('convert','branch','switch'):
        # Suggestions occur at actual task boundaries, never every message or timer tick.
        if explicit:delivery='execute'
        elif spec['event'] in ('milestone','goal_change'):delivery='ask'
        else:action='continue';target=None;facts=['当前不是结构调整边界；继续原任务，阻塞本身不触发转换。']
    if action=='continue' and dirty and spec['event']=='milestone':
        action='checkpoint';delivery='automatic';facts=['当前里程碑产物已保存，存在尚未提交的研究变化。']
    if action=='review_inputs':delivery='continue'
    key=digest({'project':project['id'],'goal':spec['goal'].strip(),'action':action,'target':target})
    proposal=digest({'key':key,'source':source,'target_head':state['branches'].get(target,{}).get('head')})
    return {'id':proposal,'key':key,'action':action,'delivery':delivery,'branch':branch,'project':project['id'],'mode':b['mode'],'head':b['head'],
            'target':target,'source':source,'goal':spec['goal'].strip(),'reason':reason,'facts':facts,'dirty':bool(dirty),
            'milestone':spec.get('milestone'),'note':'转换与派生创建独立项目；切换仅影响当前对话。运行、发布、归档和删除不在自动执行范围。'}

def assess(workspace,spec):
    result=evaluate(workspace,spec)
    if 'key' not in result:return result
    choices=load(workspace)['choices']
    pending=next((c for c in choices.values() if c['project']==result['project'] and c['goal']==result['goal'] and c['decision'] in ('presented','accept') and c['key']!=result['key']),None)
    if pending and not spec.get('explicit') and result['delivery']=='ask':
        return {**result,'delivery':'none','suppressed':True,'previous_decision':'another_pending','pending_proposal':pending['proposal']}
    old=choices.get(result['key'])
    if not old or spec.get('explicit'):return result
    status=old['decision']
    suppress=(status in ('presented','decline') or
              status=='defer' and (not spec.get('milestone') or spec.get('milestone')==old.get('milestone')) or
              status in ('applied','accept') and result['action'] in ('convert','branch','switch') or
              status in ('applied','failed','accept') and old['proposal']==result['id'])
    if suppress and result['delivery'] in ('ask','automatic'):
        result.update(delivery='none',suppressed=True,previous_decision=status)
    return result

def record(workspace,spec):
    if not isinstance(spec,dict) or set(spec)-{'context','proposal','decision','receipt','note'}:raise ResearchError('管理选择字段无效')
    decision=spec.get('decision')
    if decision not in DECISIONS:raise ResearchError('管理选择无效')
    if decision in ('applied','failed'):
        return finish(workspace,spec)
    result=evaluate(workspace,spec.get('context'))
    if not result.get('id') or result['id']!=spec.get('proposal'):raise ResearchError('来源或目标版本已变化；重新评估，不沿用旧确认')
    if result['action'] in ('continue','review_inputs'):raise ResearchError('当前没有需要登记的管理建议')
    if decision=='presented' and result['delivery']!='ask':raise ResearchError('只有实际待询问的建议可登记为已展示')
    receipt=spec.get('receipt')
    note=spec.get('note','')
    if not isinstance(note,str) or len(note)>2000:raise ResearchError('管理说明无效')
    p=path(workspace);p.parent.mkdir(parents=True,exist_ok=True)
    with p.with_suffix('.lock').open('a') as lock:
        filelock.flock(lock,filelock.LOCK_EX);data=load(workspace)
        old=data['choices'].get(result['key'])
        if decision=='accept' and (not old or old['decision'] not in ('presented','defer') or old['proposal']!=result['id']) and not spec['context'].get('explicit') and result['delivery']!='automatic':
            raise ResearchError('先提出具体建议并取得用户选择；不能推测同意')
        entry={'proposal':result['id'],'key':result['key'],'project':result['project'],'branch':result['branch'],
               'action':result['action'],'target':result['target'],'goal':result['goal'],'source':result['source'],
               'head':result['head'],'milestone':result['milestone'],'decision':decision,'at':now(),'receipt':receipt,'note':note,'context':spec['context']}
        if decision=='accept':entry['accepted_at']=entry['at']
        data['choices'][result['key']]=entry;data['history'].append(entry);atomic(p,dumps(data))
    return entry

def finish(workspace,spec):
    """Execution changes HEAD; validate its receipt against the accepted pre-action proposal."""
    p=path(workspace);p.parent.mkdir(parents=True,exist_ok=True)
    with p.with_suffix('.lock').open('a') as lock:
        filelock.flock(lock,filelock.LOCK_EX);data=load(workspace)
        previous=next((x for x in reversed(data['history']) if x['proposal']==spec.get('proposal')),None)
        if not previous or previous['decision'] not in ('accept','applied','failed') or previous['context']!=spec.get('context'):
            raise ResearchError('未找到该上下文中已接受的管理建议')
        if previous['decision']==spec['decision'] and previous.get('receipt')==spec.get('receipt'):return previous
        receipt=spec.get('receipt');note=spec.get('note','')
        if not isinstance(note,str) or len(note)>2000:raise ResearchError('管理说明无效')
        if spec['decision']=='applied':
            if not isinstance(receipt,dict):raise ResearchError('完成管理动作需提供实际 CLI 回执')
            state=giver.load(workspace);action=previous['action']
            if action=='checkpoint':
                c=state['commits'].get(receipt.get('commit'))
                valid=c and c['project']==previous['project'] and receipt.get('commit')!=previous['head'] and c['at']>=previous['accepted_at'] and state['branches'][previous['branch']]['head']==receipt.get('commit')
            elif action in ('branch','convert'):
                dest=state['branches'].get(receipt.get('branch'),{})
                valid=(dest.get('project')==receipt.get('project') and dest.get('project')!=previous['project'] and dest.get('parent')==previous['branch'] and dest.get('mode')==previous['target'] and dest.get('created_at','')>=previous['accepted_at'])
            else:valid=state['sessions'].get(spec['context'].get('session'))==previous['target']==receipt.get('branch')
            if not valid:raise ResearchError('回执与实际 giver 状态不符，不能登记为已完成')
        entry={**previous,'decision':spec['decision'],'at':now(),'receipt':receipt,'note':note}
        data['choices'][previous['key']]=entry;data['history'].append(entry);atomic(p,dumps(data))
    return entry
