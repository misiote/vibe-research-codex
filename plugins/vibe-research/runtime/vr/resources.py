"""Explicit links from research nodes to registered sources, files and reading outputs."""
import hashlib
import html
import re
from pathlib import Path
from urllib.parse import urlsplit
from . import reading
from .store import ResearchError

LABELS = {'problem':'研究问题','method':'方法与表征','assumption':'假设与适用条件','equation':'公式与推导',
          'experiment':'实验设计','result':'结果','limitation':'局限与风险','reproduction':'复现要点','comparison':'与本项目比较'}


def safe_url(url):
    if not isinstance(url, str): return None
    try:
        p=urlsplit(url)
        return url if p.scheme in {'http','https'} and p.hostname and not p.username and not p.password else None
    except ValueError:
        return None


def files(store, node):
    rows=list(node['data'].get('artifacts', []))
    if node['kind']=='V' and node['data'].get('paper'):
        p=store.get(node['data']['paper'])
        rows += [d for d in p['data'].get('documents',[]) if d.get('sha256')==node['data'].get('document_sha256')]
    unique={a['sha256']:a for a in rows if re.fullmatch('[a-f0-9]{64}',a.get('sha256',''))}
    return list(unique.values())


def links(store, node):
    out=[{'label':'节点记录','url':'/node/'+node['id'],'kind':'note'}]
    paper=node if node['kind']=='P' else store.get(node['data']['paper']) if node['kind']=='V' and node['data'].get('paper') else None
    if paper:
        b=paper['data'].get('bibliography',{})
        url=safe_url(b.get('url'))
        if url: out.append({'label':'论文来源页','url':url,'kind':'source'})
        pdf=safe_url(b.get('pdf_url'))
        if pdf: out.append({'label':'在线全文','url':pdf,'kind':'source'})
        out.append({'label':'精读结果 · '+paper['title'].split(':')[0], 'url':'/reading/'+paper['id'],'kind':'reading'})
    for a in files(store,node):
        suffix=Path(a['path']).suffix.lower()
        url='/file/'+a['sha256']
        if suffix=='.pdf' and node['kind']=='V': url+='#page='+str(node['data'].get('page',1))
        out.append({'label':('原文 · ' if suffix=='.pdf' else '附件 · ')+a.get('name','归档文件'),'url':url,'kind':'file','sha256':a['sha256']})
    for ident in node['data'].get('paper_ids',[]):
        p=store.get(ident)
        out.append({'label':'检索命中 · '+p['title'],'url':'/node/'+ident,'kind':'paper'})
    return out


def registered_file(store, digest):
    if not re.fullmatch('[a-f0-9]{64}',digest): raise ResearchError('无效附件标识')
    for n in store.rows('nodes'):
        for a in files(store,n):
            if a['sha256']!=digest: continue
            path=(store.root/a['path']).resolve()
            directory=(store.home/'artifacts').resolve()
            if not path.is_relative_to(directory) or not path.is_file(): raise ResearchError('附件路径无效或已丢失')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ResearchError('附件校验失败')
            return path,a.get('name',path.name)
    raise ResearchError('附件未在研究库登记')


