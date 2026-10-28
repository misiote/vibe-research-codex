"""Explicit, recoverable workspace reset. Configuration and plugin code stay in place."""
import json,shutil,hashlib,uuid
from pathlib import Path
from .store import ResearchError,atomic,dumps,now
from . import hub,retrieval


def reset(workspace, confirmed=False):
    if not confirmed:raise ResearchError('重置需先取得用户对备份及数据范围的明确确认，再传 --confirmed')
    workspace=Path(workspace).expanduser().resolve()
    for row in hub.entries(workspace/'projects.json'):
        root=Path(row['root'])
        if not root.is_relative_to(workspace/'projects'):raise ResearchError('存在工作区外研究项目，需另行确认路径')
        if root.exists() and retrieval.snapshot(root)['worker_alive']:raise ResearchError('研究检索仍有实际 worker，请先停止实际运行再重置数据')
    paths=[workspace/'projects.json',workspace/'projects']+[workspace/'.vibe-research'/name for name in ('brainstorms','drafts','sessions','transfers','giver','workflow')]
    existing=[p for p in paths if p.exists()]
    dest=workspace/'research-backups'/('before-giver-'+uuid.uuid4().hex[:12]);dest.mkdir(parents=True)
    manifest={'created_at':now(),'workspace':str(workspace),'scope':[str(p.relative_to(workspace)) for p in existing],'files':{},'restoration':'停止工作台后，把 originals 中的各路径移回原位置；先另行备份新建研究。'}
    for p in existing:
        for f in ([p] if p.is_file() else p.rglob('*')):
            if f.is_file():
                if f.is_symlink():raise ResearchError('重置备份不跟随符号链接')
                manifest['files'][str(f.relative_to(workspace))]=hashlib.sha256(f.read_bytes()).hexdigest()
    atomic(dest/'manifest.json',dumps(manifest))
    # Same-filesystem renames preserve the complete databases, sidecars and attachments.
    for p in existing:
        target=dest/'originals'/p.relative_to(workspace);target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(p),str(target))
    for name,digest in manifest['files'].items():
        if hashlib.sha256((dest/'originals'/name).read_bytes()).hexdigest()!=digest:raise ResearchError('备份校验未通过，请保留 originals 核查')
    atomic(workspace/'projects.json',dumps({'version':3,'projects':[]}))
    return {'reset':True,'backup':str(dest),'files':len(manifest['files']),'note':'研究入口已清空，原始研究数据完整移入可恢复备份；配置、插件源码及验证记录保留。'}
