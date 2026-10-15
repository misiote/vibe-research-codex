"""On-demand institutional onboarding; no browser cookie or password reuse."""
import json,hashlib,os,platform,time,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from html import escape
from .store import ResearchError,atomic,now
from . import connections,request_gate,network_access

GUIDES={
 'wos':{'title':'Web of Science Starter','url':'https://developer.clarivate.com/apis/wos-starter','condition':'先申请官方免费试用或学校已授权套餐；不同套餐的引文计数权限不同。','steps':['在官方开发者门户注册应用并申请 Starter key。','确认免费试用或既有机构权益；不自动购买套餐。','回到工作台设置页，在 Web of Science 卡片中保存 key。','用一个明确主题做真实查询；通过后可进入分页检索，但不代表全文权限。']},
 'scopus':{'title':'Scopus','url':'https://dev.elsevier.com/','condition':'需要本人 API key；机构字段还取决于订阅 entitlement，以及 API 请求实际经过的网络出口。','steps':['选择机构与接入方式。中科院自动化所案例使用官方图书馆远程入口 https://webvpn.ia.ac.cn/ 。','在 Elsevier 官方门户申请本人 API key，并在本机保存。机构账号、密码和验证码只在机构或 Elsevier 官方页面输入。','网页入口只代理浏览器访问，不能转发 Python API。校外自动检索应使用能够改变系统路由的校园 VPN，或者由 Elsevier 签发的 Institutional Token。','智能路由会让 Scopus API 绕过应用层全局代理，由操作系统校园 VPN/校内路由承载；其他公开来源仍可沿用用户代理。','运行一次真实 API 查询确认权限。401 通常需检查 key；403 需检查机构 entitlement、网络出口或 Institutional Token。']},
 'unpaywall':{'title':'Unpaywall 开放全文定位','url':'https://unpaywall.org/products/api','condition':'免费 DOI 查询，需要发送本人联系邮箱给服务方；不支持旧关键词搜索接口。','steps':['在工作台设置页填写愿意发送给服务方的本人联系邮箱。','输入 DOI 做单条验证；没有 OA 位置也可能是正常结果。','启用后，覆盖检索会为候选 DOI 建立独立定位任务。','只使用返回的合法开放位置；不会绕过出版商授权。']},
 'campus':{'title':'校园数据库与北大案例','url':'https://dbnav.lib.pku.edu.cn/','condition':'当前执行主机能否访问校园资源，需要单独验证。主页 200、校园标识或 SSO 成功均不能证明全文权限。','steps':['确认请求在本机执行，而不是 SSH 或云端。','从学校官方导航进入目标库；北大学位论文入口为 https://thesis.lib.pku.edu.cn/ 。','核验一条检索和一篇有权访问的全文；门户可达不算通过。','校内失败时检查目标的代理分流；离校后按校方规定使用 VPN/CARSI。','没有开放 API 时使用允许的 RIS/BibTeX/PDF 导出，保留来源；不推测内部接口。']},
}

def context(root,provider,network):
    if provider not in GUIDES or network not in ('campus','off_campus','unknown'):raise ResearchError('无效的来源或网络条件')
    p=Path(root)/'research/access-context.json';data=json.loads(p.read_text(encoding="utf8")) if p.exists() else {}
    data[provider]={'network':network,'execution':'local','updated_at':now()};atomic(p,json.dumps(data,ensure_ascii=False,indent=2))
    return {'saved':True,'note':'已保存网络条件；尚未证明目标数据可访问'}

def saved_context(root,provider):
    p=Path(root)/'research/access-context.json'
    return json.loads(p.read_text(encoding="utf8")).get(provider,{}) if p.exists() else {}

def environment_fingerprint():
    # Used only to invalidate checks; no IP/SSID, interface name or raw proxy address is saved.
    snapshot=network_access.environment_snapshot()
    return hashlib.sha256((platform.node()+snapshot['fingerprint']).encode()).hexdigest()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ResearchError('来源发生跳转；未向新地址转发凭据，请核对官方 API 地址')