def page(title, content):
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+html.escape(title)+'''</title><style>
:root{color-scheme:light dark;--bg:light-dark(#f5f8fc,#101923);--panel:light-dark(#fff,#1a2837);--ink:light-dark(#182d47,#e3edf9);--muted:light-dark(#526780,#a0b6ce);--line:light-dark(#d7e3f1,#354a62);--blue:light-dark(#165fae,#91c2ff);--blue-soft:light-dark(#eaf3ff,#203a57);--green:light-dark(#087f75,#63d7c9);--amber:light-dark(#9b5a08,#ffd08a)}*{box-sizing:border-box}html{scroll-behavior:smooth}body{background:var(--bg);color:var(--ink);font:16px/1.7 system-ui;margin:0;padding:24px}main{max-width:1160px;margin:auto}h1{font-size:1.5rem;line-height:1.35}h2{font-size:1.1rem}h3{font-size:1rem;margin-bottom:4px}a{color:var(--blue);overflow-wrap:anywhere}button{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:7px 11px;cursor:pointer}button:hover{border-color:var(--blue);color:var(--blue)}article{background:var(--panel);padding:20px;border:1px solid var(--line);border-radius:12px;margin:18px 0}p,pre,blockquote{overflow-wrap:anywhere;white-space:pre-wrap}pre{font:14px/1.7 system-ui}blockquote{border-left:3px solid var(--blue);padding-left:16px;margin:12px 0}.meta{color:var(--muted);font-size:14px}.links{display:flex;gap:9px;flex-wrap:wrap}.links a{display:inline-flex;padding:7px 11px;border:1px solid var(--line);border-radius:8px;text-decoration:none}.page-nav{margin-bottom:20px}body.embedded .page-nav{display:none}.reading-layout{display:grid;grid-template-columns:230px minmax(0,1fr);gap:22px;align-items:start}.reading-sidebar{position:sticky;top:18px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}.reading-sidebar strong{display:block;margin-bottom:8px}.reading-index{display:grid;gap:3px}.reading-index a{display:grid;grid-template-columns:10px 1fr auto;gap:8px;align-items:center;padding:7px 8px;border-radius:8px;color:var(--ink);text-decoration:none;font-size:14px}.reading-index a:hover,.reading-index a[aria-current=true]{background:var(--blue-soft);color:var(--blue)}.reading-dot{width:8px;height:8px;border-radius:50%;background:var(--line)}.reading-dot.done{background:var(--green)}.reading-dot.pending{background:var(--amber)}.reading-count{color:var(--muted);font-size:12px}.reading-tools{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}.reading-tools button{font-size:13px;padding:5px 8px}.reading-main{min-width:0}.reading-overview{margin-top:0}.reading-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:14px 0}.reading-metric{padding:11px;border-radius:9px;background:var(--bg)}.reading-metric strong{display:block;font-size:18px}.reading-metric span{font-size:12px;color:var(--muted)}.reading-section{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin:10px 0;scroll-margin-top:18px;overflow:hidden}.reading-section>summary,.evidence-entry>summary{list-style:none;cursor:pointer}.reading-section>summary::-webkit-details-marker,.evidence-entry>summary::-webkit-details-marker{display:none}.reading-section>summary{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;font-weight:650}.reading-section>summary::after,.evidence-entry>summary::after{content:'⌄';color:var(--muted);transition:transform .15s}.reading-section[open]>summary::after,.evidence-entry[open]>summary::after{transform:rotate(180deg)}.section-label{min-width:0}.section-label small{display:block;color:var(--muted);font-weight:400}.section-body{padding:2px 16px 16px;border-top:1px solid var(--line)}.section-empty{color:var(--muted);margin:14px 0}.evidence-entry{border:1px solid var(--line);border-radius:10px;margin-top:12px;overflow:hidden}.evidence-entry>summary{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;padding:11px 12px}.evidence-page{color:var(--blue);font-weight:650}.evidence-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.evidence-status{font-size:12px;color:var(--muted)}.evidence-content{padding:0 14px 14px;border-top:1px solid var(--line)}.evidence-content h3{margin-top:14px}.status-pill{display:inline-flex;padding:2px 7px;border-radius:999px;background:var(--blue-soft);color:var(--blue);font-size:12px;font-weight:500}.status-pill.done{color:var(--green)}.status-pill.pending{color:var(--amber)}@media(max-width:760px){body{padding:14px}.reading-layout{grid-template-columns:1fr}.reading-sidebar{position:static}.reading-index{display:flex;overflow:auto;padding-bottom:4px}.reading-index a{flex:0 0 auto;grid-template-columns:8px auto auto;border:1px solid var(--line)}.reading-metrics{grid-template-columns:1fr}.evidence-entry>summary{grid-template-columns:auto minmax(0,1fr) auto}}</style><main><nav class="page-nav"><a href="/">← 研究工作台</a></nav><h1>'''+html.escape(title)+'</h1>'+content+'''</main><script>
if(window.self!==window.top)document.body.classList.add('embedded');
const readingSections=[...document.querySelectorAll('.reading-section')],readingEntries=[...document.querySelectorAll('.evidence-entry')];
function openReadingTarget(){if(!location.hash)return;const target=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(target?.classList.contains('reading-section')){target.open=true;target.querySelector('.evidence-entry')?.setAttribute('open','')}}
document.querySelector('[data-reading-action="expand"]')?.addEventListener('click',()=>[...readingSections,...readingEntries].forEach(x=>x.open=true));
document.querySelector('[data-reading-action="collapse"]')?.addEventListener('click',()=>[...readingSections,...readingEntries].forEach(x=>x.open=false));
document.querySelectorAll('.reading-index a').forEach(a=>a.addEventListener('click',()=>{document.querySelectorAll('.reading-index a').forEach(x=>x.removeAttribute('aria-current'));a.setAttribute('aria-current','true');setTimeout(openReadingTarget)}));
addEventListener('hashchange',openReadingTarget);openReadingTarget();
</script></html>'''


