"""Durable candidate retrieval, separate from reviewed research graph state.
A page and its continuation commit atomically. Import remains an explicit vr action.
"""
import contextlib, json, os, random, sqlite3, time, uuid
from xml.etree.ElementTree import ParseError
from pathlib import Path
from .store import ResearchError, Store, now, dumps
from . import filelock as fcntl, literature, request_gate

SCHEMA='''
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,title TEXT,spec TEXT,created TEXT,paused INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,run TEXT,query TEXT,provider TEXT,cursor TEXT,status TEXT,
 attempts INTEGER DEFAULT 0,next_retry REAL DEFAULT 0,pages INTEGER DEFAULT 0,total INTEGER,note TEXT DEFAULT '',lease TEXT,lease_until REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS pages(task TEXT,cursor TEXT,body TEXT,created TEXT,PRIMARY KEY(task,cursor));
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY,run TEXT,action TEXT,note TEXT,created TEXT);
CREATE TABLE IF NOT EXISTS workers(id TEXT PRIMARY KEY,heartbeat REAL);
'''
WAITING={'queued','waiting_rate_limit','waiting_network','waiting_service'}
LABELS={'queued':'等待检索','fetching':'正在查询','done':'已完成查询','waiting_rate_limit':'等待来源限流解除',
        'waiting_network':'等待网络恢复','waiting_service':'等待服务恢复','needs_auth':'需要配置权限','needs_review':'需要核查范围',
        'excluded':'已明确排除'}

def path(root): return Path(root)/'.research/retrieval.sqlite3'
@contextlib.contextmanager
def database(root, write=False):
    p=path(root)
    if not p.exists() and not write:
        yield None; return
    if write:
        if not (p.parent/'research.db').exists(): raise ResearchError('先初始化研究项目')
        db=sqlite3.connect(p,timeout=30);db.executescript(SCHEMA)
        db.execute('PRAGMA journal_mode=WAL')
    else: db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True,timeout=30)
    db.row_factory=sqlite3.Row
    try: yield db
    finally: db.close()

def audit(db,run,action,note):
    db.execute('INSERT INTO audit(run,action,note,created) VALUES(?,?,?,?)',(run,action,note,now()))

def start(root,title,queries,providers,include,page_size=25):
    queries=list(dict.fromkeys(q.strip() for q in queries if q.strip()))
    providers=list(dict.fromkeys(providers))
    search=[p for p in providers if p in literature.PROVIDERS]
    resolvers=[p for p in providers if p in literature.RESOLVERS]
    if not title.strip() or not include.strip() or not queries or not search or set(providers)-set(literature.ALL_SOURCES) or not 1<=page_size<=100:
        raise ResearchError('需要标题、查询、来源和纳入范围；分页大小 1..100')
    if len(queries)*len(search)>100:raise ResearchError('每轮最多 100 个来源查询组合')
    ident='S'+uuid.uuid4().hex[:12]
    spec={'queries':queries,'providers':search,'resolvers':resolvers,'include':include,'page_size':page_size,'mode':'coverage',
          'cost_policy':'free_first_no_automatic_purchase','created_at':now()}
    with database(root,True) as db,db:
        db.execute('INSERT INTO runs(id,title,spec,created) VALUES(?,?,?,?)',(ident,title,dumps(spec),now()))
        for q in queries:
            for p in search:
                db.execute('INSERT INTO tasks(id,run,query,provider,status) VALUES(?,?,?,?,?)',('T'+uuid.uuid4().hex[:12],ident,q,p,'queued'))
        audit(db,ident,'start','创建覆盖检索；结果仅为候选，不自动导入研究图')
    return {'id':ident,'state':'queued'}

def claim(root, worker, run=None):
    stamp=time.time()
    with database(root,True) as db,db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR REPLACE INTO workers VALUES(?,?)',(worker,stamp))
        db.execute("UPDATE tasks SET status='queued',lease=NULL,lease_until=0,note='请求执行中断；保留原游标重新查询' WHERE status='fetching' AND lease_until<?",(stamp,))
        row=db.execute("SELECT t.*,r.spec FROM tasks t JOIN runs r ON t.run=r.id WHERE r.paused=0 AND t.status IN ('queued','waiting_rate_limit','waiting_network','waiting_service') AND t.next_retry<=? AND (? IS NULL OR t.run=?) ORDER BY t.next_retry,t.pages,t.rowid LIMIT 1",(stamp,run,run)).fetchone()
        if not row:return None
        token=uuid.uuid4().hex
        db.execute("UPDATE tasks SET status='fetching',lease=?,lease_until=? WHERE id=?",(token,stamp+120,row['id']))
        return {**dict(row),'lease':token,'spec':json.loads(row['spec'])}

