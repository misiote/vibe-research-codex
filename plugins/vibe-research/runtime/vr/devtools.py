"""Independent read adapters. Each returns observations, never scientific conclusions."""
import base64
import json
import math
import os
import re
import shlex
import subprocess
import urllib.request
from urllib.parse import urlsplit,quote
from .store import ResearchError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ResearchError('服务重定向；请核对原始地址后重新关联')


def request(url, payload=None, token=None, basic=None):
    headers = {'Accept':'application/json','User-Agent':'VibeResearch/0.7.0'}
    if token: headers['Authorization']='Bearer '+token
    if basic: headers['Authorization']='Basic '+base64.b64encode(basic.encode()).decode()
    if payload is not None: headers['Content-Type']='application/json'
    req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=12) as response:
        raw=response.read(2_000_001)
        if len(raw)>2_000_000: raise ResearchError('服务返回内容过大，请缩小项目范围')
        return json.loads(raw)


def command(args):
    try: return subprocess.check_output(args,stderr=subprocess.DEVNULL,text=True,timeout=15)
    except (OSError,subprocess.SubprocessError): raise ResearchError('命令未完成；请检查工具安装、已有认证或 SSH 连通性')


def github(link):
    parts=urlsplit(link['tools']['github']).path.strip('/').split('/')
    if len(parts)!=2: raise ResearchError('GitHub 地址需为仓库首页')
    repo='/'.join(parts)
    # gh uses the user's existing authentication without copying credentials into research records.
    commits=json.loads(command(['gh','api','repos/'+repo+'/commits?per_page=5']))
    pulls=json.loads(command(['gh','api','repos/'+repo+'/pulls?state=open&per_page=5']))
    checks=json.loads(command(['gh','api','repos/'+repo+'/actions/runs?per_page=5']))
    return {'commits':[{'commit':c['sha'],'date':c['commit']['committer']['date']} for c in commits],
            'pulls':[{'number':p['number'],'title':p['title'],'url':p['html_url'],'commit':p['head']['sha']} for p in pulls],
            'checks':[{'id':r['id'],'status':r['status'],'conclusion':r['conclusion'],'commit':r['head_sha'],'url':r['html_url']} for r in checks.get('workflow_runs',[])],
            'limit':'各类最近 5 条，非完整仓库历史'}


def wandb(link):
    entity,project=urlsplit(link['tools']['wandb']).path.strip('/').split('/')
    key=os.environ.get('WANDB_API_KEY')
    if not key: raise ResearchError('需要本机 WANDB_API_KEY；不要在聊天或项目 JSON 填写密钥')
    query='query($entity:String!,$project:String!){project(name:$project,entityName:$entity){runs(first:10,order:"-createdAt"){edges{node{name displayName state commit summaryMetrics}}}}}'
    data=request('https://api.wandb.ai/graphql',{'query':query,'variables':{'entity':entity,'project':project}},basic='api:'+key)
    if data.get('errors') or not data.get('data',{}).get('project'): raise ResearchError('W&B 查询未通过；检查项目范围与认证')
    runs=[]
    for edge in data['data']['project']['runs']['edges']:
        r=edge['node']; summary=r.get('summaryMetrics') or '{}'
        if isinstance(summary,str): summary=json.loads(summary)
        runs.append({'id':r['name'],'name':r.get('displayName'),'state':r['state'],'commit':r.get('commit'),
                     'metrics':metrics(summary,link.get('metric_keys',[]))})
    return {'runs':runs,'limit':'最近 10 次运行；指标仅含明确选定的数值键'}


def metrics(values, keys):
    return {k:values[k] for k in keys if isinstance(values.get(k),(int,float)) and not isinstance(values[k],bool) and math.isfinite(values[k])}


def mlflow(link):
    base=link['tools']['mlflow'].rstrip('/')
    ids=link.get('mlflow_experiments',[])
    if not ids: raise ResearchError('需选择 mlflow_experiments；不会扫描服务器全部实验')
    data=request(base+'/api/2.0/mlflow/runs/search',{'experiment_ids':ids,'max_results':10,'order_by':['attributes.start_time DESC']},token=os.environ.get('MLFLOW_TRACKING_TOKEN'))
    runs=[]
    for r in data.get('runs',[]):
        info=r['info'];detail=r.get('data',{});tags={t['key']:t['value'] for t in detail.get('tags',[])}
        runs.append({'id':info['run_id'],'state':info['status'],'start_time':info.get('start_time'),
                     'commit':tags.get('mlflow.source.git.commit'),
                     'metrics':metrics({m['key']:m['value'] for m in detail.get('metrics',[])},link.get('metric_keys',[]))})
    return {'runs':runs,'limit':'所选实验最近 10 次运行；不采集参数、环境变量或完整日志'}


def ssh(link):
    remote=link['ssh'];alias=remote['host'];repo=remote['repo']
    # Only two fixed read-only git operations. Quote the path for the remote login shell.
    cmd='git -C '+shlex.quote(repo)+' rev-parse HEAD && git -C '+shlex.quote(repo)+' status --porcelain=v1 --untracked-files=normal'
    result=command(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','--',alias,cmd])
    lines=result.splitlines()
    if not lines or not re.fullmatch('[0-9a-f]{40,64}',lines[0]): raise ResearchError('远程 Git 返回格式无效')
    return {'host':alias,'repo':repo,'commit':lines[0],'changed_files':len(lines)-1,
            'editor':'vscode://vscode-remote/ssh-remote+'+alias+quote(repo,safe='/'),
            'note':'仅仓库快照，不执行训练；使用已有 SSH 配置、代理和已知主机信任。'}


ADAPTERS={'github':github,'wandb':wandb,'mlflow':mlflow,'ssh':ssh}
