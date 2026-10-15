"""Loopback live view with explicit CLI-backed, origin-checked project actions."""
import json
import secrets
import subprocess
import sys
import re
import mimetypes
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .store import Store, ResearchError
from . import activity, progress, graph, resources, retrieval, access, connections, integrations, runtime_env, network_access
from .workflows import capabilities


def connection_view(store):
    from .connections import status
    data = status()
    data['network_access'] = network_access.status()
    path = store.root / 'research/integrations.json'
    try:
        saved = json.loads(path.read_text(encoding="utf8"))
        data['checked_at'] = saved.get('generated_at')
        data['checks'] = [r for r in saved.get('items',[]) if r.get('name') in {'SQLite / 研究图','PDF 精读','openalex','s2','arxiv','crossref','core','huggingface','wos','scopus','unpaywall','Zotero'}]
    except (OSError,ValueError):
        data['checks'] = []
    data['access_checks']=access.view(store.root)
    data['access_guides']=[{'provider':p,'title':g['title'],'url':'/settings/connections/'+p} for p,g in access.GUIDES.items()]
    data['runtime']=integrations.runtime_status()
    return data


def state(root):
    s = Store(root)
    try:
        s.db.execute('BEGIN')
        p = progress.snapshot(s)
        nodes = {n['id']: {'id': n['id'], 'title': n['title']} for n in s.rows('nodes')}
        live = activity.snapshot(s.root, nodes)
        return {'question': p['question'], 'revision': p['revision'], 'counts': p['counts'],
                'nodes': nodes, 'retrieval': retrieval.snapshot(root), 'connections': connection_view(s), 'settings_skills': resources.skill_catalog(), 'capabilities': capabilities(), 'papers': [{**p, 'resources': resources.links(s, s.get(p['id']))} for p in p['papers']], 'branches': p['branches'], **live}
    finally:
        s.db.rollback()
        s.db.close()


