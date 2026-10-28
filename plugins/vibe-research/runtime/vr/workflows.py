"""Community-informed workflows adapted to free-first, evidence-grounded research."""
import contextlib
import io
import json
import re
import tempfile
from pathlib import Path
from .store import ResearchError, now, atomic, dumps
from .literature import Router, import_paper
from .community.bib_common import render_entry, parse_bibtex
from .community.validator import CitationValidator


def capabilities():
    meta=json.loads((Path(__file__).parent/'community/provenance.json').read_text(encoding="utf8"))
    base=meta['html_url']+'/tree/'+meta['commit']+'/skills/'
    return [
        {'title':'发现与检索','status':'已接入 · 免费来源','description':'保留查询词、筛选条件、时间、来源与失败记录；按论文标识去重，形成可追溯的检索节点。','note':'通过 vr scout 执行；候选文献需要继续筛选。','links':[{'label':'社区检索方法','url':base+'citation-management'}]},
        {'title':'分层文献阅读','status':'已接入 · 助手执行','description':'根据任务选择概要、粗读或精读；精读检查研究设计、证据强弱和替代解释，保留页码与待审阅状态。','note':'概要与粗读独立保存；精读使用九类证据记录。','links':[{'label':'技能来源','url':base+'scientific-critical-thinking'}]},
        {'title':'研究历史','status':'已接入 · 助手执行','description':'以 global/local 时间轴呈现有来源的研究事件，关联研究图和阅读结果。','note':'global 表示当前资料覆盖的方向历史；local 深入主题下明确的子主题。','links':[]},
        {'title':'方向决策','status':'已接入 · 辅助判断','description':'比较贡献、可行性、可检验性与信息增益；检查硬约束、证据缺口和权重敏感性。','note':'先补证据，再决定是否推荐；保留最小实验、停止与恢复条件。','links':[]},
        {'title':'引用与归档','status':'已接入 · 离线校验','description':'生成 BibTeX 并使用社区校验器检查字段、年份和重复记录；原文文件继续以哈希归档。','note':'离线校验不证明 DOI 在线可达，也不证明引用语义正确。','links':[{'label':'校验器来源','url':base+'citation-management/scripts/validate_citations.py'}]},
    ]


def scout(store, queries, providers, limit, include, offline=False):
    if not 1 <= len(queries) <= 5 or not 1 <= limit <= 20 or not include:
        raise ResearchError('需要 1..5 个查询、1..20 的 limit 和纳入条件')
    runs=[]
    for q in queries:
        for provider in providers:
            try:
                result=Router(store,offline=offline).search(q,provider,limit)
                runs.append(result)
            except ResearchError as e:
                runs.append({'query':q,'provider':provider,'error':str(e),'papers':[],'retrieved_at':now()})
    return {'kind':'search_record','queries':queries,'providers':providers,'include':include,'retrieved_at':now(),
            'runs':runs,'note':'检索命中尚未经过纳入筛选；来源限流和缓存不等于实时检索成功。'}


def archive_scout(store, record):
    ids=[]
    for run in record['runs']:
        for p in run['papers']:
            ident=import_paper(store,p)
            if ident not in ids:ids.append(ident)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'search-record.json';path.write_text(dumps(record),encoding='utf8')
        artifact=store.artifact(path)
    node=store.add_node('A','文献检索 · '+', '.join(record['queries']),{'source_type':'literature_search','paper_ids':ids,'artifacts':[artifact],'scope':record['include'],'search_status':'candidates' if ids else 'no_results'})
    for ident in ids:store.add_edge(node,'derived_from',ident)
    return {'id':node,'papers':ids,'searches':len(record['runs']),'note':record['note']}


def bib_value(value):
    # Metadata remains data; avoid creating TeX commands or terminating a field.
    return str(value or '').replace('\\','').replace('{','(').replace('}',')').replace('\n',' ')


def bibliography(store):
    entries=[]
    for n in store.rows('nodes'):
        if n['kind']!='P':continue
        b=n['data'].get('bibliography',{})
        fields={k:bib_value(b.get(k)) for k in ('title','year','doi','url')}
        fields['title']=bib_value(n['title']);fields['author']=' and '.join(bib_value(x) for x in b.get('authors',[]))
        if b.get('arxiv'):fields.update(eprint=bib_value(b['arxiv']),archivePrefix='arXiv',note='Preprint; published version not verified')
        else:fields['note']='Publication venue metadata requires source verification'
        entries.append(render_entry('misc',n['id'],fields))
    body='\n\n'.join(entries)+'\n';parsed=parse_bibtex(body)
    if len(parsed)!=len(entries):raise ResearchError('书目导出解析数量不一致')
    path=store.root/'research/references.bib';atomic(path,body)
    with contextlib.redirect_stderr(io.StringIO()):
        report=CitationValidator().validate_file(str(path),check_dois=False)
    report['scope']='离线字段/年份/重复项检查；未进行在线 DOI 或引用语义核验。'
    report['source_commit']=json.loads((Path(__file__).parent/'community/provenance.json').read_text(encoding="utf8"))['commit']
    atomic(store.root/'research/BibliographyCheck.json',dumps(report))
    return {'bibtex':str(path),'report':str(store.root/'research/BibliographyCheck.json'),'entries':len(entries),'errors':len(report['errors']),'warnings':len(report['warnings']),'scope':report['scope']}


READING_CHECKS = {
    'method':['可见信息与隐藏信息是否严格区分？','动作编码、候选集合与合法性筛选是否分开说明？'],
    'experiment':['比较是否保持训练预算、可见信息、对手池与规则版本一致？','是否报告多随机种子、不确定性及负面结果？'],
    'limitation':['有哪些替代解释或混杂因素？','哪些结论只在作者设置下成立？'],
    'comparison':['作者明确报告了什么？本项目的推断是什么？','哪些缺口尚未通过跨文献核查？']}
