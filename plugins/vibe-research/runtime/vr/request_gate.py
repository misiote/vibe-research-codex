"""Host-wide, credential-scoped admission and cooldown. No credentials stored."""
import hashlib, os, sqlite3, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .connections import credential
from .store import ResearchError

class Deferred(ResearchError):
    def __init__(self, until, message='来源请求间隔或配额等待'):
        self.until = until
        super().__init__(message)

def location():
    if os.name=='nt':
        default=Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming')))/'VibeResearch/runtime'
    else:
        default=Path.home()/'.config/vibe-research'
    return Path(os.environ.get('VR_RUNTIME_DIR',str(default))) / 'request-budget.sqlite3'

def scope(provider):
    key, _ = credential(provider)
    return provider + ':' + hashlib.sha256((key or 'anonymous').encode()).hexdigest()

def connect():
    p=location()
    try:
        p.parent.mkdir(parents=True,exist_ok=True,mode=0o777 if os.name=='nt' else 0o700)
        db=sqlite3.connect(p,timeout=30)
    except (OSError,sqlite3.Error) as exc:
        raise ResearchError('无法打开本机请求预算库；请使用同一用户运行工作台和检索，或为 VR_RUNTIME_DIR 选择该用户可写的位置。') from exc
    db.execute('CREATE TABLE IF NOT EXISTS gates(scope TEXT PRIMARY KEY, day TEXT, calls INTEGER, next REAL, cooldown REAL)')
    return db

def tomorrow():
    return (datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)).timestamp()

def admit(provider, limit=50):
    key=scope(provider); stamp=time.time(); day=datetime.now(timezone.utc).date().isoformat()
    db=connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT day,calls,next,cooldown FROM gates WHERE scope=?',(key,)).fetchone()
        calls=row[1] if row and row[0]==day else 0
        due=max(row[2],row[3]) if row else 0
        if calls>=limit: due=max(due,tomorrow())
        if due>stamp: raise Deferred(due,'来源共享冷却中；进度已保留')
        interval=3.1 if provider=='arxiv' else 10.1 if provider=='core' else 1.1
        db.execute('INSERT OR REPLACE INTO gates VALUES(?,?,?,?,?)',(key,day,calls+1,stamp+interval,0))
        db.commit()
    finally: db.close()

def cool(provider, until):
    key=scope(provider); db=connect()
    try:
        with db:
            db.execute('INSERT INTO gates VALUES(?,?,0,0,?) ON CONFLICT(scope) DO UPDATE SET cooldown=max(cooldown,excluded.cooldown)',(key,datetime.now(timezone.utc).date().isoformat(),until))
    finally: db.close()