def server(root, port, registry=None):
    root = Path(root).resolve()
    csrf_token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            allowed = {'127.0.0.1:' + str(self.server.server_port), 'localhost:' + str(self.server.server_port)}
            if self.headers.get('Host') not in allowed:
                return self.reply(403, 'text/plain', b'Local access only')
            route = urlsplit(self.path).path
            self.project_prefix = ''
            selected_root = root
            try:
                if sys.platform=='win32' and route.startswith('/static/'):
                    directory=Path(__file__).parent/'static'
                    asset=(directory/route[len('/static/'):]).resolve()
                    if not asset.is_relative_to(directory.resolve()) or not asset.is_file():
                        return self.reply(404,'text/plain',b'Not found')
                    kind={'.mjs':'application/javascript','.wasm':'application/wasm'}.get(asset.suffix,mimetypes.guess_type(str(asset))[0] or 'application/octet-stream')
                    return self.reply(200,kind,asset.read_bytes())
                if registry:
                    from . import hub
                    if route == '/':
                        body=(Path(__file__).parent/'templates/hub.html').read_bytes()
                        if sys.platform=='win32':
                            body=body.replace(b"box.checked=['arxiv','crossref','core']",b"box.checked=['arxiv','crossref','openalex']")
                        return self.reply(200,'text/html',body)
                    if route == '/api/workspace':
                        return self.reply(200,'application/json',json.dumps({'registry':str(Path(registry).resolve()),'version':'0.2.0'}).encode())
                    if route == '/api/session':
                        return self.reply(200,'application/json',json.dumps({'token':csrf_token}).encode())
                    if route == '/api/projects':
                        return self.reply(200,'application/json',json.dumps(hub.catalog(registry,include_removed=True),ensure_ascii=False).encode())
                    match=re.match(r'^/p/(p[a-f0-9]{12})(/.*)$',route)
                    if not match: return self.reply(404,'text/plain',b'Unknown project')
                    project=next((p for p in hub.entries(registry) if p['id']==match[1]),None)
                    if not project: return self.reply(404,'text/plain',b'Unknown project')
                    selected_root=Path(project['root'])
                    self.project_prefix='/p/'+match[1]
                    route=match[2]
                if re.fullmatch(r'/settings/connections/[a-z]+',route):
                    return self.reply(200,'text/html',access.page(route.rsplit('/',1)[-1]).encode())
                if re.fullmatch(r'/settings/skills/[a-z-]+',route):
                    return self.reply(200,'text/html',resources.skill_page(route.rsplit('/',1)[-1]).encode())
                if re.fullmatch(r'/retrieval/report/S[a-f0-9]{12}',route):
                    return self.reply(200,'text/html',retrieval.report(selected_root,route.rsplit('/',1)[-1]).encode())
                if re.fullmatch(r'/api/retrieval/export/S[a-f0-9]{12}',route):
                    data=retrieval.snapshot(selected_root,route.rsplit('/',1)[-1],True)
                    if not data['runs']:raise ResearchError('检索不存在')
                    return self.reply(200,'application/json',json.dumps(data['runs'][0],ensure_ascii=False).encode())
                if route == '/api/history':
                    q=parse_qs(urlsplit(self.path).query)
                    data=activity.history(selected_root,int(q.get('limit',['50'])[0]),int(q.get('offset',['0'])[0]),q.get('since',[None])[0],q.get('until',[None])[0])
                    return self.reply(200,'application/json',json.dumps(data,ensure_ascii=False).encode())
                if route == '/api/state':
                    return self.reply(200, 'application/json', json.dumps(state(selected_root), ensure_ascii=False).encode())
                if route == '/':
                    return self.reply(200, 'text/html', (Path(__file__).parent / 'templates/watch.html').read_bytes())
                if re.fullmatch(r'/(node|reading)/[A-Z]+[0-9]+', route):
                    kind, ident = route.strip('/').split('/')
                    s = Store(selected_root)
                    try:
                        s.db.execute('BEGIN')
                        body = resources.reading_page(s, ident) if kind == 'reading' else resources.node_page(s, ident)
                    finally:
                        s.db.close()
                    return self.reply(200, 'text/html', body.encode())
                if sys.platform=='win32' and re.fullmatch(r'/pdf/[a-f0-9]{64}',route):
                    s=Store(selected_root)
                    try:
                        path,name=resources.registered_file(s,route.split('/')[-1])
                        if path.suffix.lower()!='.pdf':raise ResearchError('不是 PDF 文件')
                    finally:s.db.close()
                    template=(Path(__file__).parent/'templates/pdf_viewer.html').read_text(encoding='utf8')
                    body=template.replace('__TITLE__',html.escape(name)).replace('__FILE__','/file/'+route.split('/')[-1])
                    return self.reply(200,'text/html',body.encode())
                if re.fullmatch(r'/file/[a-f0-9]{64}', route):
                    s = Store(selected_root)
                    try:
                        path, name = resources.registered_file(s, route.split('/')[-1])
                        content = path.read_bytes()
                    finally:
                        s.db.close()
                    suffix = path.suffix.lower()
                    kind = 'application/pdf' if suffix == '.pdf' else 'text/plain' if suffix in {'.txt','.md','.py','.json','.yaml','.csv','.log'} else 'application/octet-stream'
                    return self.reply(200, kind, content)
                if route == '/graph':
                    s = Store(selected_root)
                    try:
                        s.db.execute('BEGIN')
                        body = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>' + graph.BASE + '</style><body>' + graph.fragment(s) + '</body></html>'
                    finally:
                        s.db.rollback()
                        s.db.close()
                    return self.reply(200, 'text/html', body.encode())
                return self.reply(404, 'text/plain', b'Not found')
            except ResearchError:
                return self.reply(404, 'text/plain', '资源不存在或未通过校验'.encode())
            except Exception:
                return self.reply(503, 'application/json', b'{"error":"state_unavailable"}')

        def do_POST(self):
            self.project_prefix=''
            host=self.headers.get('Host','')
            allowed={'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}
            if host not in allowed or self.headers.get('Origin')!='http://'+host or not secrets.compare_digest(self.headers.get('X-VR-Token',''),csrf_token):
                return self.reply(403,'application/json',b'{"error":"Request origin or session rejected"}')
            access_route=re.fullmatch(r'/p/(p[a-f0-9]{12})/api/access',self.path)
            retrieval_route=re.fullmatch(r'/p/(p[a-f0-9]{12})/api/retrieval',self.path)
            global_route=self.path in ('/api/manage','/api/preflight','/api/configure','/api/runtime','/api/network-profile')
            if not registry or (not global_route and not retrieval_route and not access_route) or self.headers.get('Content-Type')!='application/json':
                return self.reply(404,'application/json',b'{"error":"Unsupported operation"}')
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=8192:raise ResearchError('请求大小无效')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ResearchError('请求格式无效')
                action=data.get('action')
                if self.path=='/api/preflight':
                    if set(data)!={'providers'} or not isinstance(data['providers'],list) or not all(isinstance(p,str) and p in retrieval.literature.ALL_SOURCES for p in data['providers']):raise ResearchError('来源无效')
                    return self.reply(200,'application/json',json.dumps(integrations.preflight(data['providers']),ensure_ascii=False).encode())
                if self.path=='/api/configure':
                    if set(data)!={'provider','value'} or data.get('provider') not in connections.PROVIDERS or not isinstance(data.get('value'),str) or not 0<len(data['value'])<=4096:raise ResearchError('凭据格式无效')
                    connections.save(data['provider'],data['value'],connections.default_backend())
                    return self.reply(200,'application/json',json.dumps({'saved':True,'backend':connections.backend_info(),'note':'已安全保存到本机；请重新运行实际连接预检。'},ensure_ascii=False).encode())
                if self.path=='/api/network-profile':
                    fields={'action','provider','institution_id','institution_name','portal_url','method','declared_network'}
                    if set(data)!=fields or data.get('action')!='configure' or not all(isinstance(data.get(k),str) for k in fields):raise ResearchError('机构网络配置格式无效')
                    result=network_access.configure(data['provider'],data['institution_id'],data['institution_name'],data['portal_url'],data['method'],data['declared_network'])
                    return self.reply(200,'application/json',json.dumps(result,ensure_ascii=False).encode())
                if self.path=='/api/runtime':
                    if data!={'action':'prepare_pdf'}:raise ResearchError('运行时操作无效')
                    return self.reply(200,'application/json',json.dumps(runtime_env.prepare(),ensure_ascii=False).encode())
                args=[sys.executable,str(Path(__file__).resolve().parents[1]/'bin/vr'),'hub']
                if access_route:
                    from . import hub
                    project=next((p for p in hub.entries(registry) if p['id']==access_route[1] and p['lifecycle']=='active'),None)
                    if not project or data.get('provider') not in access.GUIDES:raise ResearchError('来源或项目无效')
                    field='query' if action=='verify' else 'network'
                    if action not in ('verify','context') or set(data)!={'action','provider',field} or not isinstance(data[field],str) or not 0<len(data[field])<=1000:raise ResearchError('无效的配置操作')
                    args=[sys.executable,str(Path(__file__).resolve().parents[1]/'bin/vr'),'--project',project['root'],'integrations',action,data['provider'],'--'+field,data[field]]
                elif retrieval_route:
                    from . import hub
                    project=next((p for p in hub.entries(registry) if p['id']==retrieval_route[1] and p['lifecycle']=='active'),None)
                    if not project:raise ResearchError('请选择有效的活动项目')
                    args=[sys.executable,str(Path(__file__).resolve().parents[1]/'bin/vr'),'--project',project['root'],'retrieval']
                    if action=='launch':
                        if set(data)!={'action'}:raise ResearchError('不支持的字段')
                        args+=['launch']
                    elif action in ('pause','resume','retry','exclude'):
                        pattern=r'S[a-f0-9]{12}' if action in ('pause','resume') else r'T[a-f0-9]{12}'
                        if set(data)!={'action','id','reason'} or not isinstance(data['id'],str) or not re.fullmatch(pattern,data['id']) or not isinstance(data['reason'],str) or not 0<len(data['reason'].strip())<=2000:raise ResearchError('请填写有效操作与原因')
                        args += [action,data['id'],'--reason',data['reason']]
                    else:raise ResearchError('不支持的检索操作')
                elif action=='create':
                    if set(data)!={'action','name','question','providers','request_id'}:raise ResearchError('不支持的配置字段')
                    if not all(isinstance(data[k],str) and 0<len(data[k])<=2000 for k in ('name','question','request_id')):raise ResearchError('请填写有效项目内容')
                    if not isinstance(data['providers'],list) or not all(isinstance(p,str) and p in retrieval.literature.ALL_SOURCES for p in data['providers']):raise ResearchError('来源无效')
                    args+=['create','--registry',str(registry),'--name',data['name'],'--question',data['question'],'--request-id',data['request_id']]
                    for provider in data['providers']:args+=['--provider',provider]
                elif action in ('archive','restore','remove'):
                    if set(data)!={'action','id','reason'} or not isinstance(data['id'],str) or not re.fullmatch(r'p[a-f0-9]{12}',data['id']) or not isinstance(data['reason'],str) or not 0<len(data['reason'])<=2000:raise ResearchError('项目操作格式无效')
                    args += [action,data['id'],'--registry',str(registry),'--reason',data['reason']]
                else:raise ResearchError('此操作尚未开放')
                result=subprocess.run(args,capture_output=True,text=True,encoding='utf8',timeout=30)
                if result.returncode:
                    raise ResearchError(result.stderr.strip()[:500] or '操作未完成')
                return self.reply(200,'application/json',result.stdout.encode())
            except (ResearchError,ValueError,TypeError,subprocess.TimeoutExpired) as exc:
                return self.reply(400,'application/json',json.dumps({'error':str(exc)},ensure_ascii=False).encode())

        def reply(self, code, kind, content):
            if getattr(self,'project_prefix','') and kind in ('text/html','application/json'):
                prefix=self.project_prefix
                if kind=='application/json':
                    def scoped(value):
                        if isinstance(value,dict): return {k:scoped(v) for k,v in value.items()}
                        if isinstance(value,list): return [scoped(v) for v in value]
                        if isinstance(value,str) and re.match(r'^/(node|reading|file|pdf|graph|settings)(/|\?|$)',value): return prefix+value
                        return value
                    content=json.dumps(scoped(json.loads(content)),ensure_ascii=False).encode()
                else:
                    text=content.decode()
                    text=re.sub(r"([\"'])/(api/state|graph|node/|reading/|file/|pdf/|settings/)",lambda m:m[1]+prefix+'/'+m[2],text)
                    text=text.replace('href="/"','href="'+prefix+'/"')
                    if '<body>' in text and '<div class="app">' in text:
                        text=text.replace('<body>','<body><nav class="workspace-back"><a href="/">← 项目</a></nav>',1)
                    content=text.encode()
            self.send_response(code)
            self.send_header('Content-Type', kind + ('; charset=utf-8' if kind.startswith('text/') or kind in ('application/json','application/javascript') else ''))
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            policy = "default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; worker-src 'self' blob:; img-src 'self' data: blob:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'"
            if sys.platform != 'win32':
                policy = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'"
            self.send_header('Content-Security-Policy', policy)
            self.end_headers()
            self.wfile.write(content)
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def serve(root, port=8765, open_browser=False, registry=None):
    http = server(root, port, registry)
    print('研究过程视图：http://127.0.0.1:' + str(http.server_port) + '\n保持此命令运行；Ctrl+C 关闭。', flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open('http://127.0.0.1:' + str(http.server_port))
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http.server_close()
    return {'stopped': True}
