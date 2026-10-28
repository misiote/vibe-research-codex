"""GIt VibE Research: independent project branches with immutable, local research commits."""
import copy,hashlib,json,os,re,uuid,tempfile,zipfile
from pathlib import Path
from contextlib import contextmanager
from . import hub,brainstorm,backup,filelock
from .store import Store,ResearchError,atomic,dumps,now


def home(workspace):return Path(workspace).expanduser().resolve()/'.vibe-research/giver'
def name(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,79}',value) or '..' in value or value.endswith(('/','.lock')):raise ResearchError('分支或标签名使用字母、数字、/、-、_，不含 ..')
    return value

def load(workspace):
    p=home(workspace)/'index.json'
    state=json.loads(p.read_text()) if p.exists() else {'version':1,'branches':{},'commits':{},'tags':{},'reflog':[],'sessions':{},'requests':{}}
    for row in hub.entries(Path(workspace)/'projects.json'):
        if not any(b['project']==row['id'] for b in state['branches'].values()):
            mode=row.get('mode','engineering');state['branches'][mode+'/'+row['id']]={'project':row['id'],'mode':mode,'head':None,'parent':None,'base':None,'created_at':now()}
    return state

@contextmanager
def edit(workspace):
    root=home(workspace);root.mkdir(parents=True,exist_ok=True)
    with (root/'lock').open('a') as lock:
        filelock.flock(lock,filelock.LOCK_EX);state=load(workspace);yield state;atomic(root/'index.json',dumps(state))

def row(workspace,ident):
    result=next((p for p in hub.entries(Path(workspace)/'projects.json') if p['id']==ident),None)
    if not result:raise ResearchError('项目未登记')
    return result

def resolve(state,value):
    if value in state['branches']:return value
    found=next((n for n,b in state['branches'].items() if b['project']==value),None)
    if not found:raise ResearchError('分支或项目不存在')
    return found

def capture(workspace,ident,root_override=None,board_data=None):
    project=row(workspace,ident);store=Store(root_override or project['root'])
    try:
        store.db.execute('BEGIN');files={'question':store.db.execute("SELECT value FROM meta WHERE key='question'").fetchone()[0]}
        for table in ('nodes','edges','branches','members'):
            for item in store.rows(table):
                key=item.get('id') or hashlib.sha256(dumps(item).encode()).hexdigest()[:20]
                files[table+'/'+key]=item
        for f in (store.root/'.research/artifacts').glob('*'):
            if f.is_file():files['artifacts/'+f.name]={'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size}
    finally:store.db.rollback();store.db.close()
    inherited=Path(root_override or project['root'])/'.research/giver-modules.json'
    if project.get('board') or inherited.exists():
        board=board_data or (brainstorm.show(workspace,project['board']) if project.get('board') else json.loads(inherited.read_text()));files['topic']=board['topic'];files['context']=board['context']
        for k,v in board['modules'].items():files['modules/'+k]={q:v.get(q) for q in ('content','sources','uses')}
    return files

def object_data(workspace,state,ref):
    if ref in state['tags']:ref=state['tags'][ref]
    if ref in state['branches']:ref=state['branches'][ref]['head']
    if not ref:return {}
    if ref not in state['commits']:raise ResearchError('提交不存在')
    snapshot=json.loads((home(workspace)/'objects'/ref/'snapshot.json').read_text())
    if hashlib.sha256(dumps({'snapshot':snapshot,**state['commits'][ref]}).encode()).hexdigest()[:20]!=ref:raise ResearchError('提交快照校验失败')
    return snapshot

def changes(left,right):
    return [{'path':k,'change':'added' if k not in left else 'deleted' if k not in right else 'modified','before':left.get(k),'after':right.get(k)} for k in sorted(set(left)|set(right)) if left.get(k)!=right.get(k) or (k in left)!=(k in right)]

def event(state,action,**data):state['reflog'].append({'at':now(),'action':action,**data})

def save_commit(workspace,state,branch,message,parents=None,source=None):
    if not isinstance(message,str) or not message.strip() or len(message)>2000:raise ResearchError('提交需填写说明（1–2000 字符）')
    b=state['branches'][branch];parents=parents if parents is not None else ([b['head']] if b['head'] else [])
    meta={'branch':branch,'project':b['project'],'parents':parents,'message':message.strip(),'at':now(),'source':source}
    project=row(workspace,b['project']);objects=home(workspace)/'objects';objects.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=objects) as temp:
        stage=Path(temp);backup.create(project['root'],stage/'research.zip')
        board=brainstorm.show(workspace,project['board']) if project.get('board') else None
        # Build the diff snapshot from the immutable bundle, never from a later live database.
        snapshot_root=stage/'snapshot';snapshot_root.mkdir()
        with zipfile.ZipFile(stage/'research.zip') as z:
            for path in z.namelist():
                if path.startswith('.research/'):
                    target=snapshot_root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(path))
        snapshot=capture(workspace,b['project'],root_override=snapshot_root,board_data=board)
        ident=hashlib.sha256(dumps({'snapshot':snapshot,**meta}).encode()).hexdigest()[:20];dest=objects/ident;dest.mkdir()
        atomic(dest/'snapshot.json',dumps(snapshot));(stage/'research.zip').rename(dest/'research.zip')
        if board:atomic(dest/'board.json',dumps(board))
    state['commits'][ident]=meta;b['head']=ident;event(state,'commit',branch=branch,commit=ident)
    return {'commit':ident,**meta}

