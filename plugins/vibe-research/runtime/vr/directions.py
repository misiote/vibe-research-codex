"""Evidence-aware direction comparison. Scores organize judgments; they do not create evidence."""
import math
from .store import ResearchError

CRITERIA = {'importance': '问题价值', 'novelty': '增量与差异', 'feasibility': '资源可行性', 'testability': '可证伪性', 'information_gain': '预期信息增益'}
DEFAULT_WEIGHTS = {'importance': .25, 'novelty': .2, 'feasibility': .2, 'testability': .2, 'information_gain': .15}


def packet(store):
    nodes = store.rows('nodes')
    return {'candidates': [n for n in nodes if n['kind'] in ('G', 'I', 'H')],
            'counterevidence': [n for n in nodes if n['kind'] in ('F', 'R') or n['data'].get('evidence_role') == 'contradicts'],
            'criteria': CRITERIA, 'default_weights': DEFAULT_WEIGHTS,
            'instructions': '提出互有区别的路线及维持现状选项。先查方向史和检索覆盖，找最接近工作、反例和失败。明确贡献、可证伪假设、最小实验、成功阈值、停止与复活条件。逐维给 0..5 区间、具体理由和证据编号；未知保持 [0,5]。资源硬约束单独门控，不以总分补偿。评价不修改假设状态，正式行动另用 decide。',
            'schema': {'question': '要做哪条路线', 'constraints': '时间/预算/数据/算力/技能', 'coverage': '已查来源及未覆盖部分', 'weights': DEFAULT_WEIGHTS,
                       'candidates': [{'id': 'route-a', 'title': '候选路线', 'hypothesis': '可证伪主张', 'contribution': '相对最接近工作的增量',
                                       'nearest_work': ['P0001'], 'hard_constraints': [{'name': '数据可得性', 'status': 'unknown', 'reason': '待验证'}],
                                       'criteria': {k: {'range': [0, 5], 'reason': '待证据判断', 'evidence': []} for k in CRITERIA},
                                       'counterevidence': [], 'risks': '主要竞争解释与依赖', 'minimum_test': '最小区分实验、基线与预算',
                                       'success_threshold': '事先固定可判定阈值', 'stop_rule': '何时停止', 'revival_condition': '何时重启'}]}}


