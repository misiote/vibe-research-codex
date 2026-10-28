"""User-facing work reports, separate from scientific evidence and graph revisions."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .store import ResearchError, now

ACTIVE = ('working', 'waiting', 'blocked')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,title TEXT NOT NULL,why TEXT NOT NULL,
 state TEXT NOT NULL,message TEXT NOT NULL,next_step TEXT NOT NULL,needs_user TEXT NOT NULL,
 nodes TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS continuations(run_id TEXT PRIMARY KEY REFERENCES runs(id), previous_id TEXT REFERENCES runs(id),reason TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active ON runs((1)) WHERE state IN ('working','waiting','blocked');
CREATE TABLE IF NOT EXISTS messages(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT REFERENCES runs(id),
 time TEXT NOT NULL,state TEXT NOT NULL,message TEXT NOT NULL,nodes TEXT NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL);
'''


def connect(root):
    db = sqlite3.connect(str(root / '.research/activity.db'), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript(SCHEMA)
    return db


def clean(text, label, required=False):
    text = (text or '').strip()
    if required and not text:
        raise ResearchError(label + '不能为空')
    if len(text) > 1600:
        raise ResearchError(label + '请控制在 1600 字以内')
    return text


def refs(store, nodes):
    valid = {n['id'] for n in store.rows('nodes')}
    nodes = list(dict.fromkeys(nodes or []))
    if any(n not in valid for n in nodes):
        raise ResearchError('关联节点不存在')
    return json.dumps(nodes)


def write(store, op, ident=None, title=None, why=None, state='working', message=None,
          next_step=None, needs_user=None, nodes=None, previous=None, reason=None):
    if state not in (*ACTIVE, 'completed', 'failed', 'paused', 'superseded'):
        raise ResearchError('未知工作状态')
    stamp = now()
    db = connect(store.root)
    try:
        db.execute('BEGIN IMMEDIATE')
        if op == 'start':
            if db.execute("SELECT 1 FROM runs WHERE state IN ('working','waiting','blocked')").fetchone():
                raise ResearchError('已有未结束的工作，请继续更新或结束它')
            if previous and not db.execute('SELECT 1 FROM runs WHERE id=?', (previous,)).fetchone():
                raise ResearchError('前序工作不存在')
            if previous: clean(reason, '接续理由', True)
            ident = 'W' + uuid.uuid4().hex[:12]
            title, why = clean(title, '工作目标', True), clean(why, '目的', True)
            message = title
            row = dict(id=ident, title=title, why=why, state='working', message=message,
                       next_step=clean(next_step, '下一步', True), needs_user='', nodes=refs(store, nodes),
                       created_at=stamp, updated_at=stamp)
            db.execute('INSERT INTO runs VALUES(:id,:title,:why,:state,:message,:next_step,:needs_user,:nodes,:created_at,:updated_at)', row)
            if previous:
                db.execute('INSERT INTO continuations VALUES(?,?,?)', (ident,previous,reason))
        else:
            record = db.execute('SELECT * FROM runs WHERE id=?', (ident,)).fetchone()
            if not record or record['state'] not in ((*ACTIVE, 'paused') if op in ('resume','finish') else ACTIVE):
                raise ResearchError('工作不存在或已经结束；请开始新的工作')
            row = dict(record)
            if op == 'resume':
                if db.execute("SELECT 1 FROM runs WHERE state IN ('working','waiting','blocked') AND id<>?", (ident,)).fetchone():
                    raise ResearchError('已有其他进行中的工作，先明确暂停或结束它')
                state = 'working'
            if op == 'pause': state = 'paused'
            if op == 'heartbeat':
                db.execute('UPDATE runs SET updated_at=? WHERE id=?', (stamp, ident))
                db.commit()
                return {'id': ident, 'updated_at': stamp}
            row.update(state=state, message=clean(message, '进展说明', True), updated_at=stamp,
                       next_step=clean(next_step, '下一步', True), needs_user=clean(needs_user, '需要用户决定的事项'))
            if nodes is not None:
                row['nodes'] = refs(store, nodes)
            db.execute('UPDATE runs SET state=:state,message=:message,next_step=:next_step,needs_user=:needs_user,nodes=:nodes,updated_at=:updated_at WHERE id=:id', row)
        db.execute('INSERT INTO messages(run_id,time,state,message,nodes,kind,detail) VALUES(?,?,?,?,?,?,?)',
                   (ident, stamp, row['state'], row['message'], row['nodes'], 'report', '助手报告；关联节点可用于核对产出，报告本身不是研究证据。'))
        db.commit()
        return {'id': ident, 'state': row['state'], 'message': row['message']}
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


# Only meaningful operations, not every status read or tool token. Never capture args, SQL, logs or secrets.
ACTIONS = {
    'scout': '归档文献检索与候选线索', 'bibliography': '生成书目与离线校验记录',
    'search': '文献检索', 'paper.import': '导入文献记录', 'paper.attach': '归档文献全文',
    'paper.expand': '扩展引用线索', 'reading.add': '保存精读证据（仍需审阅）',
    'reading.depth': '选择文献阅读深度', 'reading.note': '保存概要或粗读笔记',
    'engineering.link':'关联研究开发环境', 'engineering.task':'更新工程工作包','engineering.sync':'采集开发进度快照',
    'history.search':'建立主题历史检索',
    'history.add': '归档研究历史时间轴', 'direction.save': '保存研究方向评估',
    'reading.review': '记录证据审阅', 'reading.complete': '检查并标记精读完成',
    'node.add': '保存研究节点', 'edge.add': '建立研究关系', 'edge.remove': '移除研究关系',
    'transition': '记录研究状态变化', 'artifact.add': '归档研究产物',
    'experiment.plan': '建立实验计划（尚无结果）', 'experiment.ingest': '归档实验结果',
    'failure.add': '记录失败与恢复条件', 'decide': '记录路线决策',
    'branch.add': '建立研究分支', 'branch.attach': '关联研究分支',
    'integrations.check': '检查工具接入', 'integrations.record': '保存接入检查记录',
    'doctor': '检查研究库完整性', 'db.backup': '备份研究库', 'db.repair': '修复图快照',
}


def operation(root, args, result=None, failed=False):
    key = args.cmd + ('.' + args.op if getattr(args, 'op', None) else '')
    if key not in ACTIONS or not (root / '.research/research.db').exists():
        return
    # References are subsequently filtered against current graph in the read API.
    ids = [getattr(args, k) for k in ('id', 'source', 'target', 'hypothesis') if isinstance(getattr(args, k, None), str)]
    if isinstance(result, dict) and isinstance(result.get('id'), str):
        ids.append(result['id'])
    elif isinstance(result, str):
        ids.append(result)
    db = connect(root)
    try:
        with db:
            active = db.execute("SELECT id FROM runs WHERE state IN ('working','waiting','blocked')").fetchone()
            message = ACTIONS[key] + ('未完成，需要检查' if failed else '：操作已完成')
            if key == 'integrations.check' and not failed:
                message = '接入检查已返回；各工具是否可用请查看检查结果'
            db.execute('INSERT INTO messages(run_id,time,state,message,nodes,kind,detail) VALUES(?,?,?,?,?,?,?)',
                       (active['id'] if active else None, now(), 'failed' if failed else 'completed', message,
                        json.dumps(list(dict.fromkeys(ids))), 'operation', key + (' 返回错误；查看 Codex 工具详情。' if failed else ' 命令返回成功；不等于研究结论已验证。')))
    finally:
        db.close()


def snapshot(root, valid_nodes, clock=None):
    path = root / '.research/activity.db'
    if not path.exists():
        return {'current': None, 'messages': []}
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN')
        current = db.execute("SELECT * FROM runs ORDER BY CASE WHEN state IN ('working','waiting','blocked') THEN 0 ELSE 1 END,updated_at DESC,rowid DESC LIMIT 1").fetchone()
        messages = db.execute('SELECT * FROM messages ORDER BY seq DESC LIMIT 60').fetchall()
        def decode(r):
            r = dict(r)
            r['nodes'] = [n for n in json.loads(r['nodes']) if n in valid_nodes]
            return r
        current = decode(current) if current else None
        if current:
            current['age_seconds'] = max(0, int(((clock or datetime.now(timezone.utc)) - datetime.fromisoformat(current['updated_at'])).total_seconds()))
            current['stale'] = current['state'] in ACTIVE and current['age_seconds'] > 120
        return {'current': current, 'messages': [decode(m) for m in messages]}
    finally:
        db.close()


def instructions():
    return '''
## 工作过程对用户可见

工作接续遵循工具目录 skills/vibe-research-continuity/SKILL.md（或宿主工作区同名 skill）。先按项目读取 work history/recover 判断目标：同一未完成目标继续，暂停后 resume 原编号；已完成后的新目标用 start --previous 并写理由。长期离开先核对产物、版本和阻塞，不按时间自动拆分目标。固定项目入口由工作区 open-workbench.py 启动。

每轮开始先 `vr work status` 恢复未结束的工作；没有活动工作时，用 `vr work start --title '当前目标' --why '研究意义' --next-step '下一步'` 创建工作记录。
有实质进展、改变方向、产出落盘、遇到阻碍或结束时，用 `vr work update/finish` 写简短自然语言说明；通过 --nodes 关联真实产物。用 --help 查看参数。
区分“已找到全文”“证据待审阅”“结论已验证”；工作报告不当作研究证据。默认不汇报原始命令、内部思考、令牌流和重复日志，不写入密钥。
超过约一分钟的长操作，在确实仍执行或等待时更新说明或用 `vr work heartbeat`；不得用脱离实际执行的永久心跳冒充在工作。
需要用户决定时用 --needs-user 写出问题，并在 Codex 对话中提问；页面提示不能替代用户回答。结束、失败和暂停等待都如实记录，不能留下虚假的运行状态。
文献工作使用 `vr scout` 记录查询、纳入标准与命中来源，导入后用 `vr reading triage` 记录初筛理由。按任务使用 `vr reading plan` 选择概要、粗读或精读，并检查 `vr reading queue`；概要可基于摘要，粗读与精读需要全文。概要或粗读用 `vr reading note` 保存，不当作精读证据；需要精读时用 `vr reading packet` 执行逐页审计，缺全文则记录阻塞。`vr bibliography` 输出书目与离线校验。工作区存在 citation-management / scientific-critical-thinking 技能时，先阅读相关 SKILL.md；不要把初筛有价值、技能加载或离线校验当成研究结论验证。
用户可用 `vr watch` 打开动态工作现场。CLI 自动记录重要操作，CLI 外的工作由助手主动汇报；这不是对所有 Codex 工具的自动监听。
'''


def history(root, limit=50, offset=0, since=None, until=None):
    """Read complete work units with pagination; dates filter last substantive update in UTC."""
    if not 1 <= limit <= 200 or offset < 0:
        raise ResearchError('limit 应为 1–200，offset 不得为负')
    clauses=[]; values=[]
    for value,op in ((since, '>='),(until, '<=')):
        if value:
            try:
                datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                raise ResearchError('日期应为 YYYY-MM-DD（UTC）')
            clauses.append('substr(updated_at,1,10) '+op+' ?');values.append(value)
    if since and until and since > until: raise ResearchError('开始日期不能晚于结束日期')
    path=Path(root)/'.research/activity.db'
    if not path.exists(): return {'runs':[], 'total':0, 'next_offset':None}
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN')
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        total=db.execute('SELECT count(*) FROM runs'+where, values).fetchone()[0]
        rows=[dict(r) for r in db.execute('SELECT * FROM runs'+where+' ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?',values+[limit,offset])]
        has_links=db.execute("SELECT 1 FROM sqlite_master WHERE name='continuations'").fetchone()
        for r in rows:
            r['nodes']=json.loads(r['nodes'])
            link=db.execute('SELECT previous_id,reason FROM continuations WHERE run_id=?',(r['id'],)).fetchone() if has_links else None
            r['continuation']=dict(link) if link else None
            r['age_seconds']=max(0,int((datetime.now(timezone.utc)-datetime.fromisoformat(r['updated_at'])).total_seconds()))
            r['recovery_required']=r['state'] in (*ACTIVE,'paused') and r['age_seconds'] >= 86400
        return {'runs':rows,'total':total,'next_offset':offset+limit if offset+limit<total else None}
    finally: db.close()


def recovery(root, ident):
    path=Path(root)/'.research/activity.db'
    if not path.exists(): raise ResearchError('工作不存在')
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        row=db.execute('SELECT * FROM runs WHERE id=?',(ident,)).fetchone()
        if not row: raise ResearchError('工作不存在')
        row=dict(row);row['nodes']=json.loads(row['nodes'])
        row['messages']=[dict(r) for r in db.execute('SELECT time,state,message,detail FROM messages WHERE run_id=? ORDER BY seq DESC LIMIT 20',(ident,))]
        age=max(0,int((datetime.now(timezone.utc)-datetime.fromisoformat(row['updated_at'])).total_seconds()))
        row['age_seconds']=age
        row['recommendation']='新工作并关联此前记录' if row['state'] in ('completed','failed','superseded') else '核对现场后继续同一工作；目标改变时暂停旧工作并另建'
        row['checks']=['核对用户当前目标和授权','查看关联产物、研究版本及代码变化','重验阻塞条件和仍在运行的任务','记录恢复依据与下一步']
        row['note']='只读建议；时间间隔不自动改变工作状态，>=24小时建议完整恢复核验。'
        return row
    finally: db.close()