def status(workspace,branch=None,session=None):
    state=load(workspace);projects={p['id']:p for p in hub.entries(Path(workspace)/'projects.json')}
    result={'branches':[{**b,'name':n,'title':projects[b['project']]['name'],'lifecycle':projects[b['project']]['lifecycle'],'root':projects[b['project']]['root'],'url':('/brainstorming?space='+projects[b['project']]['board']) if b['mode']=='brainstorming' else '/p/'+b['project']+'/engineering'} for n,b in state['branches'].items() if b['project'] in projects],
            'commits':[{'id':k,**v} for k,v in state['commits'].items()],'tags':state['tags'],'reflog':state['reflog'],'active':state['sessions'].get(session)}
    if branch:
        n=resolve(state,branch);b=state['branches'][n];result.update(branch=n,changes=changes(object_data(workspace,state,b['head']),capture(workspace,b['project'])))
    return result

def init(workspace,title,mode='brainstorming',branch=None):
    if not isinstance(title,str) or not title.strip() or len(title)>300:raise ResearchError('请填写有效项目名称（1–300 字符）')
    if mode not in ('brainstorming','engineering'):raise ResearchError('模式无效')
    if branch and name(branch) in load(workspace)['branches']:raise ResearchError('分支名已存在')
    if mode=='brainstorming':board=brainstorm.write(workspace,topic=title);project=row(workspace,board['project'])
    else:
        root=Path(workspace).resolve()/'projects'/str(uuid.uuid4());store=Store.init(root,title);store.db.close();p=hub.register(Path(workspace)/'projects.json',root,title,mode=mode);project=row(workspace,p['id'])
    with edit(workspace) as state:
        old=resolve(state,project['id']);n=name(branch) if branch else old
        if n!=old:
            if n in state['branches']:raise ResearchError('分支名已存在')
            state['branches'][n]=state['branches'].pop(old)
        c=save_commit(workspace,state,n,'Initial research snapshot');event(state,'init',branch=n)
    return {'project':project['id'],'branch':n,'commit':c['commit'],'mode':mode}

def commit(workspace,branch,message):
    with edit(workspace) as state:return save_commit(workspace,state,resolve(state,branch),message)