def link_html(items):
    def anchor(item):
        external=item['url'].startswith(('http://','https://'))
        attrs=' target="_blank" rel="noopener noreferrer"' if external else ''
        return '<a href="'+html.escape(item['url'],quote=True)+'"'+attrs+'>'+html.escape(item['label'])+'</a>'
    return '<div class="links">'+''.join(anchor(x) for x in items)+'</div>'


def reading_page(store, ident):
    p=store.get(ident)
    if p['kind']!='P': raise ResearchError('需要论文节点')
    notes=[n for n in store.rows('nodes') if n['kind']=='V' and n['data'].get('paper')==ident]
    current=p['data'].get('active_document')
    accepted={n['data']['section'] for n in notes if n['data'].get('review_status')=='accepted' and n['data'].get('document_sha256')==current}
    quality={n['data'].get('quality_dimension') for n in notes if n['data'].get('review_status')=='accepted' and n['data'].get('document_sha256')==current and n['data'].get('quality_dimension') and n['data'].get('quality_verdict')}
    screening=p['data'].get('screening',{}); verdict={'valuable':'有价值','uncertain':'信息不足','exclude':'不纳入'}.get(screening.get('verdict'),'尚未初筛')
    grouped={sec:[n for n in notes if n['data'].get('section')==sec] for sec in LABELS}
    index=[];sections=[]
    for sec,title in LABELS.items():
        rows=grouped[sec];reviewed=sum(n['data'].get('review_status')=='accepted' and n['data'].get('document_sha256')==current for n in rows)
        if not rows: label='未记录';dot=''
        elif reviewed==len(rows): label='已审阅';dot='done'
        elif reviewed: label=str(reviewed)+'/'+str(len(rows));dot='pending'
        else: label='待审阅';dot='pending'
        index.append('<a href="#section-'+sec+'"><span class="reading-dot '+dot+'"></span><span>'+title+'</span><span class="reading-count">'+label+'</span></a>')
        section='<details class="reading-section" id="section-'+sec+'"><summary><span class="section-label">'+title+'<small>'+str(len(rows))+' 条记录</small></span><span class="status-pill '+dot+'">'+label+'</span></summary><div class="section-body">'
        if not rows: section+='<p class="section-empty">尚未留下这一部分的精读记录。</p>'
        for n in rows:
            d=n['data'];status={'pending':'待审阅','accepted':'已接受','rejected':'已驳回'}.get(d.get('review_status'),'未审阅')
            preview=d.get('author_claim') or d.get('interpretation') or d.get('quote') or '查看精读记录'
            preview=' '.join(str(preview).split())
            if len(preview)>70:preview=preview[:69]+'…'
            old=d.get('document_sha256')!=current
            section+='<details class="evidence-entry"><summary><span class="evidence-page">第 '+str(d.get('page','?'))+' 页</span><span class="evidence-title">'+html.escape(preview)+'</span><span class="evidence-status">'+status+(' · 旧版本' if old else '')+'</span></summary><div class="evidence-content"><h3>原文</h3><blockquote>'+html.escape(d.get('quote',''))+'</blockquote>'
            if d.get('author_claim'): section+='<h3>作者主张</h3><p>'+html.escape(d['author_claim'])+'</p>'
            section+='<h3>解释</h3><p>'+html.escape(d.get('interpretation',''))+'</p>'
            if d.get('quality_judgment'): section+='<h3>质量判断</h3><p>'+html.escape(d['quality_judgment'])+'</p>'
            if d.get('impact'): section+='<h3>对结论的影响</h3><p>'+html.escape(d['impact'])+'</p>'
            if d.get('scope'): section+='<h3>适用范围</h3><p>'+html.escape(d['scope'])+'</p>'
            if d.get('unresolved'): section+='<h3>未决问题</h3><p>'+html.escape(d['unresolved'])+'</p>'
            if d.get('missing_information'): section+='<h3>论文未报告</h3><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in d['missing_information'])+'</ul>'
            if d.get('details'): section+='<h3>研究细节</h3><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in d['details'])+'</ul>'
            section+=link_html([l for l in links(store,n) if l['kind'] in {'file','note'}])+'</div></details>'
        sections.append(section+'</div></details>')
    document_state='已获取全文' if current else '等待全文'
    overview='<article class="reading-overview" id="reading-overview"><h2>判断</h2><p><strong>'+html.escape(verdict)+'</strong> · '+html.escape(screening.get('reason','尚未留下初筛依据。'))+'</p><div class="reading-metrics"><div class="reading-metric"><strong>'+str(len(accepted))+'/9</strong><span>阅读部分已审阅</span></div><div class="reading-metric"><strong>'+str(len(quality))+'/'+str(len(reading.QUALITY_DIMENSIONS))+'</strong><span>质量维度已判断</span></div><div class="reading-metric"><strong>'+document_state+'</strong><span>原文状态</span></div></div><p class="meta">原文匹配只证明引文位置存在；解释和质量判断仍需审阅。</p>'+link_html([l for l in links(store,p) if l['kind'] in {'source','file'}])+'</article>'
    if not current:overview+='<article class="notice">尚未获取全文；有价值的文献会保留在全文获取队列，不能据摘要声称完成精读。</article>'
    sidebar='<aside class="reading-sidebar"><strong>精读目录</strong><div class="reading-index"><a href="#reading-overview" aria-current="true"><span class="reading-dot done"></span><span>判断与进度</span><span class="reading-count">概览</span></a>'+''.join(index)+'</div><div class="reading-tools"><button data-reading-action="expand">展开全部</button><button data-reading-action="collapse">收起全部</button></div></aside>'
    return page('精读结果 · '+p['title'],'<div class="reading-layout">'+sidebar+'<div class="reading-main">'+overview+''.join(sections)+'</div></div>')


