"""Explicit portable project registry; never scans or imports unrelated directories."""
from . import filelock as fcntl
import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from .store import ResearchError, Store, atomic
from . import activity, retrieval


def entries(registry):
    registry=Path(registry).resolve()
    if not registry.exists(): return []
    data=json.loads(registry.read_text())
    rows=data['projects']
    if len({r['id'] for r in rows})!=len(rows): raise ResearchError('项目编号重复')
    return [{**r,'uuid':r.get('uuid',str(uuid.uuid5(uuid.NAMESPACE_URL,'vibe-research:'+r['id']))),'lifecycle':r.get('lifecycle','active'),'root':str((registry.parent/r['path']).resolve())} for r in rows]


def register(registry,path,name):
    registry=Path(registry).resolve();root=Path(path).resolve()
    s=Store(root)
    try:
        if not s.doctor()['ok']: raise ResearchError('先修复项目完整性再登记')
    finally: s.db.close()
    name=name.strip()
    if not name: raise ResearchError('项目名称不能为空')
    registry.parent.mkdir(parents=True,exist_ok=True)
    with open(str(registry)+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rows=entries(registry)
        existing=next((r for r in rows if r['root']==str(root)),None)
        if existing: existing['name']=name
        else:
            existing={'id':'p'+uuid.uuid4().hex[:12], 'uuid':str(uuid.uuid4()),'lifecycle':'active','name':name,'path':os.path.relpath(root,registry.parent),'root':str(root)}
            rows.append(existing)
        atomic(root/'.research/project-identity.json',json.dumps({'uuid':existing['uuid']}))
        atomic(registry,json.dumps({'version':2,'projects':[{k:v for k,v in r.items() if k!='root'} for r in rows]},ensure_ascii=False,indent=2))
    return {k:v for k,v in existing.items() if k!='root'}


def catalog(registry,include_removed=False):
    result=[]
    for row in entries(registry):
        if row['lifecycle']=='removed' and not include_removed:continue
        try:
            s=Store(row['root'])
            try:
                current=activity.snapshot(s.root,{n['id'] for n in s.rows('nodes')})['current']
                item={**row,'revision':s.revision(),'current':current,'available':True,'total':activity.history(s.root,1)['total'],
                      'onboarding_required':not row.get('onboarding',{}).get('completed')}
            finally: s.db.close()
        except Exception:
            item={**row,'available':False,'error':'项目不可读，请检查路径或数据库','current':None,'total':0}
        result.append(item)
    return {'projects':result}


@contextmanager
def edit_registry(registry):
    registry=Path(registry).resolve()
    registry.parent.mkdir(parents=True,exist_ok=True)
    with open(str(registry)+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rows=entries(registry)
        yield rows
        atomic(registry,json.dumps({'version':2,'projects':[{k:v for k,v in r.items() if k!='root'} for r in rows]},ensure_ascii=False,indent=2))


def lifecycle(registry,ident,action,reason):
    if not reason.strip():raise ResearchError('需要记录变更原因')
    if action not in ('archive','restore','remove'):raise ResearchError('未知项目操作')
    with edit_registry(registry) as rows:
        row=next((r for r in rows if r['id']==ident),None)
        if row is None:raise ResearchError('项目未登记')
        if action!='restore' and Path(row['root']).exists():
            current=activity.snapshot(Path(row['root']),set())['current']
            if current and current['state'] in ('working','waiting','blocked'):
                raise ResearchError('先暂停或结束项目当前工作，再归档或从入口移除')
            queue=retrieval.snapshot(row['root'])
            with retrieval.database(row['root']) as db:
                pending=db is not None and db.execute("SELECT 1 FROM tasks t JOIN runs r ON t.run=r.id WHERE r.paused=0 AND t.status NOT IN ('done','excluded') LIMIT 1").fetchone()
            if queue['worker_alive'] or pending:
                raise ResearchError('先暂停待补检索并等待后台 worker 退出')
        row['lifecycle']={'archive':'archived','restore':'active','remove':'removed'}[action]
        from .store import now
        row.setdefault('lifecycle_history',[]).append({'action':action,'reason':reason,'at':now()})
    return {'id':ident,'lifecycle':row['lifecycle'],'note':'研究文件全部保留；移除仅隐藏入口，可恢复'}


def relocate(registry,ident,path):
    root=Path(path).resolve()
    with edit_registry(registry) as rows:
        row=next((r for r in rows if r['id']==ident),None)
        if row is None:raise ResearchError('项目未登记')
        if any(r['id']!=ident and r['root']==str(root) for r in rows):raise ResearchError('目标目录已属于其他项目')
        try:identity=json.loads((root/'.research/project-identity.json').read_text())
        except (OSError,ValueError):raise ResearchError('目标缺少项目身份文件；迁移前请先登记原项目')
        if identity.get('uuid')!=row['uuid']:raise ResearchError('目标目录不是此项目的迁移副本')
        store=Store(root)
        try:
            if not store.doctor()['ok']:raise ResearchError('迁移副本完整性未通过')
        finally:store.db.close()
        row['path']=os.path.relpath(root,Path(registry).resolve().parent)
    return {'id':ident,'uuid':row['uuid'],'note':'目录已更新，原项目链接保持有效'}


def create(registry,name,question,providers,request_id):
    # A deterministic destination makes retries idempotent without accepting arbitrary UI paths.
    try: key=str(uuid.UUID(request_id))
    except (ValueError,TypeError,AttributeError):raise ResearchError('无效的创建请求标识')
    if not name.strip() or not question.strip():raise ResearchError('请填写项目名称和研究问题')
    if not providers or set(providers)-set(retrieval.literature.ALL_SOURCES) or not set(providers)&set(retrieval.literature.PROVIDERS):raise ResearchError('请选择至少一个可检索来源')
    root=Path(registry).resolve().parent/'projects'/key
    root.parent.mkdir(parents=True,exist_ok=True)
    with open(root.parent/(key+'.lock'),'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        signature={'name':name,'question':question,'providers':providers}
        intent=root/'creation-request.json'
        if intent.exists() and json.loads(intent.read_text())!=signature:raise ResearchError('同一创建请求不能改变项目内容，请重新开始向导')
        root.mkdir(parents=True,exist_ok=True)
        atomic(intent,json.dumps(signature,ensure_ascii=False))
        if not (root/'.research/research.db').exists():
            store=Store.init(root,question);store.db.close()
        atomic(root/'.research/source-profile.json',json.dumps({'providers':[p for p in providers if p in retrieval.literature.PROVIDERS],
            'resolvers':[p for p in providers if p in retrieval.literature.RESOLVERS],
            'budget_cny_per_source_month':50,'automatic_purchase':False},ensure_ascii=False))
        row=register(registry,root,name)
        with edit_registry(registry) as rows:
            target=next(r for r in rows if r['id']==row['id'])
            target['onboarding']={'version':2,'completed':True,'providers':providers,'budget_cny_per_source_month':50,'automatic_purchase':False,
                                  'connection_preflight':'performed_in_wizard'}
        return {**row,'url':'/p/'+row['id']+'/','note':'已保存研究问题与来源偏好；尚未执行联网检索'}


def relate(registry,source,target,kind,reason):
    if kind not in ('derived_from','related_to','reproduces') or not reason.strip():raise ResearchError('需要有效关系和原因')
    if source==target:raise ResearchError('项目不能关联自身')
    with edit_registry(registry) as rows:
        index={r['id']:r for r in rows}
        if source not in index or target not in index:raise ResearchError('只能关联已登记项目')
        if any(index[i]['lifecycle']=='removed' for i in (source,target)):raise ResearchError('请先恢复已移除项目')
        if kind=='derived_from':
            todo=[target];seen=set()
            while todo:
                current=todo.pop()
                if current==source:raise ResearchError('派生关系不能形成循环')
                if current in seen:continue
                seen.add(current)
                todo += [e['target'] for e in index.get(current,{}).get('relations',[]) if e['kind']=='derived_from']
        store=Store(index[target]['root'])
        try:revision=store.revision()
        finally:store.db.close()
        from .store import now
        relation={'target':target,'target_uuid':index[target]['uuid'],'kind':kind,'reason':reason,'target_revision':revision,'at':now()}
        existing=index[source].setdefault('relations',[])
        if any(e['target']==target and e['kind']==kind for e in existing):raise ResearchError('这条关系已经存在')
        existing.append(relation)
    return {'source':source,**relation,'note':'仅建立可追溯关联，不复制或共享研究状态'}


def bind_codex(registry,ident,codex_id,codex_root,name,host):
    if not all(isinstance(v,str) and v.strip() and len(v)<2000 for v in (codex_id,name,host)):raise ResearchError('需要有效宿主项目信息')
    parent=Path(codex_root).resolve()
    if not parent.is_dir():raise ResearchError('Codex 项目目录不存在')
    with edit_registry(registry) as rows:
        row=next((r for r in rows if r['id']==ident),None)
        if not row:raise ResearchError('研究项目未登记')
        root=Path(row['root'])
        if root!=parent and parent not in root.parents:raise ResearchError('研究目录不属于所选 Codex 项目')
        from .store import now
        row['codex_project']={'id':codex_id,'host':host,'name':name,'root':str(parent),'linked_at':now()}
    return {'linked':True,'note':'已记录宿主项目映射；没有创建新 Codex 项目或改变访问权限'}
