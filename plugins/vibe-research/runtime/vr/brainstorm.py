"""Topic-centered research spaces with independently versioned, explicitly linked modules."""
import json
import hashlib
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from . import filelock
from .store import ResearchError, atomic, dumps, now

MODULES={
    'landscape':{'title':'研究视野','skill':'research-landscape-expert'},
    'history':{'title':'研究脉络','skill':'research-history-expert'},
    'directions':{'title':'方向研判','skill':'research-direction-expert'},
    'proposal':{'title':'方案规划','skill':'research-admin-expert'},
    'progress':{'title':'进展回顾','skill':'research-writing-editor'},
}


def directory(workspace): return Path(workspace).expanduser().resolve()/'.vibe-research'/'brainstorms'


def path(workspace, ident):
    if not isinstance(ident,str) or not re.fullmatch('B[a-f0-9]{12}',ident): raise ResearchError('主题空间编号无效')
    return directory(workspace)/(ident+'.json')


def show(workspace, ident):
    p=path(workspace,ident)
    if not p.is_file(): raise ResearchError('主题空间不存在')
    data=json.loads(p.read_text(encoding='utf8'))
    for key,module in data['modules'].items():
        module['needs_review']=module['context_revision']!=data['context_revision'] or any(data['modules'].get(k,{}).get('revision')!=v for k,v in module.get('uses',{}).items())
    return data


def listing(workspace, include_hidden=False):
    from . import hub,giver
    branch_names={b['project']:name for name,b in giver.load(workspace)['branches'].items()}
    projects={r['id']:r for r in hub.entries(Path(workspace).expanduser().resolve()/'projects.json')}
    items=[];hidden=0
    for p in directory(workspace).glob('B*.json'):
        board=show(workspace,p.stem)
        # A topic belongs to its own Brainstorming project. Lineage is never ownership.
        row=projects.get(board.get('project'))
        visibility=row['lifecycle'] if row else 'active'
        if visibility!='active':
            hidden+=1
            if not include_hidden:continue
        items.append({**board,'visibility':visibility,'branch':branch_names.get(board.get('project'))})
    return {'spaces':sorted(items,key=lambda b:b['updated_at'],reverse=True),'modules':MODULES,'hidden_count':hidden}


