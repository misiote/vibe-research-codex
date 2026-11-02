"""Global workspace HTTP routes; no project resolution or research Store access.

The HTTP adapter owns Host/Origin/CSRF validation before calling these handlers.
A None result means this dispatcher does not own the route.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from . import resources, access, connections, workspace_config, runtime_env, network_access
from .store import ResearchError
from .workflows import capabilities
from .literature import ALL_SOURCES
from .web_response import reply


def read(route, path, registry, csrf_token, platform):
    if not registry:
        return None
    if route in ('/settings', '/settings/'):
        return reply(200,'text/html',(Path(__file__).parent/'templates/settings.html').read_bytes())
    if route == '/api/settings':
        data=workspace_config.snapshot(Path(registry).resolve().parent)
        data['skills']=resources.skill_catalog()
        data['capabilities']=capabilities()
        return reply(200,'application/json',json.dumps(data,ensure_ascii=False).encode())
    if re.fullmatch(r'/settings/skills/[a-z-]+',route):
        return reply(200,'text/html',resources.skill_page(route.rsplit('/',1)[-1]).encode())
    if re.fullmatch(r'/settings/connections/[a-z]+',route):
        return reply(200,'text/html',access.page(route.rsplit('/',1)[-1]).encode())
    from . import hub
    if route == '/':
        body=(Path(__file__).parent/'templates/hub.html').read_bytes()
        if platform=='win32':
            body=body.replace(b"box.checked=['arxiv','crossref','core']",b"box.checked=['arxiv','crossref','openalex']")
        return reply(200,'text/html',body)
    if route=='/giver':return reply(200,'text/html',(Path(__file__).parent/'templates/giver.html').read_bytes())
    if route=='/api/giver':
        from . import giver
        return reply(200,'application/json',json.dumps(giver.status(Path(registry).resolve().parent),ensure_ascii=False).encode())
    if route == '/api/workspace':
        return reply(200,'application/json',json.dumps({'registry':str(Path(registry).resolve()),'version':'0.2.0'}).encode())
    if route == '/api/session':
        return reply(200,'application/json',json.dumps({'token':csrf_token}).encode())
    if route in ('/lightning', '/lightning/'):
        return reply(200,'text/html',(Path(__file__).parent/'templates/lightning.html').read_bytes())
    if route in ('/brainstorming','/brainstorming/'):
        return reply(200,'text/html',(Path(__file__).parent/'templates/brainstorming.html').read_bytes())
    if route=='/api/brainstorm':
        from . import brainstorm
        q=parse_qs(urlsplit(path).query)
        data=brainstorm.show(Path(registry).resolve().parent,q['id'][0]) if q.get('id') else brainstorm.listing(Path(registry).resolve().parent,include_hidden=q.get('include_hidden',['0'])[0]=='1')
        return reply(200,'application/json',json.dumps(data,ensure_ascii=False).encode())
    if route == '/api/lightning':
        from . import lightning
        return reply(200,'application/json',json.dumps(lightning.listing(Path(registry).resolve().parent,parse_qs(urlsplit(path).query).get('mode',[None])[0]),ensure_ascii=False).encode())
    if route == '/engineering':
        return reply(200,'text/html',(Path(__file__).parent/'templates/engineering.html').read_bytes())
    if route == '/api/projects':
        return reply(200,'application/json',json.dumps(hub.catalog(registry,include_removed=True),ensure_ascii=False).encode())
    return None


def write(route, data, registry):
    if not registry:
        return None
    if route=='/api/preflight':
        if set(data)!={'providers'} or not isinstance(data['providers'],list) or not all(isinstance(p,str) and p in ALL_SOURCES for p in data['providers']):raise ResearchError('来源无效')
        return reply(200,'application/json',json.dumps(workspace_config.check(Path(registry).resolve().parent,data['providers']),ensure_ascii=False).encode())
    if route=='/api/configure':
        if set(data)!={'provider','value'} or data.get('provider') not in connections.PROVIDERS or not isinstance(data.get('value'),str) or not 0<len(data['value'])<=4096:raise ResearchError('凭据格式无效')
        connections.save(data['provider'],data['value'],connections.default_backend())
        workspace_config.invalidate(Path(registry).resolve().parent,data['provider'])
        return reply(200,'application/json',json.dumps({'saved':True,'backend':connections.backend_info(),'note':'已安全保存到本机；请重新运行实际连接预检。'},ensure_ascii=False).encode())
    if route=='/api/network-profile':
        fields={'action','provider','institution_id','institution_name','portal_url','method','declared_network'}
        if set(data)!=fields or data.get('action')!='configure' or not all(isinstance(data.get(k),str) for k in fields):raise ResearchError('机构网络配置格式无效')
        result=network_access.configure(data['provider'],data['institution_id'],data['institution_name'],data['portal_url'],data['method'],data['declared_network'])
        return reply(200,'application/json',json.dumps(result,ensure_ascii=False).encode())
    if route=='/api/runtime':
        if data!={'action':'prepare_pdf'}:raise ResearchError('运行时操作无效')
        return reply(200,'application/json',json.dumps(runtime_env.prepare(),ensure_ascii=False).encode())
    return None
