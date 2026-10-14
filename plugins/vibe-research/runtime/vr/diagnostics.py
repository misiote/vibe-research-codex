"""Shareable diagnostics with a strict field allowlist; no queries, titles, paths or credentials."""
import json,platform,sys
from pathlib import Path
from .store import Store,ResearchError,now
from . import retrieval,connections

def export(root,destination):
    s=Store(root)
    try:doctor=s.doctor();revision=s.revision()
    finally:s.db.close()
    queue=retrieval.snapshot(root)
    states={}
    for run in queue['runs']:
        for task in run['tasks']:states[task['status']]=states.get(task['status'],0)+1
    data={'format':'vibe-research-diagnostics','version':1,'generated_at':now(),'python':platform.python_version(),'platform':sys.platform,'revision':revision,'integrity_ok':doctor['ok'],'integrity_error_count':len(doctor.get('errors',[])),'retrieval':{'worker_alive':queue['worker_alive'],'recent_task_states':states},'credentials':[{'provider':p['provider'],'configured':p['configured'],'storage':p['source']} for p in connections.status()['providers']],'note':'不含原始错误、项目标题、查询、文件路径、响应正文、IP、代理地址或凭据；需用户明确分享才发送。'}
    path=Path(destination)
    with open(path,'x') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    return {'diagnostics':str(path.resolve()),'note':data['note']}