def finish_page(root,task,result):
    with database(root,True) as db,db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM tasks WHERE id=?',(task['id'],)).fetchone()
        if not row or row['lease']!=task['lease'] or row['status']!='fetching': return False
        cursor=task['cursor'] or ''
        nxt=result['next_cursor']; note=result.get('boundary') or ''
        if nxt is not None and db.execute('SELECT 1 FROM pages WHERE task=? AND cursor=?',(task['id'],str(nxt))).fetchone():
            note='来源游标发生循环，需核查范围';nxt=None
        existing=db.execute('SELECT 1 FROM pages WHERE task=? AND cursor=?',(task['id'],cursor)).fetchone()
        db.execute('INSERT INTO pages VALUES(?,?,?,?) ON CONFLICT(task,cursor) DO UPDATE SET body=excluded.body,created=excluded.created',(task['id'],cursor,dumps(result),now()))
        state='needs_review' if note else 'queued' if nxt is not None else 'done'
        db.execute('UPDATE tasks SET cursor=?,status=?,pages=pages+?,total=?,attempts=0,next_retry=0,note=?,lease=NULL,lease_until=0 WHERE id=?',
                   (task['cursor'] if note else nxt,state,0 if existing else 1,result.get('total'),note,task['id']))
        if task['provider'] not in literature.RESOLVERS and not existing:
            for resolver in task.get('spec',{}).get('resolvers',[]):
                for paper in result.get('papers',[]):
                    doi=paper.get('doi')
                    if doi:
                        doi=literature.clean_doi(doi)
                        if not db.execute('SELECT 1 FROM tasks WHERE run=? AND provider=? AND query=?',(task['run'],resolver,doi)).fetchone():
                            db.execute('INSERT INTO tasks(id,run,query,provider,status,note) VALUES(?,?,?,?,?,?)',
                                ('T'+uuid.uuid4().hex[:12],task['run'],doi,resolver,'queued','由候选 DOI 自动加入开放全文定位'))
        audit(db,task['run'],'page',task['provider']+' 已保存一页候选；'+LABELS[state])
    return True

def fail(root,task,exc):
    attempt=task['attempts']+1;stamp=time.time();delay=min(3600,60*2**min(attempt-1,6))+random.uniform(0,10)
    until=stamp+delay;state='waiting_network';note='网络或响应异常；游标与已有结果已保留'
    if isinstance(exc,request_gate.Deferred):
        state='waiting_rate_limit';until=exc.until;note=str(exc)
    elif isinstance(exc,literature.APIError):
        info=exc.diagnostic;code=info['http'];note=str(exc)
        if code==429:
            state='waiting_rate_limit';delay=info.get('retry_after_seconds',delay);until=stamp+max(1,delay)
            request_gate.cool(task['provider'],until)
        elif code in (401,403):state='needs_auth';until=0
        elif code>=500:state='waiting_service';until=stamp+max(delay,info.get('retry_after_seconds',0))
        else:state='needs_review';until=0
    elif isinstance(exc,literature.AuthenticationRequired):
        state='needs_auth';until=0;note=str(exc)
    elif isinstance(exc,(ValueError,KeyError,TypeError,ParseError)):
        state='needs_review';until=0;note='来源响应格式不符合预期；保留当前页供核查，不自动反复重试'
    elif isinstance(exc,ResearchError):
        # Transport errors have this explicit sanitized message; everything else needs inspection.
        if '网络、代理、TLS' not in str(exc):state='needs_review';until=0;note='配置或响应需要核查；未丢弃原查询'
    with database(root,True) as db,db:
        updated=db.execute('UPDATE tasks SET status=?,attempts=?,next_retry=?,note=?,lease=NULL,lease_until=0 WHERE id=? AND lease=? AND status=\'fetching\'',
                       (state,attempt,until,note,task['id'],task['lease'])).rowcount
        if updated:audit(db,task['run'],'wait',task['provider']+'：'+note)

def tick(root,run=None,worker=None):
    worker=worker or 'once-'+uuid.uuid4().hex
    task=claim(root,worker,run)
    if not task:return {'processed':False}
    s=Store(root)
    try:
        result=literature.search_page(literature.Router(s,defer=True),task['query'],task['provider'],task['cursor'],task['spec']['page_size'])
        finish_page(root,task,result)
    except (ResearchError,ValueError,KeyError,TypeError,ParseError,OSError) as exc:fail(root,task,exc)
    finally:s.db.close()
    return {'processed':True,'provider':task['provider']}