def fork(workspace,source,branch,mode=None,title=None,request_id=None,idea=None,plan=None):
    branch=name(branch)
    request_id=str(uuid.UUID(request_id)) if request_id else str(uuid.uuid4())
    signature={'source':source,'branch':branch,'mode':mode,'title':title,'idea':idea,'plan':plan}
    with edit(workspace) as state:
        previous=state['requests'].get(request_id)
        if previous:
            if previous['signature']!=signature:raise ResearchError('同一分支请求不能改变内容')
            return previous['result']
        if branch in state['branches']:raise ResearchError('分支名已存在')
        historical=source if source in state['commits'] else None
        src=state['commits'][historical]['branch'] if historical else resolve(state,source);parent=state['branches'][src];mode=mode or parent['mode']
        if mode not in ('brainstorming','engineering'):raise ResearchError('模式无效')
        journal=home(workspace)/'requests'/(request_id+'.json')
        if journal.exists():
            prepared=json.loads(journal.read_text())
            if prepared['signature']!=signature:raise ResearchError('同一分支请求不能改变内容')
            base=prepared['base'];state['commits'].update(prepared['commits'])
            if state['branches'][src]['head']==prepared.get('previous_head'):state['branches'][src]['head']=base
        else:
            base=historical or save_commit(workspace,state,src,'Branch point for '+branch)['commit']
            atomic(journal,dumps({'signature':signature,'base':base,'previous_head':state['commits'][base]['parents'][0] if state['commits'][base]['parents'] else None,'commits':state['commits']}))
        # Destination identities are deterministic, so retries can recover a partially created branch.
        root=Path(workspace).resolve()/'projects'/str(uuid.uuid5(uuid.UUID(request_id),'giver-project'))
        if not root.exists():backup.restore(home(workspace)/'objects'/base/'research.zip',root)
        srcrow=row(workspace,parent['project']);board_id=None
        if mode=='brainstorming':
            board_id='B'+hashlib.sha256(request_id.encode()).hexdigest()[:12]
            source_board=home(workspace)/'objects'/base/'board.json'
            if source_board.exists():board=json.loads(source_board.read_text())
            else:
                from .bridge import report
                store=Store(root)
                try:packet=report(store)
                finally:store.db.close()
                inherited=root/'.research/giver-modules.json';materials=json.loads(inherited.read_text()) if inherited.exists() else {}
                board={'topic':title or srcrow['name'],'context':packet['question'],'context_revision':materials.get('context_revision',1),'modules':{**materials.get('modules',{}),'progress':{'content':packet['markdown'],'sources':[],'uses':{},'context_revision':materials.get('context_revision',1),'revision':1,'updated_at':now()}},'created_at':now()}
            board.update(id=board_id,topic=title or board['topic'],connections=[],updated_at=now());board.pop('project',None)
        if mode=='engineering':
            source_board=home(workspace)/'objects'/base/'board.json'
            if source_board.exists():atomic(root/'.research/giver-modules.json',source_board.read_text())
        project=hub.register(Path(workspace)/'projects.json',root,title or srcrow['name'],mode=mode,board=board_id)
        if board_id:
            board['project']=project['id'];brainstorm.directory(workspace).mkdir(parents=True,exist_ok=True);atomic(brainstorm.path(workspace,board_id),dumps(board))
        task_id=None
        if mode=='engineering' and idea:
            from . import engineering
            store=Store(root)
            try:
                existing=next((n for n in store.rows('nodes') if n['data'].get('giver_request')==request_id),None)
                if existing:task_id=existing['id']
                else:
                  with store.write('giver.fork.plan',{'source_project':parent['project'],'base':base}):
                    env=engineering.link(store,plan['environment']) if plan and plan.get('environment') else None
                    task=engineering.task(store,{'title':title or srcrow['name'],'question':idea,'acceptance':(plan or {}).get('acceptance') or '明确指标、基线和验收依据。','protocol':(plan or {}).get('protocol') or '从分叉点建立可复现验证。','stop_rule':(plan or {}).get('stop_rule') or '关键假设或资源约束不成立时暂停。','refs':['RQ0001']+([env['id']] if env else [])})
                    task_id=task['id'];store.update_data(task_id,{'giver_request':request_id})
            finally:store.db.close()
        for automatic in [n for n,b in state['branches'].items() if b['project']==project['id'] and n!=branch]:state['branches'].pop(automatic)
        state['branches'][branch]={'project':project['id'],'mode':mode,'head':base,'parent':src,'base':base,'created_at':now()}
        c=save_commit(workspace,state,branch,'Fork '+src+' → '+branch,parents=[base]);event(state,'branch',branch=branch,source=src,base=base)
        result={'project':project['id'],'title':project['name'],'branch':branch,'base':base,'commit':c['commit'],'board':board_id,'task':task_id,'url':'/brainstorming?space='+board_id if board_id else '/p/'+project['id']+'/engineering'}
        state['requests'][request_id]={'signature':signature,'result':result}
        return result

def switch(workspace,branch,session):
    if not isinstance(session,str) or not session.strip():raise ResearchError('切换分支需当前对话 session ID')
    with edit(workspace) as state:
        n=resolve(state,branch);state['sessions'][session]=n;event(state,'switch',branch=n,session=session)
    return {'branch':n,'note':'仅切换当前对话的工作分支，其他项目和对话不受影响。'}

def diff(workspace,left,right=None):
    state=load(workspace)
    if right is None:
        n=resolve(state,left);return {'left':state['branches'][n]['head'],'right':'working tree','changes':changes(object_data(workspace,state,n),capture(workspace,state['branches'][n]['project']))}
    return {'left':left,'right':right,'changes':changes(object_data(workspace,state,left),object_data(workspace,state,right))}

def tag(workspace,label,ref):
    label=name(label)
    with edit(workspace) as state:
        if label in state['tags']:raise ResearchError('标签已存在，不覆盖')
        if ref in state['branches']:ref=state['branches'][ref]['head']
        if ref not in state['commits']:raise ResearchError('提交不存在')
        state['tags'][label]=ref;event(state,'tag',tag=label,commit=ref)
    return {'tag':label,'commit':ref}

