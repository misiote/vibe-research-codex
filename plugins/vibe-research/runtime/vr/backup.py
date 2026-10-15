"""Versioned research bundle: databases, tracked artifacts and recovery metadata."""
import contextlib,hashlib,json,os,shutil,sqlite3,tempfile,zipfile
from pathlib import Path,PurePosixPath
from .store import Store,ResearchError,now
from . import filelock as fcntl

DATABASES=('research.db','activity.db','retrieval.sqlite3')
METADATA=('nodes.json','branches.json','events.jsonl','project-identity.json','source-profile.json')

def allowed(name):
    p=PurePosixPath(name)
    return not p.is_absolute() and '..' not in p.parts and (name in {'.research/'+n for n in DATABASES+METADATA} or (len(p.parts)==3 and p.parts[:2]==('.research','artifacts')))

def create(root,destination):
    root=Path(root).resolve();destination=Path(destination).resolve();store=Store(root)
    store.db.close()
    if destination.exists():raise ResearchError('备份目标已存在，不覆盖')
    if root==destination or root in destination.parents:raise ResearchError('备份请保存到项目目录之外')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp,contextlib.ExitStack() as stack:
        stage=Path(tmp);home=stage/'.research';home.mkdir()
        lock=stack.enter_context(open(root/'.research/lock','a'));fcntl.flock(lock,fcntl.LOCK_EX)
        # Hold each database against writes while all three snapshots and immutable artifacts are read.
        for name in DATABASES:
            source=root/'.research'/name
            if not source.exists():continue
            guard=sqlite3.connect(source,timeout=30);stack.callback(guard.close);guard.execute('BEGIN IMMEDIATE')
        for name in DATABASES:
            source=root/'.research'/name
            if not source.exists():continue
            reader=sqlite3.connect(source);target=sqlite3.connect(home/name)
            try:
                reader.backup(target)
                # Portable snapshots must not require unbundled WAL/SHM sidecars.
                target.execute("PRAGMA journal_mode=DELETE")
            finally:reader.close();target.close()
        for name in METADATA:
            source=root/'.research'/name
            if source.exists():
                if source.is_symlink():raise ResearchError('备份不跟随符号链接')
                shutil.copyfile(source,home/name)
        artifacts=root/'.research/artifacts'
        if artifacts.exists():
            (home/'artifacts').mkdir()
            for source in artifacts.iterdir():
                if source.is_symlink() or not source.is_file():raise ResearchError('附件包含非普通文件，需核查')
                shutil.copyfile(source,home/'artifacts'/source.name)
        files={p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in home.rglob('*') if p.is_file() and allowed(p.relative_to(stage).as_posix())}
        manifest={'format':'vibe-research-bundle','version':1,'created_at':now(),'files':files,'scope':'研究数据库、工作历史、待补检索、已登记附件与身份；不包含外部代码、用户凭据或 Codex 任务'}
        bundle=stage/'bundle.zip'
        with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
            for name in files:archive.write(stage/name,name)
        # O_EXCL avoids overwriting even if another process creates the target meanwhile.
        with open(destination,'xb') as output,open(bundle,'rb') as source:shutil.copyfileobj(source,output)
    return {'backup':str(destination),'files':len(files),'scope':manifest['scope']}

def restore(source,destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ResearchError('恢复目标必须是不存在的新目录')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(source) as archive,tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        names=archive.namelist()
        if len(names)!=len(set(names)):raise ResearchError('备份包含重复路径')
        if sum(i.file_size for i in archive.infolist())>1024**3:raise ResearchError('备份超过 1 GiB，需单独审查恢复')
        if 'manifest.json' not in names:raise ResearchError('缺少备份清单')
        manifest=json.loads(archive.read('manifest.json'))
        files=manifest.get('files',{})
        if manifest.get('format')!='vibe-research-bundle' or manifest.get('version')!=1 or not isinstance(files,dict):raise ResearchError('不支持的备份格式')
        if set(names)!={'manifest.json',*files} or '.research/research.db' not in files or not all(allowed(n) for n in files):raise ResearchError('备份包含不支持的路径或缺失研究库')
        stage=Path(tmp)/'project';stage.mkdir()
        for name,digest in files.items():
            body=archive.read(name)
            if hashlib.sha256(body).hexdigest()!=digest:raise ResearchError('备份文件校验失败')
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
        # Older bundles can retain WAL mode even though the snapshot is standalone.
        # Normalize before read-only readers open databases without their sidecars.
        for name in DATABASES:
            path=stage/'.research'/name
            if path.exists():
                db=sqlite3.connect(path)
                try:db.execute('PRAGMA journal_mode=DELETE')
                finally:db.close()
        store=Store(stage)
        try:
            if not store.doctor()['ok']:raise ResearchError('恢复副本完整性检查失败')
            from . import activity
            active=activity.snapshot(stage,set())['current']
            if active and active['state'] in ('working','waiting','blocked'):
                activity.write(store,'pause',active['id'],message='从备份恢复；请核对产物、网络和当前目标',next_step='恢复核验后继续原工作')
            queue=stage/'.research/retrieval.sqlite3'
            if queue.exists():
                db=sqlite3.connect(queue)
                try:
                    with db:
                        db.execute('DELETE FROM workers');db.execute('UPDATE runs SET paused=1')
                        db.execute("UPDATE tasks SET status='queued',lease=NULL,lease_until=0 WHERE status='fetching'")
                finally:db.close()
            from .render import render
            render(store)
        finally:store.db.close()
        stage.rename(destination)
    return {'restored':str(destination),'note':'恢复到新目录；研究工作与检索已暂停，未启动后台任务。外部代码需另行恢复。'}