def evaluate(store, spec):
    if not isinstance(spec, dict): raise ResearchError('决策比较需为对象')
    for key in ('question', 'constraints', 'coverage'):
        if not isinstance(spec.get(key), str) or not spec[key].strip(): raise ResearchError(key + ' 必填')
    weights = spec.get('weights', DEFAULT_WEIGHTS)
    if not isinstance(weights, dict) or set(weights) != set(CRITERIA) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in weights.values()):
        raise ResearchError('所有维度需有正的有限权重')
    total = sum(weights.values()); weights = {k: v / total for k, v in weights.items()}
    candidates = spec.get('candidates')
    if not isinstance(candidates, list) or not 2 <= len(candidates) <= 20: raise ResearchError('比较需提供 2..20 条路线（可包括维持现状）')
    ids = set(); rows = []
    def refs(values):
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values): raise ResearchError('证据引用需为编号列表')
        return [store.get(v) for v in values]
    for c in candidates:
        if not isinstance(c, dict): raise ResearchError('路线格式无效')
        for k in ('id', 'title', 'hypothesis', 'contribution', 'risks', 'minimum_test', 'success_threshold', 'stop_rule', 'revival_condition'):
            if not isinstance(c.get(k), str) or not c[k].strip(): raise ResearchError('路线 ' + k + ' 必填')
        if c['id'] in ids: raise ResearchError('路线编号重复')
        ids.add(c['id'])
        refs(c.get('nearest_work', [])); refs(c.get('counterevidence', []))
        gates = c.get('hard_constraints')
        if not isinstance(gates, list) or not gates: raise ResearchError('需列出资源硬约束及其核验状态')
        for g in gates:
            if not isinstance(g, dict) or g.get('status') not in ('pass', 'fail', 'unknown') or not isinstance(g.get('name'), str) or not g['name'].strip() or not isinstance(g.get('reason'), str) or not g['reason'].strip():
                raise ResearchError('硬约束需 name/status(pass|fail|unknown)/reason')
        criteria = c.get('criteria')
        if not isinstance(criteria, dict) or set(criteria) != set(CRITERIA): raise ResearchError('需评价全部五个维度')
        intervals = {}; gaps = []; unreviewed = set()
        for k, a in criteria.items():
            if not isinstance(a, dict) or not isinstance(a.get('reason'), str) or not a['reason'].strip(): raise ResearchError('每维需具体理由')
            interval = a.get('range')
            if not isinstance(interval, list) or len(interval) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in interval) or not 0 <= interval[0] <= interval[1] <= 5:
                raise ResearchError('评分区间必须在 0..5 且下界不大于上界')
            evidence = refs(a.get('evidence', []))
            if not evidence:
                intervals[k] = [0, 5]; gaps.append(k)
            else:
                intervals[k] = interval
                for n in evidence:
                    if not (n['kind'] == 'V' and n['data'].get('review_status') == 'accepted'):
                        unreviewed.add(n['id'])
        lo = sum(weights[k] * intervals[k][0] for k in CRITERIA); hi = sum(weights[k] * intervals[k][1] for k in CRITERIA)
        gate = 'blocked' if any(g['status'] == 'fail' for g in gates) else 'conditional' if any(g['status'] == 'unknown' for g in gates) else 'eligible'
        if gaps or unreviewed:
            if gate == 'eligible': gate = 'conditional'
        rows.append({**c, 'intervals': intervals, 'score_range': [round(lo, 3), round(hi, 3)], 'midpoint': (lo + hi) / 2,
                     'gate': gate, 'next_checks': sorted([{'criterion': k, 'priority': round(weights[k]*(intervals[k][1]-intervals[k][0]),3), 'reason': criteria[k]['reason']} for k in CRITERIA],key=lambda x:-x['priority']), 'evidence_gaps': gaps, 'unreviewed_sources': sorted(unreviewed)})
    feasible = [r for r in rows if r['gate'] != 'blocked']
    scenarios = [weights]
    for k in CRITERIA:
        for scale in (.8, 1.2):
            w = {j: v * (scale if j == k else 1) for j, v in weights.items()}; t = sum(w.values()); scenarios.append({j: v/t for j, v in w.items()})
    winners = set()
    for w in scenarios:
        if not feasible: break
        scores = {r['id']: sum(w[k] * sum(r['intervals'][k])/2 for k in CRITERIA) for r in feasible}
        best = max(scores.values()); winners.update(k for k, v in scores.items() if abs(v-best) < 1e-9)
    robust = [r['id'] for r in feasible if r['gate'] == 'eligible' and all(r['id'] == q['id'] or r['score_range'][0] > q['score_range'][1] for q in feasible)]
    for r in rows:
        r['pareto_dominated'] = any(q['id'] != r['id'] and all(q['intervals'][k][0] >= r['intervals'][k][1] for k in CRITERIA) and any(q['intervals'][k][0] > r['intervals'][k][1] for k in CRITERIA) for q in feasible)
    return {'question': spec['question'], 'constraints': spec['constraints'], 'coverage': spec['coverage'], 'weights': weights,
            'candidates': sorted(rows, key=lambda r: (r['gate'] == 'blocked', -r['midpoint'])), 'recommendation': robust[0] if len(robust) == 1 else None,
            'sensitivity': {'weight_change': '逐维 ±20%', 'possible_midpoint_winners': sorted(winners), 'stable': len(winners) == 1},
            'next_step': '先核验硬约束与宽区间中最能改变选择的信息，再执行最小实验。',
            'note': '区间分数来自显式人工/助手判断，非统计置信区间。无证据维度强制 [0,5]；未审阅来源只能给条件建议。敏感性分析基于区间中点，不表示稳健性证明。不会自动支持、否定或剪枝假设。'}


def save(store, spec):
    result = evaluate(store, spec)
    ident = store.add_node('A', '方向比较 · ' + spec['question'], {'source_type': 'direction_assessment', 'assessment': result, 'spec': spec, 'source_revision': store.revision()})
    sources = {e for c in spec['candidates'] for a in c['criteria'].values() for e in a.get('evidence', [])}
    for ref in sorted(sources): store.add_edge(ident, 'derived_from', ref)
    return {'id': ident, **result}
