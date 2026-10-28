"""Research-engineering links and work packages; never executes repository code."""
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor
from .store import now
from pathlib import Path
from urllib.parse import quote, urlsplit
from .store import ResearchError


def git(repo, *args):
    try:
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
    except (subprocess.SubprocessError, OSError): raise ResearchError('无法读取 Git 仓库及已提交版本')


def environment(spec):
    if not isinstance(spec, dict): raise ResearchError('工程关联需为 JSON 对象')
    if set(spec)-{'title','repo','tools','ssh','mlflow_experiments','metric_keys'}: raise ResearchError('工程关联包含未知字段')
    if not isinstance(spec.get('repo',''),str) or not isinstance(spec.get('title',''),str): raise ResearchError('名称和仓库需为文本')
    repo = Path(spec.get('repo', '')).expanduser().resolve()
    remote=spec.get('ssh')
    if not spec.get('repo') and not remote: raise ResearchError('需要本地 Git 仓库或已有 SSH 环境')
    commit=None
    if spec.get('repo'):
        if not repo.is_dir(): raise ResearchError('本地仓库不存在')
        repo = Path(git(repo,'rev-parse','--show-toplevel')).resolve()
        commit = git(repo,'rev-parse','HEAD')
    if remote:
        if not isinstance(remote,dict) or set(remote)!={'host','repo'} or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',str(remote.get('host',''))) or not isinstance(remote.get('repo'),str) or not remote['repo'].startswith('/') or any(c in remote['repo'] for c in '\n\r\x00'): raise ResearchError('SSH 需要已有 Host 别名和绝对仓库路径')
    tools = spec.get('tools', {})
    if not isinstance(tools, dict) or set(tools)-{'github', 'gitlab', 'wandb', 'mlflow'}: raise ResearchError('支持 GitHub/GitLab/W&B/MLflow 的项目 URL')
    for name, url in tools.items():
        try: p = urlsplit(url)
        except (ValueError, TypeError): raise ResearchError('工具 URL 无效')
        if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise ResearchError('工具 URL 需为不含凭据、查询或片段的 HTTP(S) 项目地址')
    for name,host in [('github','github.com'),('wandb','wandb.ai')]:
        if name in tools and (urlsplit(tools[name]).hostname!=host or len(urlsplit(tools[name]).path.strip('/').split('/'))!=2): raise ResearchError(name+' 需要官方主机上的项目首页 URL')
    if 'mlflow' in tools:
        u=urlsplit(tools['mlflow'])
        if u.scheme!='https' and u.hostname not in ('localhost','127.0.0.1','::1'): raise ResearchError('远端 MLflow 使用 HTTPS；SSH 隧道可指向本机 HTTP')
    experiments=spec.get('mlflow_experiments',[])
    keys=spec.get('metric_keys',[])
    if not isinstance(experiments,list) or len(experiments)>20 or not all(isinstance(x,str) and re.fullmatch('[A-Za-z0-9_-]{1,100}',x) for x in experiments): raise ResearchError('MLflow 实验 ID 无效')
    if not isinstance(keys,list) or len(keys)>30 or not all(isinstance(x,str) and 0<len(x)<=100 for x in keys): raise ResearchError('指标键无效')
    data = {'source_type':'engineering_link', 'repo':str(repo) if spec.get('repo') else None,'ssh':remote,'mlflow_experiments':experiments,'metric_keys':keys,'commit':commit,
            'tools':tools, 'editors':({k:k+'://file'+quote(str(repo),safe='/') for k in ('vscode','cursor')} if spec.get('repo') else {}),
            'note':'关联地址与版本，不代表远端认证、同步或实验已运行。'}
    return data


def link(store, spec):
    data=environment(spec)
    title=spec.get('title') or '工程仓库 · '+(Path(data['repo']).name if data['repo'] else data['ssh']['host'])
    ident=store.add_node('A',title,data)
    return {'id':ident,**data}