def control(root,ident,action,reason):
    if not reason.strip():raise ResearchError('需要记录原因')
    with database(root,True) as db,db:
        db.execute('BEGIN IMMEDIATE')
        run=db.execute('SELECT id FROM runs WHERE id=?',(ident,)).fetchone()
        if action in ('pause','resume'):
            if not run:raise ResearchError('检索工作不存在')
            db.execute('UPDATE runs SET paused=? WHERE id=?',(action=='pause',ident))
        elif action in ('exclude','retry'):
            task=db.execute('SELECT * FROM tasks WHERE id=?',(ident,)).fetchone()
            if not task:raise ResearchError('来源查询不存在')
            ident=task['run']
            if action=='exclude' and task['status']=='done':raise ResearchError('已完成来源不需要排除')
            if action=='retry' and task['status'] in ('fetching','done'):raise ResearchError('执行中或已完成的查询不可重置；需新建检索')
            # Retry never bypasses a persisted server cooldown.
            state='excluded' if action=='exclude' else 'queued'
            db.execute('UPDATE tasks SET status=?,note=?,lease=NULL,lease_until=0 WHERE id=?',(state,reason,task['id']))
        else:raise ResearchError('未知操作')
        audit(db,ident,action,reason)
    return {'ok':True}

def results_from(db,run):
    rows=db.execute('SELECT t.id,t.provider,t.query,p.body,p.created FROM pages p JOIN tasks t ON p.task=t.id WHERE t.run=? ORDER BY p.created,p.rowid',(run,))
    papers=[]; index={}
    for row in rows:
        for paper in json.loads(row['body'])['papers']:
            ids=literature.identifiers(paper)
            matches={index[i] for i in ids if i in index}
            provenance={'provider':row['provider'],'query':row['query'],'retrieved_at':row['created']}
            if matches:
                target=min(matches)
                # Merge bridged identifier sets, while retaining each source record.
                for other in matches-{target}:
                    papers[target]['sources']+=papers[other]['sources'];papers[other]['merged']=True
                    for k,v in list(index.items()):
                        if v==other:index[k]=target
                for field in ('doi','arxiv','abstract','url','pdf_url','year'):
                    if not papers[target].get(field) and paper.get(field):papers[target][field]=paper[field]
                papers[target]['sources'].append(provenance)
            else:
                target=len(papers);papers.append({**paper,'sources':[provenance]})
            for i in ids:index[i]=target
    return [p for p in papers if not p.get('merged')]

def snapshot(root,ident=None,include_results=False):
    with database(root) as db:
        if db is None:return {'runs':[],'worker_alive':False}
        stamp=time.time();runs=[]
        for r in db.execute('SELECT * FROM runs WHERE (? IS NULL OR id=?) ORDER BY created DESC LIMIT 20',(ident,ident)):
            tasks=[dict(t) for t in db.execute('SELECT * FROM tasks WHERE run=? ORDER BY rowid',(r['id'],))]
            for t in tasks:
                t.pop('lease',None);t['label']=LABELS[t['status']]
                if t['status']=='fetching' and t['lease_until']<stamp:t['label']='执行中断，等待恢复'
            terminal=all(t['status'] in ('done','excluded') for t in tasks)
            state='paused' if r['paused'] else 'completed_with_exclusions' if terminal and any(t['status']=='excluded' for t in tasks) else 'completed' if terminal else 'pending'
            papers=results_from(db,r['id'])
            item={**dict(r),'spec':json.loads(r['spec']),'state':state,'tasks':tasks,'candidate_count':len(papers),'done':sum(t['status']=='done' for t in tasks),'total_tasks':len(tasks)}
            if include_results:item['papers']=papers
            runs.append(item)
        return {'runs':runs,'worker_alive':bool(db.execute('SELECT 1 FROM workers WHERE heartbeat>? AND id NOT LIKE \'once-%\'',(stamp-45,)).fetchone())}

def work(root,seconds=300):
    lock=open(Path(root)/'.research/retrieval-worker.lock','a')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close(); return {'already_running':True}
    try: return _work(root,seconds)
    finally: lock.close()

def _work(root,seconds=300):
    if not 1<=seconds<=86400:raise ResearchError('worker 运行时长须为 1..86400 秒')
    worker='worker-'+uuid.uuid4().hex;end=time.monotonic()+seconds
    try:
        while time.monotonic()<end:
            if not tick(root,worker=worker)['processed']:
                with database(root) as db:
                    remaining=db.execute("SELECT 1 FROM tasks t JOIN runs r ON t.run=r.id WHERE r.paused=0 AND t.status IN ('queued','waiting_rate_limit','waiting_network','waiting_service','fetching') LIMIT 1").fetchone()
                if not remaining:break
                time.sleep(2)
    finally:
        with database(root,True) as db,db:db.execute('DELETE FROM workers WHERE id=?',(worker,))
    return {'stopped':True,'note':'未完成检索仍保留，可再次运行 worker'}


