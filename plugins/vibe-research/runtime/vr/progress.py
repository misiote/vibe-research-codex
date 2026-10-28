"""Evidence-based progress; no fabricated overall completion percentage."""
from collections import Counter
from .store import now, atomic, dumps
from .reading import report, queue_action, processing_stage


def snapshot(store):
    nodes = store.rows('nodes')
    edges = store.rows('edges')
    by_id = {n['id']: n for n in nodes}
    kinds = Counter(n['kind'] for n in nodes)
    papers, evidence, hypotheses = [], [], []
    for n in nodes:
        if n['kind'] == 'P':
            d = n['data']
            fulltext = bool(d.get('documents'))
            sections, missing = [], []
            if fulltext:
                reading = report(store, n['id'])
                sections, missing = reading['accepted_sections'], reading['missing_sections']
            papers.append({'id': n['id'], 'title': n['title'], 'fulltext': fulltext,
                           'complete': fulltext and not missing and d.get('reading_status') == 'complete',
                           'accepted_sections': sections, 'missing_sections': missing,
                           'status': d.get('reading_status', 'metadata_only'), 'reading_depth': d.get('reading_depth', 'deep'), 'reading_notes': d.get('reading_notes', {}),
                           'screening_verdict': d.get('screening', {}).get('verdict'),
                           'screening_reason': d.get('screening', {}).get('reason'),
                           'publication_date':str(d.get('bibliography',{}).get('published_date') or d.get('bibliography',{}).get('year') or ''),
                           'processing_rank':processing_stage(n,fulltext and not missing and d.get('reading_status')=='complete'),
                           'queue_action': queue_action(n)})
        if n['kind'] == 'V':
            d = n['data']
            evidence.append({'id': n['id'], 'title': n['title'], 'paper': d.get('paper'),
                             'page': d.get('page'), 'section': d.get('section'),
                             'review_status': d.get('review_status', 'pending'),
                             'quote_verified': d.get('quote_verified', False)})
        if n['kind'] == 'H':
            xs = {e['target'] for e in edges if e['source'] == n['id'] and e['relation'] == 'tested_by'}
            rs = {e['target'] for e in edges if e['source'] in xs and e['relation'] == 'produces' and by_id[e['target']]['kind'] == 'R'}
            hypotheses.append({'id': n['id'], 'title': n['title'], 'status': n['status'],
                               'planned_experiments': sorted(xs), 'archived_results': sorted(rs)})
    tasks = [{'id': n['id'], 'title': n['title'], 'status': n['status']} for n in nodes if n['kind'] == 'Q']
    branches = []
    members = store.rows('members')
    for b in store.rows('branches'):
        ids = [m['node'] for m in members if m['branch'] == b['id']]
        hs = [h for h in hypotheses if h['id'] in ids]
        branches.append({'id': b['id'], 'title': b['title'], 'status': b['status'], 'members': ids,
                         'hypotheses': hs, 'results': sorted({r for h in hs for r in h['archived_results']})})
    return {'generated_at': now(), 'revision': store.revision(), 'project': str(store.root),
            'question': store.db.execute("SELECT value FROM meta WHERE key='question'").fetchone()[0],
            'counts': {'papers': len(papers), 'fulltexts': sum(p['fulltext'] for p in papers),
                       'reading_complete': sum(p['complete'] for p in papers),
                       'reading_queued': sum(bool(p['queue_action']) for p in papers),
                       'evidence_pending': sum(v['review_status'] == 'pending' for v in evidence),
                       'evidence_accepted': sum(v['review_status'] == 'accepted' for v in evidence),
                       'hypotheses': len(hypotheses), 'experiments': kinds['X'], 'results': kinds['R'],
                       'running_experiments': sum(n['kind'] == 'X' and n['status'] == 'running' for n in nodes),
                       'tasks_open': sum(t['status'] != 'completed' for t in tasks),
                       'tasks_completed': sum(t['status'] == 'completed' for t in tasks)},
            'papers': papers, 'evidence': evidence, 'hypotheses': hypotheses, 'tasks': tasks, 'branches': branches,
            'recent_events': [{k: e[k] for k in ('seq', 'time', 'actor', 'action')} for e in store.rows('events')[-8:]],
            'note': '计数来自当前研究库。假设建立/实验建档不代表完成验证；结果归档也不自动证明科学结论。'}


def publish(store):
    result = snapshot(store)
    c = result['counts']
    lines = ['# 研究进展', '', result['question'], '', f"更新时间：{result['generated_at']} · Revision {result['revision']}", '',
             '[[Home|项目首页]] · [[research.canvas|研究有向图]] · [[Integrations|工具接入检查]]', '',
             '| 阶段 | 已记录状态 |', '|---|---|',
             f"| 文献 | {c['papers']} 篇；{c['fulltexts']} 篇有全文 |",
             f"| 精读 | {c['reading_queued']} 篇已触发待处理；{c['reading_complete']} 篇完成；{c['evidence_pending']} 条证据待审阅 |",
             f"| 假设 | {c['hypotheses']} 条 |",
             f"| 实验 | {c['experiments']} 个建档；{c['running_experiments']} 个运行中；{c['results']} 份结果归档 |",
             f"| 待办 | {c['tasks_open']} 项未完成；{c['tasks_completed']} 项完成 |", '',
             '不计算总体百分比：建立研究节点不是完成研究。', '', '## 当前路线', '']
    for b in result['branches']:
        lines += [f"- {b['id']} · {b['title']} · {b['status']} · {len(b['results'])} 份结果"]
    lines += ['', '## 待办', '']
    for t in result['tasks']:
        lines.append(f"- [{'x' if t['status'] == 'completed' else ' '}] [[Notes/{t['id']}|{t['id']}]] {t['title']} · {t['status']}")
    lines += ['', '## 精读', '']
    for p in result['papers']:
        lines.append(f"- [[Papers/{p['id']}|{p['id']}]] {p['title']} · 已审阅章节 {len(p['accepted_sections'])}/9 · {p['status']}")
    atomic(store.root / 'research/Progress.md', '\n'.join(lines) + '\n')
    atomic(store.root / 'research/progress.json', dumps(result))
    return result
