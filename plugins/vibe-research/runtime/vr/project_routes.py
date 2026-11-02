"""Read-only research projections, independent of workspace configuration."""
import json
import re
from urllib.parse import urlsplit, parse_qs
from . import activity, retrieval
from .store import Store, ResearchError
from .web_response import reply


def read(route, path, root):
    if re.fullmatch(r'/retrieval/report/S[a-f0-9]{12}',route):
        return reply(200,'text/html',retrieval.report(root,route.rsplit('/',1)[-1]).encode())
    if re.fullmatch(r'/api/retrieval/export/S[a-f0-9]{12}',route):
        data=retrieval.snapshot(root,route.rsplit('/',1)[-1],True)
        if not data['runs']:raise ResearchError('检索不存在')
        return reply(200,'application/json',json.dumps(data['runs'][0],ensure_ascii=False).encode())
    if route.startswith('/api/research/'):
        from . import history, directions
        q=parse_qs(urlsplit(path).query)
        s=Store(root)
        try:
            if route == '/api/research/history':
                data=history.snapshot(s,q.get('scope',['global'])[0],q.get('focus',[None])[0],q.get('topic',[''])[0],q.get('since',[None])[0],q.get('until',[None])[0],q.get('subtopic',[''])[0],q.get('aliases',[''])[0])
            elif route == '/api/research/history/search':
                data=retrieval.snapshot(root,q.get('run',[None])[0],True)
            elif route == '/api/research/engineering':
                from . import engineering
                data=engineering.snapshot(s)
            elif route == '/api/research/directions':
                data={'assessments':[n for n in s.rows('nodes') if n['data'].get('source_type')=='direction_assessment'], 'packet':directions.packet(s)}
            else: raise ResearchError('未知研究视图')
        finally: s.db.close()
        return reply(200,'application/json',json.dumps(data,ensure_ascii=False).encode())
    if route == '/api/history':
        q=parse_qs(urlsplit(path).query)
        data=activity.history(root,int(q.get('limit',['50'])[0]),int(q.get('offset',['0'])[0]),q.get('since',[None])[0],q.get('until',[None])[0])
        return reply(200,'application/json',json.dumps(data,ensure_ascii=False).encode())
    return None