def node_page(store, ident):
    n=store.get(ident)
    body='<p class="meta">'+html.escape({'draft':'待开展','active':'推进中','running':'运行中','completed':'已完成','supported':'有支持证据','rejected':'已否定','pruned':'已剪枝','failed':'失败'}.get(n['status'],n['status']))+'</p>'+link_html([l for l in links(store,n) if l['kind']!='note'])
    for key,title in [('interpretation','解释'),('quote','原文'),('scope','范围'),('status_note','状态说明')]:
        if n['data'].get(key):body+='<article><h2>'+title+'</h2><p>'+html.escape(str(n['data'][key]))+'</p></article>'
    body+='<article><h2>关联路线</h2><a href="/graph?node='+ident+'">在关系图中定位</a></article>'
    return page(n['title'],body)


SKILLS = {'citation-management':'文献检索与引用管理','scientific-critical-thinking':'批判性精读',
          'research-reading-expert':'科研精读专家','research-landscape-expert':'研究关系专家','research-writing-editor':'科研写作编辑',
          'vibe-research-continuity':'研究工作接续','vibe-research-team':'研究专家协作'}

def skill_catalog():
    return [{'name':name,'title':title,'available':(Path(__file__).resolve().parents[1]/'skills'/name/'SKILL.md').is_file(), 'url':'/settings/skills/'+name} for name,title in SKILLS.items()]

def skill_page(name):
    if name not in SKILLS: raise ResearchError('技能不存在')
    path=Path(__file__).resolve().parents[1]/'skills'/name/'SKILL.md'
    if not path.is_file(): raise ResearchError('本安装未包含技能说明')
    return page(SKILLS[name],'<p class="meta">当前分发包中的技能说明。用于辅助助手工作；不代表研究结论已验证。</p><article><pre>'+html.escape(path.read_text())+'</pre></article>')