def verify(root,provider,query):
    if provider not in ('wos','scopus','unpaywall') or not query.strip() or len(query)>1000:raise ResearchError('需要有效来源与单条测试查询')
    token,auth_source=connections.credential(provider)
    result={'provider':provider,'checked_at':now(),'environment':environment_fingerprint(),'network_context':saved_context(root,provider),'auth_source':auth_source,'status':'needs_auth','note':'尚未配置凭据，请在本机终端引导中完成；不要粘贴到聊天。'}
    if token:
        headers={'Accept':'application/json','User-Agent':'VibeResearch/0.2'}
        insttoken=None;insttoken_source='anonymous'
        if provider=='scopus':
            url='https://api.elsevier.com/content/search/scopus?'+urllib.parse.urlencode({'query':query,'count':1});headers['X-ELS-APIKey']=token
            insttoken,insttoken_source=connections.credential('scopus_insttoken')
            if insttoken:headers['X-ELS-Insttoken']=insttoken
        elif provider=='wos':url='https://api.clarivate.com/apis/wos-starter/v1/documents?'+urllib.parse.urlencode({'q':query,'limit':1,'page':1});headers['X-ApiKey']=token
        else:
            if not query.startswith('10.') or '/' not in query:raise ResearchError('Unpaywall 需要 DOI，不能用关键词代替')
            url='https://api.unpaywall.org/v2/'+urllib.parse.quote(query,safe='/')+'?'+urllib.parse.urlencode({'email':token})
        try:
            request_gate.admit(provider)
            routing=network_access.decision(provider,url)
            with network_access.open_request(urllib.request.Request(url,headers=headers),provider,timeout=15,handlers=(NoRedirect(),)) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise ResearchError('响应超出单条验收大小')
                data=json.loads(raw)
                if not isinstance(data,dict):raise ResearchError("响应不是有效的数据对象")
            if provider=='scopus':valid=isinstance(data.get('search-results'),dict) and 'opensearch:totalResults' in data['search-results']
            elif provider=='wos':valid=isinstance(data.get('hits'),list) and isinstance(data.get('metadata'),dict)
            else:valid=isinstance(data.get('doi'),str) and isinstance(data.get('is_oa'),bool)
            if not valid:raise ResearchError('响应缺少预期数据字段')
            result.update(status='passed',network_route=routing['route'],route_reason=routing['reason'],
                          institutional_token=bool(insttoken),institutional_token_source=insttoken_source,
                          note='单次元数据查询通过；全文和完整分页权限尚未验收。' if provider!='unpaywall' else ('DOI 查询通过；返回开放位置。' if data['is_oa'] else 'DOI 查询通过；此记录未提供开放全文。'))
        except request_gate.Deferred as exc:result.update(status='waiting',next_retry=exc.until,note='共享冷却中；保留来源与原查询，不代表检索完成。')
        except urllib.error.HTTPError as exc:
            note='需要核验权限或等待服务恢复；原始响应未写入记录。'
            if provider=='scopus' and exc.code==401:note='Scopus 拒绝了 API 身份；请核对 API key，网页登录状态不能替代 API key。'
            if provider=='scopus' and exc.code==403:note='Scopus API 身份有效但权限不足；请核对机构订阅、校园 VPN 的实际出口，或申请 Institutional Token。'
            result.update(status='waiting' if exc.code==429 or exc.code>=500 else 'blocked',http=exc.code,note=note)
            if exc.code==429:
                from .literature import retry_delay
                due=time.time()+(retry_delay(exc.headers.get('Retry-After','')) or 60);request_gate.cool(provider,due);result['next_retry']=due
        except (OSError,ValueError,ResearchError):result.update(status='blocked',note='网络、返回格式或配置未通过；检查执行主机、校园条件和官方权限。')
    # Never persist secret, request URL or an echoed response body.
    result['query']=query
    p=Path(root)/'research/access-checks.json';saved=json.loads(p.read_text(encoding="utf8")) if p.exists() else {};saved[provider]=result;atomic(p,json.dumps(saved,ensure_ascii=False,indent=2))
    return result

def view(root):
    p=Path(root)/'research/access-checks.json';checks=json.loads(p.read_text(encoding="utf8")) if p.exists() else {}
    for item in checks.values():item['recheck_required']=item.get('environment')!=environment_fingerprint() or item.get('network_context',{})!=saved_context(root,item['provider']) or time.time()-__import__('datetime').datetime.fromisoformat(item['checked_at']).timestamp()>86400
    return checks

