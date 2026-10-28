"""Dated, sourced field history; distinct from the operator's work log."""
import re
from datetime import date
from .store import ResearchError

EVENT_KINDS = ('origin', 'method', 'dataset', 'result', 'debate', 'replication', 'turning_point')


def validate_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}(-\d{2}(-\d{2})?)?', value):
        raise ResearchError('事件日期使用 YYYY、YYYY-MM 或 YYYY-MM-DD；不可填采集时间代替发表时间')
    try: date.fromisoformat(value + ('-01-01' if len(value) == 4 else '-01' if len(value) == 7 else ''))
    except ValueError: raise ResearchError('事件日期无效')
    return value


def record(store, spec):
    if not isinstance(spec, dict): raise ResearchError('历史记录需为 JSON 对象')
    for key in ('title', 'topic', 'coverage'):
        if not isinstance(spec.get(key), str) or not spec[key].strip(): raise ResearchError(key + ' 必填')
    events = spec.get('events')
    if not isinstance(events, list) or not events or len(events) > 1000: raise ResearchError('需提供 1..1000 个历史事件')
    ids = set(); normalized = []
    for event in events:
        if not isinstance(event, dict): raise ResearchError('事件格式无效')
        for k in ('id', 'title', 'description'):
            if not isinstance(event.get(k), str) or not event[k].strip(): raise ResearchError('事件 ' + k + ' 必填')
        if event['id'] in ids: raise ResearchError('事件编号重复')
        ids.add(event['id']); validate_date(event.get('date'))
        if event.get('kind') not in EVENT_KINDS: raise ResearchError('历史事件类型无效')
        refs = event.get('sources')
        if not isinstance(refs, list) or not refs: raise ResearchError('历史事件必须绑定论文或证据节点')
        for ref in refs:
            n = store.get(ref)
            if n['kind'] not in ('P', 'V', 'R', 'A'): raise ResearchError('历史来源需为 P/V/R/A')
        local = event.get('local_nodes', [])
        if not isinstance(local, list): raise ResearchError('local_nodes 需为列表')
        for ref in local: store.get(ref)
        event_topics=event.get('topics',[])
        if not isinstance(event_topics,list) or not all(isinstance(t,str) and t.strip() for t in event_topics): raise ResearchError('事件 topics 需为非空字符串列表')
        normalized.append({**event, 'sources': refs, 'local_nodes': local, 'topics':event_topics})
    relations = spec.get('relations', [])
    if not isinstance(relations, list): raise ResearchError('relations 需为列表')
    for r in relations:
        if not isinstance(r, dict) or r.get('source') not in ids or r.get('target') not in ids or r['source'] == r['target'] or not isinstance(r.get('reason'), str) or not r['reason'].strip():
            raise ResearchError('历史关系需要有效的不同事件端点和具体依据')
    data = {'source_type': 'research_history', 'topic': spec['topic'], 'coverage': spec['coverage'],
            'events': normalized, 'relations': relations, 'source_revision': store.revision(), 'evidence_verified': False}
    ident = store.add_node('A', spec['title'], data)
    for ref in sorted({r for e in normalized for r in e['sources']}): store.add_edge(ident, 'derived_from', ref)
    return {'id': ident, 'events': len(events), 'note': '保存的是有来源的历史解释；来源存在不代表解释已独立核验。'}


def terms(value):
    return [x.strip().casefold() for x in re.split(r'[\n;,，；]', value or '') if x.strip()]


def matches(needles, text):
    return not needles or any(x in text.casefold() for x in needles)


def topics(store):
    return sorted({n['data']['topic'] for n in store.rows('nodes') if n['data'].get('source_type') == 'research_history'})


