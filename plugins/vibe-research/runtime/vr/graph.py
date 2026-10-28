"""Portable read-only force graph. The canonical graph is changed only via CLI."""
import json
from pathlib import Path
from .store import atomic, dumps, now
from .resources import links


def data(store):
    nodes = []
    for n in store.rows('nodes'):
        d = n['data']
        nodes.append({k: n[k] for k in ('id', 'kind', 'title', 'status')} | {
            'reading_status': d.get('reading_status'), 'review_status': d.get('review_status'),
            'screening_verdict': d.get('screening', {}).get('verdict'),
            'hidden_by_default':n['kind']=='P' and (d.get('screening',{}).get('verdict')=='exclude' or d.get('reading_status')=='screened_out'),
            'screening_reason': d.get('screening', {}).get('reason'),
            'page': d.get('page'), 'quote': d.get('quote'), 'interpretation': d.get('interpretation'),
            'source_url': d.get('bibliography', {}).get('url'),
            'resources': links(store, n), 'artifacts': d.get('artifacts', []), 'notes': {k: d[k] for k in ('scope', 'status_note', 'revival_condition', 'do_not_repeat') if k in d}})
    return {'revision': store.revision(), 'generated_at': now(), 'nodes': nodes,
            'edges': store.rows('edges'), 'branches': store.rows('branches'), 'members': store.rows('members')}


def fragment(store):
    template = (Path(__file__).parent / 'templates/research_graph.html').read_text(encoding='utf8')
    template = template.replace('__GRAPH_PHYSICS__', (Path(__file__).parent / 'templates/graph_physics.js').read_text(encoding='utf8'))
    template=template.replace('__GRAPH_STAGE__',(Path(__file__).parent/'templates/graph_stage.js').read_text(encoding='utf8'))
    return template.replace('__GRAPH_DATA__', json.dumps(data(store), ensure_ascii=False).replace('<', '\\u003c'))


BASE = '''
:root{color-scheme:light dark;--background:light-dark(#ffffff,#191a1c);--foreground:light-dark(#25282c,#e9edf2);--muted-foreground:light-dark(#666d76,#a1a8b2);--border:light-dark(#dadde2,#3b4048);--card:light-dark(#f5f6f8,#22252a);--card-foreground:var(--foreground);--primary:var(--foreground);--primary-foreground:var(--background);--viz-series-1:light-dark(#4281a4,#78bde1);--viz-series-2:light-dark(#98813f,#d4bb73);--viz-series-3:light-dark(#8170ad,#b7a4dc);--viz-series-4:light-dark(#448c75,#79c3a8);--viz-series-5:light-dark(#b5774b,#dfab80);--viz-series-6:light-dark(#9e657e,#d996b4)}
body{margin:0;padding:24px;background:var(--background);color:var(--foreground);font:14px/1.5 system-ui,sans-serif}main{max-width:1200px;margin:auto}h2,h3,strong{font-weight:500}h2{font-size:20px}.text-small{font-size:12px}.text-muted{color:var(--muted-foreground)}.viz-row,.viz-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.card{background:var(--card);color:var(--card-foreground);border-radius:12px;padding:16px}.btn,.form-select{font:inherit;color:var(--foreground);background:var(--background);border:1px solid var(--border);border-radius:7px;padding:6px 10px}.btn{cursor:pointer}.btn[aria-pressed=true]{background:var(--primary);color:var(--primary-foreground)}.btn:disabled{opacity:.45;cursor:default}.form-label{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.form-select{max-width:100%}a{color:var(--viz-series-1)}button:focus-visible,select:focus-visible{outline:2px solid var(--viz-series-1);outline-offset:2px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(max-width:500px){body{padding:12px}.btn,.form-select{min-height:40px}}
'''


def publish(store):
    body = fragment(store)
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>研究关系图</title><style>' + BASE + '</style><body><main>' + body + '</main></body></html>'
    path = store.root / 'research/graph.html'
    atomic(path, document)
    return str(path)