def _legacy_page(provider):
    if provider not in GUIDES:raise ResearchError('未提供此接入引导')
    g=GUIDES[provider]
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(g['title'])+'</title><style>body{font:16px/1.8 system-ui;background:#f1f5fa;color:#20344e}main{max-width:850px;margin:40px auto;background:white;padding:28px;border-radius:16px}li{margin:14px 0}button,input,select{font:inherit;padding:8px;margin:8px 0}code{overflow-wrap:anywhere}</style><main><a href="/">返回工作台</a><h1>'+escape(g['title'])+'</h1><p>'+escape(g['condition'])+'</p><p>每库每月预算上限 50 元。默认免费/既有机构权益；不自动采购，不在页面收集密码或 key。</p><ol>'+''.join('<li>'+escape(step)+'</li>' for step in g['steps'])+'</ol><a rel="noreferrer" target="_blank" href="'+g['url']+'">打开官方入口</a><hr><label>当前网络条件 <select id="network"><option value="unknown">尚未确认</option><option value="campus">当前在校园网</option><option value="off_campus">当前在校外</option></select></label><button id="save">保存条件</button>'+('' if provider=='campus' else '<p><label>测试查询（Unpaywall 填 DOI） <input id="query" maxlength="1000"></label><button id="verify">验证一次连接</button></p>')+'<p id="message" role="status">仅在你点击验证时发起请求。配置成功不等于授权验证通过。</p></main><script>const provider='+json.dumps(provider)+';async function act(action){const prefix=location.pathname.match(/^\\/p\\/p[a-f0-9]{12}/)?.[0];const msg=document.getElementById("message");if(!prefix){msg.textContent="请从统一项目入口打开引导";return;}try{msg.textContent="正在处理，请稍候…";const t=await(await fetch("/api/session")).json();const data={action,provider};if(action==="context")data.network=document.getElementById("network").value;else data.query=document.getElementById("query").value;const r=await fetch(prefix+"/api/access",{method:"POST",headers:{"Content-Type":"application/json","X-VR-Token":t.token},body:JSON.stringify(data)});const out=await r.json();msg.textContent=out.note||out.error||"已保存";}catch(e){msg.textContent="请求未完成，请核对工作台状态";}}document.getElementById("save").onclick=()=>act("context");if(document.getElementById("verify"))document.getElementById("verify").onclick=()=>act("verify");</script></html>'