def snapshot(store, scope='global', focus=None, topic='', since=None, until=None, subtopic='', aliases=''):
    if scope not in ('global', 'local'): raise ResearchError('scope 为 global/local')
    if focus: raise ResearchError('历史检索已改为主题索引；用 --topic 与 --subtopic，不再用节点编号')
    if scope == 'local' and (not topic.strip() or not subtopic.strip()): raise ResearchError('Local 需要研究主题和子主题')
    if since: validate_date(since)
    if until: validate_date(until)
    if since and until and since > until: raise ResearchError('起始日期不得晚于结束日期')
    needles = terms(topic) + terms(aliases); local = terms(subtopic)
    events = []; relations = []; coverages = []; undated = []; seen_papers = set()
    if topic.strip():
        for node in store.rows('nodes'):
            data = node['data']
            if data.get('source_type') != 'research_history': continue
            parent_match = matches(needles, data.get('topic',''))
            selected_events = []
            for event in data['events']:
                text = ' '.join([event['title'], event['description'], ' '.join(event.get('topics',[]))])
                if not parent_match and not matches(needles,text): continue
                if scope == 'local' and not matches(local,text): continue
                seen_papers.update(event['sources'])
                selected_events.append({**event,'id':node['id']+':'+event['id'],'artifact':node['id'],'curated':True})
            if selected_events:
                events.extend(selected_events)
                coverages.append({'artifact':node['id'],'scope':data['coverage'],'topic':data['topic'],'revision':data.get('source_revision')})
                relations.extend({**r,'source':node['id']+':'+r['source'],'target':node['id']+':'+r['target']} for r in data.get('relations',[]))
        for node in store.rows('nodes'):
            if node['kind'] != 'P' or node['id'] in seen_papers: continue
            data = node['data']; bib = data.get('bibliography', {})
            text = node['title']+' '+str(bib.get('abstract',''))+' '+str(data.get('abstract',''))+' '+' '.join(data.get('topics',[]))
            if not matches(needles,text) or (scope == 'local' and not matches(local,text)): continue
            year = str(bib.get('year') or '')
            if not re.fullmatch(r'\d{4}',year):
                undated.append({'id':node['id'],'title':node['title']}); continue
            events.append({'id':node['id'],'date':year,'title':node['title'],'kind':'publication',
                           'description':'书目发表年份；尚未评估其历史地位。','sources':[node['id']],'curated':False})
    def lower(value): return value + ('-01-01' if len(value)==4 else '-01' if len(value)==7 else '')
    def upper(value): return value + ('-12-31' if len(value)==4 else '-31' if len(value)==7 else '')
    events = sorted([e for e in events if (not since or upper(e['date'])>=lower(since)) and (not until or lower(e['date'])<=upper(until))],key=lambda e:(e['date'],e['id']))
    selected = {e['id'] for e in events}
    return {'scope':scope,'topic':topic,'subtopic':subtopic,'aliases':aliases,'events':events,'undated':undated,
            'topics':topics(store),'relations':[r for r in relations if r['source'] in selected and r['target'] in selected],
            'coverage':coverages,'needs_topic':not topic.strip(),
            'note':'以主题及其别名检索；Global 覆盖该主题，Local 深入指定子主题。节点仅作来源。当前时间轴只含本机资料；联网检索候选不自动变成历史事件。'}


def search_plan(topic, scope='global', subtopic='', aliases='', since=None, until=None):
    if not isinstance(topic,str) or not topic.strip() or len(topic)>300: raise ResearchError('请填写研究主题（最多 300 字）')
    if scope not in ('global','local'): raise ResearchError('scope 为 global/local')
    if scope == 'local' and not subtopic.strip(): raise ResearchError('Local 需要子主题，例如 offline RL 或 credit assignment')
    if len(subtopic)>300 or len(aliases)>1000: raise ResearchError('子主题或别名过长')
    if since: validate_date(since)
    if until: validate_date(until)
    if since and until and since>until: raise ResearchError('起始日期不得晚于结束日期')
    seeds = list(dict.fromkeys([topic.strip()]+[a.strip() for a in re.split(r'[;,，；\n]',aliases) if a.strip()]))[:3]
    base = [s+' '+subtopic.strip() if scope=='local' else s for s in seeds]
    queries = list(dict.fromkeys(base+[base[0]+' survey',base[0]+' historical review']))
    return {'topic':topic.strip(),'scope':scope,'subtopic':subtopic.strip(),'queries':queries,
            'include':'主题发展史：'+topic+'；子题：'+subtopic+'；时间范围：'+str(since or '不限')+' 至 '+str(until or '不限')+'。纳入奠基、竞争方法、负结果和复现；来源不支持日期过滤时需筛选，不声称完整覆盖。'}


def search(store, topic, scope='global', subtopic='', aliases='', since=None, until=None, providers=None, background=False):
    from . import retrieval
    plan = search_plan(topic,scope,subtopic,aliases,since,until)
    result = retrieval.start(store.root,'研究历史 · '+topic,plan['queries'],providers or ['crossref','arxiv'],plan['include'],20)
    worker = retrieval.launch(store.root,seconds=120) if background else None
    return {**result,'plan':plan,'worker':worker,'note':'候选需筛选和阅读后建立有来源事件。查询、限流与待补页保存在检索队列；无运行 worker 时不会自动续查。'}


def packet(store, topic, scope='global', focus=None, subtopic='', aliases=''):
    return {'timeline': snapshot(store, scope, focus, topic, subtopic=subtopic, aliases=aliases), 'task': '梳理研究历史', 'search_plan': search_plan(topic, scope, subtopic, aliases) if topic else None,
            'questions': ['术语与问题如何出现？', '哪些方法/数据/反例改变了路线？', '所谓转折点是否有同期来源及后续影响支持？', '是否遗漏相邻领域、负结果和独立复现？'],
            'workflow': ['用 retrieval 留下多来源、时间范围和引文追踪覆盖', '概要筛选、粗读建立事件、争议和转折点升级精读', '用 history add 保存来源、时间精度、局部关联和关系理由', '将未解决争议交给方向决策与最小实验'],
            'schema': {'title': '方向史', 'topic': topic, 'coverage': '实际来源/查询/时间/失败/未覆盖范围', 'events': [{'id': 'e1', 'date': '2020', 'kind': 'method', 'title': '事件标题', 'description': '意义及证据边界', 'sources': ['P0001'], 'topics': ['子主题名称']}], 'relations': []}}