def task(store, spec):
    if not isinstance(spec, dict): raise ResearchError('工作包需为 JSON 对象')
    if spec.get('id'):
        if set(spec)-{'id','state','note','evidence'}: raise ResearchError('状态更新包含未知字段')
        node=store.get(spec['id']); data=node['data']
        if data.get('source_type')!='engineering_task': raise ResearchError('需要工程工作包编号')
        state=spec.get('state')
        if state not in ('planned','working','blocked','completed','abandoned') or not isinstance(spec.get('note'),str) or not spec['note'].strip(): raise ResearchError('状态更新需要有效状态与说明')
        evidence=spec.get('evidence',[])
        if not isinstance(evidence,list): raise ResearchError('evidence 需为列表')
        for ref in evidence: store.get(ref)
        if state=='completed' and not evidence: raise ResearchError('完成工作包需要可追踪的验收产物或记录')
        data={**data,'execution_status':state,'updates':data.get('updates',[])+[{'state':state,'note':spec['note'],'evidence':evidence,'at':now()}]}
        store.update_data(node['id'],data)
        for ref in evidence: store.add_edge(node['id'],'derived_from',ref)
        return {'id':node['id'],'status':state,'note':'工作包状态已更新；不改变科学假设状态。'}
    if set(spec)-{'title','question','acceptance','protocol','stop_rule','refs'}: raise ResearchError('工作包包含未知字段')
    for key in ('title', 'question', 'acceptance', 'protocol', 'stop_rule'):
        if not isinstance(spec.get(key),str) or not spec[key].strip(): raise ResearchError('工程工作包 '+key+' 必填')
    refs = spec.get('refs', [])
    if not isinstance(refs,list) or not refs: raise ResearchError('工作包需关联研究问题、假设、实验或工程仓库')
    for ref in refs: store.get(ref)
    ident = store.add_node('A',spec['title'],{**spec,'source_type':'engineering_task','execution_status':'planned'})
    for ref in refs: store.add_edge(ident,'derived_from',ref)
    return {'id':ident,'status':'planned','note':'工作包已计划；运行仍通过 experiment plan/ingest 保留配置、种子、提交和结果。'}


def snapshot(store):
    nodes = store.rows('nodes')
    return {'transfers':[n for n in nodes if n['data'].get('source_type')=='mode_transfer'],
            'links':[n for n in nodes if n['data'].get('source_type')=='engineering_link'],
            'tasks':[n for n in nodes if n['data'].get('source_type')=='engineering_task'],
            'observations':[n for n in nodes if n['data'].get('source_type')=='engineering_observation'],
            'experiments':[n for n in nodes if n['kind'] in ('X','R','F')],
            'note':'状态按需采集，各工具独立工作；版本关联不等于实验结论。'}


def sync(store, ident, network=False):
    from . import devtools
    link=store.get(ident)['data']
    if link.get('source_type')!='engineering_link': raise ResearchError('需要工程关联记录编号')
    observations={}
    if link.get('repo'):
        try:
            observations['git']={'status':'observed','commit':git(link['repo'],'rev-parse','HEAD'),
                                 'branch':git(link['repo'],'rev-parse','--abbrev-ref','HEAD'),
                                 'changed_files':len(git(link['repo'],'status','--porcelain=v1','--untracked-files=normal').splitlines()),'checked_at':now()}
        except ResearchError:
            observations['git']={'status':'unavailable','note':'本地仓库不可读','checked_at':now()}
    def observe(name):
        if not network: return name,{'status':'not_checked','note':'远端读取需显式 --network','checked_at':now()}
        try: return name,{'status':'observed','data':devtools.ADAPTERS[name](link),'checked_at':now()}
        except Exception as exc:
            # Never store raw transport errors, tokens or server response bodies.
            message=str(exc) if isinstance(exc,ResearchError) else '读取未完成；核对认证、服务地址或版本。'
            return name,{'status':'unavailable','note':message[:300],'checked_at':now()}
    names=[n for n in devtools.ADAPTERS if n in link.get('tools',{}) or n=='ssh' and link.get('ssh')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        observations.update(pool.map(observe,names))
    revisions={}
    if observations.get('git',{}).get('commit'): revisions.setdefault(observations['git']['commit'],[]).append('git')
    for name,item in observations.items():
        data=item.get('data',{})
        if data.get('commit'): revisions.setdefault(data['commit'],[]).append(name)
        for r in data.get('runs',[])+data.get('commits',[])+data.get('checks',[]):
            if r.get('commit'): revisions.setdefault(r['commit'],[]).append(name+':'+str(r.get('id','commit')))
    data={'source_type':'engineering_observation','link':ident,'observations':observations,
          'commit_groups':[{'commit':k,'sources':v} for k,v in revisions.items()],
          'note':'每个适配器独立采集；提交匹配只建立版本关联，不证明实验等价或结论成立。按需刷新，不是持续监控。'}
    node=store.add_node('A','开发进度 · '+now(),data);store.add_edge(node,'derived_from',ident)
    return {'id':node,**data}
