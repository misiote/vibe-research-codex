"""On-demand institutional onboarding; no browser cookie or password reuse."""
import json,hashlib,os,platform,time,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from html import escape
from .store import ResearchError,atomic,now
from . import connections,request_gate

GUIDES={
 'wos':{'title':'Web of Science Starter','url':'https://developer.clarivate.com/apis/wos-starter','condition':'先申请官方免费试用或学校已授权套餐；不同套餐的引文计数权限不同。','steps':['在官方开发者门户注册应用并申请 Starter key。','确认免费试用或既有机构权益；不自动购买套餐。','回到工作台设置页，在 Web of Science 卡片中保存 key。','用一个明确主题做真实查询；通过后可进入分页检索，但不代表全文权限。']},
 'scopus':{'title':'Scopus','url':'https://dev.elsevier.com/','condition':'需要本人 API key；高级字段还取决于机构订阅与请求机器的网络出口。','steps':['由学校数据库导航确认订阅和允许的 API 用途。','在 Elsevier 官方门户申请本人 key，回到工作台设置页保存。','当前在校内时优先检查本机校园出口；浏览器 SSO 不会自动授权 Python 请求。','离校时按学校规定使用校外访问方式；不关闭 TLS 校验、不自动修改全局代理。','若仍为 401/403，联系馆员核验 entitlement；保留查询，通过公开来源继续。']},
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
    # Used only to invalidate checks; no IP/SSID or raw proxy address is saved.
    return hashlib.sha256((platform.node()+str(sorted((k,v) for k,v in os.environ.items() if k.lower() in ('http_proxy','https_proxy','all_proxy','no_proxy')))).encode()).hexdigest()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ResearchError('来源发生跳转；未向新地址转发凭据，请核对官方 API 地址')

def verify(root,provider,query):
    if provider not in ('wos','scopus','unpaywall') or not query.strip() or len(query)>1000:raise ResearchError('需要有效来源与单条测试查询')
    token,auth_source=connections.credential(provider)
    result={'provider':provider,'checked_at':now(),'environment':environment_fingerprint(),'network_context':saved_context(root,provider),'auth_source':auth_source,'status':'needs_auth','note':'尚未配置凭据，请在本机终端引导中完成；不要粘贴到聊天。'}
    if token:
        headers={'Accept':'application/json','User-Agent':'VibeResearch/0.2'}
        if provider=='scopus':url='https://api.elsevier.com/content/search/scopus?'+urllib.parse.urlencode({'query':query,'count':1});headers['X-ELS-APIKey']=token
        elif provider=='wos':url='https://api.clarivate.com/apis/wos-starter/v1/documents?'+urllib.parse.urlencode({'q':query,'limit':1,'page':1});headers['X-ApiKey']=token
        else:
            if not query.startswith('10.') or '/' not in query:raise ResearchError('Unpaywall 需要 DOI，不能用关键词代替')
            url='https://api.unpaywall.org/v2/'+urllib.parse.quote(query,safe='/')+'?'+urllib.parse.urlencode({'email':token})
        try:
            request_gate.admit(provider)
            with urllib.request.build_opener(NoRedirect).open(urllib.request.Request(url,headers=headers),timeout=15) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise ResearchError('响应超出单条验收大小')
                data=json.loads(raw)
                if not isinstance(data,dict):raise ResearchError("响应不是有效的数据对象")
            if provider=='scopus':valid=isinstance(data.get('search-results'),dict) and 'opensearch:totalResults' in data['search-results']
            elif provider=='wos':valid=isinstance(data.get('hits'),list) and isinstance(data.get('metadata'),dict)
            else:valid=isinstance(data.get('doi'),str) and isinstance(data.get('is_oa'),bool)
            if not valid:raise ResearchError('响应缺少预期数据字段')
            result.update(status='passed',note='单次元数据查询通过；全文和完整分页权限尚未验收。' if provider!='unpaywall' else ('DOI 查询通过；返回开放位置。' if data['is_oa'] else 'DOI 查询通过；此记录未提供开放全文。'))
        except request_gate.Deferred as exc:result.update(status='waiting',next_retry=exc.until,note='共享冷却中；保留来源与原查询，不代表检索完成。')
        except urllib.error.HTTPError as exc:
            result.update(status='waiting' if exc.code==429 or exc.code>=500 else 'blocked',http=exc.code,note='需要核验权限或等待服务恢复；原始响应未写入记录。')
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

def page(provider):
    if provider not in GUIDES:raise ResearchError('未提供此接入引导')
    g=GUIDES[provider]
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(g['title'])+'</title><style>body{font:16px/1.8 system-ui;background:#f1f5fa;color:#20344e}main{max-width:850px;margin:40px auto;background:white;padding:28px;border-radius:16px}li{margin:14px 0}button,input,select{font:inherit;padding:8px;margin:8px 0}code{overflow-wrap:anywhere}</style><main><a href="/">返回工作台</a><h1>'+escape(g['title'])+'</h1><p>'+escape(g['condition'])+'</p><p>每库每月预算上限 50 元。默认免费/既有机构权益；不自动采购，不在页面收集密码或 key。</p><ol>'+''.join('<li>'+escape(step)+'</li>' for step in g['steps'])+'</ol><a rel="noreferrer" target="_blank" href="'+g['url']+'">打开官方入口</a><hr><label>当前网络条件 <select id="network"><option value="unknown">尚未确认</option><option value="campus">当前在校园网</option><option value="off_campus">当前在校外</option></select></label><button id="save">保存条件</button>'+('' if provider=='campus' else '<p><label>测试查询（Unpaywall 填 DOI） <input id="query" maxlength="1000"></label><button id="verify">验证一次连接</button></p>')+'<p id="message" role="status">仅在你点击验证时发起请求。配置成功不等于授权验证通过。</p></main><script>const provider='+json.dumps(provider)+';async function act(action){const prefix=location.pathname.match(/^\\/p\\/p[a-f0-9]{12}/)?.[0];const msg=document.getElementById("message");if(!prefix){msg.textContent="请从统一项目入口打开引导";return;}try{msg.textContent="正在处理，请稍候…";const t=await(await fetch("/api/session")).json();const data={action,provider};if(action==="context")data.network=document.getElementById("network").value;else data.query=document.getElementById("query").value;const r=await fetch(prefix+"/api/access",{method:"POST",headers:{"Content-Type":"application/json","X-VR-Token":t.token},body:JSON.stringify(data)});const out=await r.json();msg.textContent=out.note||out.error||"已保存";}catch(e){msg.textContent="请求未完成，请核对工作台状态";}}document.getElementById("save").onclick=()=>act("context");if(document.getElementById("verify"))document.getElementById("verify").onclick=()=>act("verify");</script></html>'