def launch(root,seconds=86400):
    import subprocess,sys
    if not 1<=seconds<=86400:raise ResearchError('worker 运行时长须为 1..86400 秒')
    if snapshot(root)['worker_alive']:return {'already_running':True}
    with database(root) as db:
        ready=db is not None and db.execute("SELECT 1 FROM tasks t JOIN runs r ON t.run=r.id WHERE r.paused=0 AND t.status IN ('queued','waiting_rate_limit','waiting_network','waiting_service','fetching') LIMIT 1").fetchone()
    if not ready:return {'started':False,'note':'没有可自动续查的项目；请先恢复暂停项或处理权限/范围问题'}
    home=Path(root)/'.research'
    detach={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS} if os.name=='nt' else {'start_new_session':True}
    with open(home/'retrieval-worker.log','ab') as log:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'bin/vr'),'--project',str(Path(root).resolve()),'retrieval','worker','--seconds',str(seconds)],stdout=log,stderr=log,**detach)
    for _ in range(30):
        if snapshot(root)['worker_alive']:return {'started':True,'seconds':seconds,'note':'本机运行；睡眠或关机将中断，待补项保留'}
        if child.poll() is not None:break
        time.sleep(.1)
    return {'started':False,'note':'未确认后台启动；请检查 retrieval-worker.log，进度仍保留'}


def report(root,ident):
    """Human-readable coverage and candidate view; all provider text is escaped."""
    from html import escape,unescape
    import re
    from urllib.parse import urlsplit
    data=snapshot(root,ident,True)
    if not data['runs']:raise ResearchError('检索不存在')
    run=data['runs'][0];esc=lambda value:escape(str(value or ''))
    names={'openalex':'OpenAlex','s2':'Semantic Scholar','arxiv':'arXiv','crossref':'Crossref','core':'CORE','huggingface':'Hugging Face','wos':'Web of Science','scopus':'Scopus','unpaywall':'Unpaywall'}
    states={'completed':'所选查询范围分页完成','completed_with_exclusions':'按缩减范围完成','pending':'仍有待补或待核查项','paused':'已暂停'}
    rows=[]
    for task in run['tasks']:
        rows.append('<tr>'+''.join('<td>'+esc(value)+'</td>' for value in [names.get(task['provider'],task['provider']),task['query'],task['label'],task['pages'],task.get('total'),task.get('note')])+'</tr>')
    papers=[]
    def plain(value):
        return unescape(re.sub(r'</?(?:jats:[\w-]+|i|b|em|strong|sup|sub|p|br)(?:\s[^>]*)?/?>','',str(value or ''),flags=re.I))
    for paper in run['papers']:
        title=esc(plain(paper.get('title')));url=paper.get('url') or ''
        try:safe=urlsplit(url).scheme in ('https','http') and bool(urlsplit(url).netloc)
        except (ValueError,TypeError):safe=False
        if safe:title='<a rel="noreferrer" target="_blank" href="'+escape(url,quote=True)+'">'+title+'</a>'
        providers=', '.join(dict.fromkeys(names.get(x['provider'],x['provider']) for x in paper['sources']))
        papers.append('<article data-paper><h3>'+title+'</h3><p>'+esc(paper.get('year'))+' · '+esc(providers)+'</p><details><summary>查看摘要</summary><p>'+esc(plain(paper.get('abstract')) or '本记录未提供摘要；尚未精读。')+'</p></details></article>')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(run['title'])+'</title><style>body{font:16px/1.7 system-ui;background:#f1f5fa;color:#20344e;margin:0}main{max-width:1050px;margin:auto;padding:30px}article,section{background:white;padding:20px;border-radius:12px;margin:18px 0}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}a{color:#175b9c}.table{overflow:auto}h3{margin:0}</style><main><a href="/">返回项目工作台</a><h1>'+esc(run['title'])+'</h1><p>'+esc(states[run['state']])+' · '+str(run['candidate_count'])+' 篇去重候选</p><p>这些是检索命中，尚未完成相关性筛选、全文阅读或证据审阅。来源完成仅指本次查询范围，不能保证所有相关文献均已找到。</p><section><h2>检索范围</h2><p>'+esc(run['spec']['include'])+'</p><p>创建时间：'+esc(run['created'])+'</p><div class="table"><table><thead><tr><th>来源</th><th>查询</th><th>状态</th><th>页数</th><th>来源报告总数</th><th>说明</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section><h2>候选文献</h2>'+(''.join(papers) or '<p>尚未保存候选。</p>')+'</main></html>'
