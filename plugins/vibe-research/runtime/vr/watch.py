"""Loopback live view with explicit CLI-backed, origin-checked project actions."""
import json
import secrets
import tempfile
import subprocess
import sys
import re
import mimetypes
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .store import Store, ResearchError
from . import activity, progress, graph, resources, retrieval, access
from . import workspace_routes, project_routes


def state(root):
    s = Store(root)
    try:
        s.db.execute('BEGIN')
        p = progress.snapshot(s)
        nodes = {n['id']: {'id': n['id'], 'title': n['title'], 'kind':n['kind']} for n in s.rows('nodes')}
        live = activity.snapshot(s.root, nodes)
        return {'question': p['question'], 'revision': p['revision'], 'counts': p['counts'],
                'nodes': nodes, 'retrieval': retrieval.snapshot(root), 'papers': [{**p, 'resources': resources.links(s, s.get(p['id']))} for p in p['papers']], 'branches': p['branches'], **live}
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
                if route.startswith('/static/') and (sys.platform=='win32' or route.endswith('.css') or route in ('/static/mode_bridge.js','/static/actions.js','/static/giver.js','/static/giver_view.js','/static/project_nav.js','/static/workspace_ui.js','/static/settings.js')):
                    directory=Path(__file__).parent/'static'
                    asset=(directory/route[len('/static/'):]).resolve()
                    if not asset.is_relative_to(directory.resolve()) or not asset.is_file():
                        return self.reply(404,'text/plain',b'Not found')
                    kind={'.mjs':'application/javascript','.wasm':'application/wasm'}.get(asset.suffix,mimetypes.guess_type(str(asset))[0] or 'application/octet-stream')
                    return self.reply(200,kind,asset.read_bytes())
                result=workspace_routes.read(route,self.path,registry,csrf_token,sys.platform)
                if result is not None:
                    return self.reply(*result)
                if registry:
                    from . import hub
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
                if route == '/engineering':
                    self.project_prefix=''
                    return self.reply(200,'text/html',(Path(__file__).parent/'templates/engineering.html').read_bytes())
                if route == '/explore':
                    self.project_prefix=''  # This template derives its own project prefix from the URL.
                    return self.reply(200,'text/html',(Path(__file__).parent/'templates/explore.html').read_bytes())
                result=project_routes.read(route,self.path,selected_root)
                if result is not None:
                    return self.reply(*result)
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
            except (ResearchError, ValueError, TypeError):
                return self.reply(404, 'text/plain', '资源不存在或未通过校验'.encode())
            except Exception:
                return self.reply(503, 'application/json', b'{"error":"state_unavailable"}')

        def do_POST(self):
            self.project_prefix=''
            host=self.headers.get('Host','')
            allowed={'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}
            if host not in allowed or self.headers.get('Origin')!='http://'+host or not secrets.compare_digest(self.headers.get('X-VR-Token',''),csrf_token):
                return self.reply(403,'application/json',b'{"error":"Request origin or session rejected"}')
            research_route=re.fullmatch(r'/p/(p[a-f0-9]{12})/api/research',self.path)
            access_route=re.fullmatch(r'/p/(p[a-f0-9]{12})/api/access',self.path)
            retrieval_route=re.fullmatch(r'/p/(p[a-f0-9]{12})/api/retrieval',self.path)
            global_route=self.path in ('/api/manage','/api/preflight','/api/configure','/api/runtime','/api/network-profile','/api/lightning','/api/brainstorm','/api/bridge','/api/giver')
            if not registry or (not global_route and not retrieval_route and not access_route and not research_route) or self.headers.get('Content-Type')!='application/json':
                return self.reply(404,'application/json',b'{"error":"Unsupported operation"}')
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=(1048576 if research_route or self.path in ('/api/lightning','/api/brainstorm','/api/bridge','/api/giver') else 8192):raise ResearchError('请求大小无效')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ResearchError('请求格式无效')
                action=data.get('action')
                result=workspace_routes.write(self.path,data,registry)
                if result is not None:
                    return self.reply(*result)
                if self.path in ('/api/lightning','/api/brainstorm','/api/bridge','/api/giver') or research_route:
                    from . import hub
                    base=[sys.executable,str(Path(__file__).resolve().parents[1]/'bin/vr')]
                    payload=None
                    if self.path=='/api/giver':
                        if set(data)!={'action','spec'} or not isinstance(data['spec'],dict):raise ResearchError('giver 请求无效')
                        args=base+['giver','--workspace',str(Path(registry).resolve().parent)]
                        payload={'action':action,'spec':data['spec']}
                    elif self.path=='/api/bridge':
                        if set(data)!={'action','spec'} or action not in ('preview','transfer') or not isinstance(data['spec'],dict):raise ResearchError('转化请求无效')
                        args=base+['bridge',action,'--workspace',str(Path(registry).resolve().parent)]
                        payload=data['spec']
                    elif self.path=='/api/brainstorm':
                        if action not in ('start','update','packet','handoff') or set(data)-{'action','id','spec','module'}: raise ResearchError('主题空间操作无效')
                        args=base+['brainstorm',action,'--workspace',str(Path(registry).resolve().parent)]
                        if action!='start': args+=[str(data.get('id',''))]
                        if action=='packet':args+=['--module',str(data.get('module',''))]
                        if action in ('start','update'):
                            payload=data.get('spec',{})
                            if not isinstance(payload,dict): raise ResearchError('主题空间格式无效')
                    elif self.path=='/api/lightning':
                        if action not in ('start','update','discard','packet') or set(data)-{'action','id','draft'}: raise ResearchError('草稿操作无效')
                        if action!='start' and not re.fullmatch(r'L[a-f0-9]{12}',str(data.get('id',''))): raise ResearchError('草稿编号无效')
                        args=base+['lightning',action,'--workspace',str(Path(registry).resolve().parent)]
                        if action!='start': args+=[data['id']]
                        if action in ('start','update'):
                            payload=data.get('draft',{})
                            if not isinstance(payload,dict): raise ResearchError('草稿格式无效')
                    else:
                        project=next((p for p in hub.entries(registry) if p['id']==research_route[1] and p['lifecycle']=='active'),None)
                        if not project: raise ResearchError('请选择活动项目')
                        args=base+['--project',project['root']]
                        if action=='reading_depth' and set(data)=={'action','id','depth','reason'}:
                            if not all(isinstance(data[k],str) for k in ('id','depth','reason')): raise ResearchError('阅读选择无效')
                            args+=['reading','depth',data['id'],data['depth'],'--reason',data['reason']]
                        elif action=='history_search' and set(data)=={'action','spec'}:
                            spec=data['spec']
                            if not isinstance(spec,dict) or set(spec)-{'topic','scope','subtopic','aliases','since','until'}: raise ResearchError('主题查询格式无效')
                            args+=['history','search','--background']
                            for key,value in spec.items():
                                if not isinstance(value,str): raise ResearchError('查询字段需为文本')
                                if value: args+=['--'+key,value]
                        elif action=='engineering_sync' and set(data)=={'action','id','network'}:
                            if not isinstance(data['network'],bool): raise ResearchError('network 需为布尔值')
                            args+=['engineering','sync',str(data['id'])]+(['--network'] if data['network'] else [])
                        elif action in ('engineering_link','engineering_task') and set(data)=={'action','spec'}:
                            payload=data['spec']
                            if not isinstance(payload,dict): raise ResearchError('工程记录需为 JSON 对象')
                            args+=['engineering',action.split('_')[1]]
                        elif action in ('history_add','direction_evaluate','direction_save') and set(data)=={'action','spec'}:
                            payload=data['spec']
                            if not isinstance(payload,dict): raise ResearchError('研究记录格式无效')
                            args+= {'history_add':['history','add'],'direction_evaluate':['direction','evaluate'],'direction_save':['direction','save']}[action]
                        else: raise ResearchError('研究操作无效')
                    with tempfile.TemporaryDirectory(prefix='vr-ui-') as tmp:
                        if payload is not None:
                            input_path=Path(tmp)/'input.json';input_path.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
                            args+= ['--input',str(input_path)] if self.path in ('/api/lightning','/api/brainstorm','/api/bridge','/api/giver') else [str(input_path)]
                        result=subprocess.run(args,capture_output=True,text=True,encoding='utf8',timeout=60 if action=='engineering_sync' else 30)
                    if result.returncode: raise ResearchError(result.stderr.strip()[:1000] or '操作未完成')
                    return self.reply(200,'application/json',result.stdout.encode())
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
                result=subprocess.run(args,capture_output=True,text=True,encoding='utf8',timeout=60 if action=='engineering_sync' else 30)
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