def write(workspace, ident=None, creation_key=None, **spec):
    if creation_key is not None:
        try:creation_key=str(uuid.UUID(creation_key))
        except (ValueError,TypeError,AttributeError):raise ResearchError('主题空间创建请求编号无效')
        if ident:raise ResearchError('创建请求不能同时指定已有空间')
    if set(spec)-{'topic','context','module','content','sources','uses','expected_updated_at'}: raise ResearchError('主题空间包含未知字段')
    for key in ('topic','context','content'):
        if key in spec and (not isinstance(spec[key],str) or len(spec[key])>(300 if key=='topic' else 200000)): raise ResearchError('主题或内容无效/过长')
    root=directory(workspace);root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        filelock.flock(lock,filelock.LOCK_EX)
        if creation_key:
            stable='B'+hashlib.sha256(creation_key.encode()).hexdigest()[:12]
            if path(workspace,stable).exists():
                existing=show(workspace,stable)
                if existing.get('creation_request')!=creation_key:raise ResearchError('主题空间编号冲突；未覆盖已有空间')
                return existing
        if ident:
            data=show(workspace,ident)
            if spec.get('expected_updated_at') is not None and spec['expected_updated_at']!=data['updated_at']: raise ResearchError('主题空间已有更新，请重新载入后合并')
        else:
            if not spec.get('topic','').strip(): raise ResearchError('Brainstorming 需要研究主题；无主题任务可用 Lightning')
            ident=stable if creation_key else 'B'+uuid.uuid4().hex[:12]
            data={'id':ident,'topic':spec['topic'].strip(),'context':spec.get('context',''),'context_revision':1,'modules':{},'created_at':now()}
            if creation_key:data['creation_request']=creation_key
        if spec.get('topic') is not None and not spec['topic'].strip(): raise ResearchError('研究主题不可为空')
        if ident and any(k in spec and spec[k]!=data[k] for k in ('topic','context')):
            data['context_revision']+=1
        for k in ('topic','context'):
            if k in spec:data[k]=spec[k]
        if 'module' in spec:
            key=spec['module']
            if key not in MODULES: raise ResearchError('主题模块无效')
            if 'content' not in spec: raise ResearchError('模块需提供 content')
            sources=spec.get('sources',[]);uses=spec.get('uses',{})
            if not isinstance(sources,list) or len(sources)>100: raise ResearchError('sources 需为来源 URL 列表')
            for source in sources:
                if not isinstance(source,str): raise ResearchError('来源 URL 无效')
                try: p=urlsplit(source)
                except ValueError: raise ResearchError('来源 URL 无效')
                if p.scheme not in ('http','https') or not p.hostname or p.username or p.password: raise ResearchError('来源使用不含凭据的 HTTP(S) 地址')
            if not isinstance(uses,dict) or key in uses or set(uses)-set(data['modules']): raise ResearchError('模块引用需指向已有的其他模块')
            for k,v in uses.items():
                if type(v) is not int or v!=data['modules'][k]['revision']: raise ResearchError('引用版本已变化，请重新核对输入')
                # Reject cycles in the declared dependency graph, while modules themselves remain optional.
                todo=[k];seen=set()
                while todo:
                    n=todo.pop()
                    if n==key: raise ResearchError('模块引用不能形成循环')
                    if n not in seen:
                        seen.add(n);todo.extend(data['modules'][n].get('uses',{}))
            previous=data['modules'].get(key,{})
            data['modules'][key]={'content':spec['content'],'sources':sources,'uses':uses,
                                  'context_revision':data['context_revision'],'revision':previous.get('revision',0)+1,'updated_at':now()}
        if not data.get('project'):
            from . import hub
            from .store import Store
            project_root=Path(workspace).expanduser().resolve()/'projects'/str(uuid.uuid5(uuid.NAMESPACE_URL,'giver:'+ident))
            if not (project_root/'.research/research.db').exists():store=Store.init(project_root,data['context'] or data['topic']);store.db.close()
            row=hub.register(Path(workspace)/'projects.json',project_root,data['topic'],mode='brainstorming',board=ident)
            data['project']=row['id']
        if spec.get('topic') and data.get('project'):
            from . import hub
            with hub.edit_registry(Path(workspace)/'projects.json') as projects:
                for project in projects:
                    if project['id']==data['project']:project['name']=data['topic']
        data['updated_at']=now()
        atomic(path(workspace,ident),dumps(data))
    return show(workspace,ident)


def packet(workspace, ident, module):
    if module not in MODULES: raise ResearchError('模块无效')
    board=show(workspace,ident)
    return {'space':board,'module':module,'skill':MODULES[module]['skill'],
            'instructions':'围绕主题与本次需求处理选定模块。其他模块为可选输入；引用时核对来源并明确 uses 版本，不要求先完成其他模块。更新仅写当前模块；不把方向判断自动写成工程承诺或科学证据。'}


def handoff(workspace, ident):
    board=show(workspace,ident)
    return {'space':board['id'],'topic':board['topic'],'context':board['context'],
            'directions':board['modules'].get('directions'),
            'proposal':board['modules'].get('proposal'),
            'instructions':'将用户选定方向转成 Engineering 工作包的 question/acceptance/protocol/stop_rule；保留来源和版本。只生成交接材料，不创建或切换正式项目，不自动运行。'}


def connect(workspace, ident, connection, progress=None, expected_updated_at=None):
    """Append a transfer backlink and optional progress module atomically, without changing ideas."""
    root=directory(workspace)
    with (root/'.lock').open('a') as lock:
        filelock.flock(lock,filelock.LOCK_EX)
        data=show(workspace,ident)
        existing=next((c for c in data.get('connections',[]) if c['transfer']==connection['transfer']),None)
        if existing:return data
        if expected_updated_at and expected_updated_at!=data['updated_at']:
            raise ResearchError('目标主题空间已变化；请预览并重新确认，不覆盖已有内容')
        data.setdefault('connections',[]).append(connection)
        if progress is not None:
            previous=data['modules'].get('progress',{})
            # Preserve earlier reports in a version archive, including user edits.
            archive=data.setdefault('progress_archive',[])
            if previous:archive.append(previous)
            data['modules']['progress']={'content':progress,'sources':[],'uses':{},'context_revision':data['context_revision'],
                'revision':previous.get('revision',0)+1,'updated_at':now(),'origin':connection}
        data['updated_at']=now();atomic(path(workspace,ident),dumps(data))
    return show(workspace,ident)