def apply_modules(workspace,board_id,updates):
    board=brainstorm.show(workspace,board_id)
    with tempfile.TemporaryDirectory() as temporary:
        temp=Path(temporary);brainstorm.directory(temp).mkdir(parents=True);atomic(brainstorm.path(temp,board_id),dumps(board))
        for key,value in updates:
            current=brainstorm.show(temp,board_id)
            uses={k:current['modules'][k]['revision'] for k in value.get('uses',{}) if k in current['modules']}
            brainstorm.write(temp,board_id,module=key,content=value['content'],sources=value.get('sources',[]),uses=uses,expected_updated_at=current['updated_at'])
        prepared=brainstorm.show(temp,board_id)
    with (brainstorm.directory(workspace)/'.lock').open('a') as lock:
        filelock.flock(lock,filelock.LOCK_EX)
        if brainstorm.show(workspace,board_id)['updated_at']!=board['updated_at']:raise ResearchError('目标模块已变化，请重新比较')
        atomic(brainstorm.path(workspace,board_id),dumps(prepared))


def restore(workspace,branch,ref,paths):
    # Restores module content as a new version and commit; history and evidence never rewind.
    if not paths:raise ResearchError('恢复需明确模块路径')
    with edit(workspace) as state:
        n=resolve(state,branch);project=row(workspace,state['branches'][n]['project']);data=object_data(workspace,state,ref)
        if not project.get('board'):raise ResearchError('原位恢复限于 Brainstorming 模块；完整历史可从快照派生独立项目')
        for k in paths:
            if not k.startswith('modules/') or k not in data:raise ResearchError('恢复路径不是有效模块')
        save_commit(workspace,state,n,'Before restore')
        apply_modules(workspace,project['board'],[(k.split('/',1)[1],data[k]) for k in paths])
        return save_commit(workspace,state,n,'Restore modules from '+ref,source={'commit':ref,'paths':paths})

def execute(workspace,action,spec):
    allowed={
        'init':{'title','mode','branch'},'branch':{'source','branch','mode','title','request_id','idea','plan'},
        'commit':{'branch','message'},'switch':{'branch','session'},'checkout':{'branch','session'},
        'diff':{'left','right'},'tag':{'label','ref'},'restore':{'branch','ref','paths'},
        'status':{'branch','session'},'tree':set(),'log':set(),'reflog':set(),'show':{'ref'}}
    if action not in allowed or not isinstance(spec,dict) or set(spec)-allowed[action]:raise ResearchError('giver 操作或字段无效')
    if action in ('status','tree','log','reflog'):return status(workspace,**spec)
    if action=='show':return object_data(workspace,load(workspace),spec['ref'])
    if action=='branch':return fork(workspace,**spec)
    if action in ('switch','checkout'):return switch(workspace,**spec)
    return {'init':init,'commit':commit,'diff':diff,'tag':tag,'restore':restore}[action](workspace,**spec)


def command(workspace,arguments):
    import argparse
    p=argparse.ArgumentParser(prog='giver');sub=p.add_subparsers(dest='action',required=True)
    for op in ('status','tree','log','reflog'):
        c=sub.add_parser(op)
        if op=='status':c.add_argument('--branch');c.add_argument('--session')
    c=sub.add_parser('init');c.add_argument('--title',required=True);c.add_argument('--mode',choices=('brainstorming','engineering'),default='brainstorming');c.add_argument('--branch')
    c=sub.add_parser('branch');c.add_argument('branch');c.add_argument('--from',dest='source',required=True);c.add_argument('--mode',choices=('brainstorming','engineering'));c.add_argument('--title');c.add_argument('--request-id',dest='request_id')
    c=sub.add_parser('commit');c.add_argument('--branch',required=True);c.add_argument('-m','--message',required=True)
    for op in ('switch','checkout'):
        c=sub.add_parser(op);c.add_argument('branch');c.add_argument('--session',default=os.environ.get('CODEX_THREAD_ID'))
    c=sub.add_parser('diff');c.add_argument('left');c.add_argument('right',nargs='?')
    c=sub.add_parser('show');c.add_argument('ref')
    c=sub.add_parser('tag');c.add_argument('label');c.add_argument('ref')
    c=sub.add_parser('restore');c.add_argument('--branch',required=True);c.add_argument('--source',dest='ref',required=True);c.add_argument('--path',dest='paths',required=True,action='append')
    d=vars(p.parse_args(arguments));action=d.pop('action')
    return execute(workspace,action,d)