def page(provider):
    if provider not in GUIDES:
        raise ResearchError('未提供此接入引导')
    guide = GUIDES[provider]
    initial = json.dumps(network_access.status(), ensure_ascii=False).replace('<', '\\u003c')
    if provider == 'scopus':
        institution = '''
<section class="card"><h2>1 · 机构和网络</h2>
<label>机构 <select id="institution"><option value="casia">中国科学院自动化研究所</option><option value="custom">其他机构</option><option value="none">暂不使用机构权限</option></select></label>
<div id="custom-fields" hidden><label>机构名称 <input id="institution-name" maxlength="160" placeholder="学校或研究机构全称"></label><label>官方校外入口 <input id="portal-url" maxlength="500" placeholder="https://…"></label></div>
<label>接入方式 <select id="method"><option value="auto">自动判断</option><option value="campus_vpn">校内网络或校园 VPN</option><option value="browser_portal">机构网页入口</option><option value="institutional_token">Elsevier Institutional Token</option><option value="public_only">仅使用公开/基础 API 权限</option></select></label>
<label>当前位置 <select id="network"><option value="unknown">尚未确认</option><option value="campus">当前在机构内网</option><option value="off_campus">当前在机构外</option></select></label>
<div class="actions"><button id="save-profile">保存并检查路由</button><a id="institution-portal" target="_blank" rel="noreferrer">打开机构官方入口</a></div><p id="route-note" class="note"></p></section>
<section class="card"><h2>2 · API 凭据</h2><p>API key 只保存在本机。机构账号、密码和验证码请留在官方登录页。</p>
<label>Scopus API key <input id="api-key" type="password" autocomplete="off"></label><button data-secret="scopus" data-input="api-key">保存 API key</button>
<details><summary>机构 VPN 不能承载 API 时</summary><p>Elsevier 可为符合条件的机构签发 Institutional Token。它不是机构网页登录密码，也不能自行生成。</p><label>Institutional Token <input id="insttoken" type="password" autocomplete="off"></label><button data-secret="scopus_insttoken" data-input="insttoken">保存 Institutional Token</button></details></section>'''
    else:
        institution = '<section class="card"><label>当前网络条件 <select id="network"><option value="unknown">尚未确认</option><option value="campus">当前在校园网</option><option value="off_campus">当前在校外</option></select></label><button id="save-context">保存条件</button></section>'
    if provider == 'campus':
        query = ''
    else:
        placeholder = '10.1038/nature12373' if provider == 'unpaywall' else 'machine learning'
        query = f'<section class="card"><h2>{"3" if provider == "scopus" else "2"} · 实际验证</h2><label>测试查询 <input id="query" maxlength="1000" placeholder="{placeholder}"></label><button id="verify">验证一次连接</button><p class="note">只做单条只读查询，不导入文献。网页能登录不等于 API 已获得机构权限。</p></section>'
    steps = ''.join('<li>' + escape(step) + '</li>' for step in guide['steps'])
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(guide['title'])}</title><style>
:root{{font-family:system-ui;color:#20344e;background:#eef4fa}}*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:880px;margin:auto;padding:28px 20px 60px}}header,.card{{background:white;border:1px solid #d6e2ef;border-radius:16px;padding:22px;margin-bottom:14px}}h1{{margin:.2em 0}}h2{{font-size:18px;margin-top:0}}li{{margin:10px 0}}label{{display:block;margin:12px 0}}button,input,select{{font:inherit;padding:9px;border:1px solid #aabbd0;border-radius:8px}}input{{width:min(100%,520px)}}button{{cursor:pointer;background:#165f9f;color:white}}a{{color:#155b9c}}.actions{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:12px}}.note{{background:#eef5fc;border-radius:9px;padding:10px;color:#52687f}}.warn{{background:#fff3d9;padding:10px;border-radius:9px;color:#875000}}details{{margin-top:14px}}#message[data-state="ok"]{{background:#e4f5ef;color:#176c5b}}#message[data-state="bad"]{{background:#ffebe7;color:#9a3425}}
</style><main><header><a href="/">← 返回工作台</a><h1>{escape(guide['title'])}</h1><p>{escape(guide['condition'])}</p><p class="warn">每个数据库每月预算上限 50 元；配置不会自动购买服务。</p><ol>{steps}</ol><a rel="noreferrer" target="_blank" href="{escape(guide['url'])}">打开数据库官方说明 ↗</a></header>{institution}{query}<p id="message" class="note" role="status">尚未发起网络请求。</p></main><script>
const provider={json.dumps(provider)},initial={initial},$=id=>document.getElementById(id);async function post(path,data){{const s=await fetch('/api/session'),token=(await s.json()).token,r=await fetch(path,{{method:'POST',headers:{{'Content-Type':'application/json','X-VR-Token':token}},body:JSON.stringify(data)}}),out=await r.json();if(!r.ok)throw Error(out.error||'操作未完成');return out}}function message(text,ok){{$('message').textContent=text;$('message').dataset.state=ok?'ok':'bad'}}
function profile(){{return initial.routes?.scopus||{{institution_id:'casia',institution_name:'',portal_url:'',method:'auto',declared_network:'unknown'}}}}function fill(){{if(!$('institution'))return;const p=profile();$('institution').value=p.institution_id||'casia';$('method').value=p.method||'auto';$('network').value=p.declared_network||'unknown';$('institution-name').value=p.institution_name||'';$('portal-url').value=p.portal_url||'';toggle();routeText(initial)}}function toggle(){{if(!$('institution'))return;const custom=$('institution').value==='custom';$('custom-fields').hidden=!custom;const known=initial.known_institutions.find(x=>x.id===$('institution').value),url=known?.portal_url||$('portal-url').value;$('institution-portal').href=url||'#';$('institution-portal').hidden=!url}}function routeText(data){{if(!$('route-note'))return;const e=data.environment||initial.environment,d=data.decision||initial.scopus_decision;$('route-note').textContent=(e.tunnel_candidate?'检测到 VPN/隧道接口候选':'未检测到 VPN/隧道接口')+'；'+(e.application_proxy?'存在应用层代理。':'未发现应用层代理。')+(d?' Scopus：'+d.reason:'')}}
if($('institution')){{$('institution').onchange=toggle;$('portal-url').oninput=toggle;$('save-profile').onclick=async()=>{{try{{const out=await post('/api/network-profile',{{action:'configure',provider:'scopus',institution_id:$('institution').value,institution_name:$('institution-name').value,portal_url:$('portal-url').value,method:$('method').value,declared_network:$('network').value}});initial.routes.scopus=out.route;routeText(out);message('网络策略已保存。本次判断仍需用真实 Scopus API 查询确认。',true)}}catch(e){{message(e.message,false)}}}};document.querySelectorAll('[data-secret]').forEach(button=>button.onclick=async()=>{{const input=$(button.dataset.input);try{{await post('/api/configure',{{provider:button.dataset.secret,value:input.value}});input.value='';message('凭据已保存在本机。下一步运行实际验证。',true)}}catch(e){{message(e.message,false)}}}});fill()}}
if($('save-context'))$('save-context').onclick=()=>act('context');async function act(action){{try{{const prefix=location.pathname.match(/^\/p\/p[a-f0-9]{{12}}/)?.[0];if(action==='context'){{if(!prefix)throw Error('请先进入一个研究项目再保存项目网络条件');const out=await post(prefix+'/api/access',{{action,provider,network:$('network').value}});message(out.note||'已保存',true);return}}const text=$('query').value.trim();if(!text)throw Error('请填写测试查询');let out;if(prefix)out=await post(prefix+'/api/access',{{action:'verify',provider,query:text}});else{{const result=await post('/api/preflight',{{providers:[provider]}});out=result.providers[0]}}message(out.note||out.message||'检查完成',out.status==='passed')}}catch(e){{message(e.message,false)}}}}if($('verify'))$('verify').onclick=()=>act('verify');
</script></html>'''
