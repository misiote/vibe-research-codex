import argparse
import json
import sqlite3
import sys
from pathlib import Path
from .store import Store, ResearchError, KINDS, RELATIONS, dumps
from . import literature, reading, experiments
from .render import render, gaps


def load(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def parser():
    p = argparse.ArgumentParser(prog="vr", description="Vibe Research：用可追溯有向图管理研究")
    p.add_argument("--project", help="研究项目目录；默认向上查找 .research")
    sub = p.add_subparsers(dest="cmd", required=True)
    def command(name, args=(), parent=sub):
        c = parent.add_parser(name)
        for names, options in args:
            c.add_argument(*names.split(), **options)
        return c
    def arg(name, **options):
        return (name, options)
    def group(name):
        return sub.add_parser(name).add_subparsers(dest="op", required=True)
    command("init", [arg("--question", required=True)])
    for name in ("status", "tree", "doctor", "gaps", "progress", "graph"):
        command(name)
    command("scout", [arg("--query", action="append", required=True), arg("--provider", action="append", choices=literature.PROVIDERS), arg("--include", required=True), arg("--limit", type=int, default=5), arg("--offline", action="store_true")])
    bundle = group('bundle')
    command('create',[arg('path')],bundle)
    command('restore',[arg('path'),arg('--destination',required=True)],bundle)
    retrieval = group('retrieval')
    command('start', [arg('--title',required=True),arg('--query',action='append',required=True),arg('--provider',action='append',choices=literature.ALL_SOURCES),arg('--include',required=True),arg('--page-size',type=int,default=25)],retrieval)
    command('status',[arg('id',nargs='?')],retrieval)
    command('tick',[arg('--run')],retrieval)
    command('worker',[arg('--seconds',type=int,default=300)],retrieval)
    command('launch',[arg('--seconds',type=int,default=86400)],retrieval)
    for op in ('pause','resume','exclude','retry'):
        command(op,[arg('id'),arg('--reason',required=True)],retrieval)
    command('export',[arg('id')],retrieval)
    command('import',[arg('id'),arg('--branch')],retrieval)
    command('backup',[arg('path')],retrieval)
    command("bibliography")
    command("watch", [arg("--port", type=int, default=8765), arg("--open", action="store_true")])
    work = group("work")
    command("start", [arg("--title", required=True), arg("--why", required=True), arg("--next-step", required=True), arg("--nodes", nargs="*"), arg("--previous"), arg("--reason")], work)
    command("update", [arg("id"), arg("--state", choices=("working", "waiting", "blocked"), default="working"), arg("--message", required=True), arg("--next-step", required=True), arg("--needs-user"), arg("--nodes", nargs="*")], work)
    command("finish", [arg("id"), arg("--state", choices=("completed", "failed", "superseded"), default="completed"), arg("--message", required=True), arg("--next-step", required=True), arg("--nodes", nargs="*")], work)
    command("heartbeat", [arg("id")], work)
    command("status", parent=work)
    command("history", [arg("--limit", type=int, default=50), arg("--offset", type=int, default=0), arg("--since"), arg("--until")], work)
    command("recover", [arg("id")], work)
    for op in ('pause','resume'):
        command(op, [arg('id'),arg('--message',required=True),arg('--next-step',required=True),arg('--nodes',nargs='*')], work)
    hub = group('hub')
    for op in ('list','serve','add'):
        opts=[arg('--registry', default='projects.json')]
        if op=='serve': opts += [arg('--port',type=int,default=8765),arg('--open',action='store_true')]
        if op=='add': opts += [arg('path'),arg('--name',required=True)]
        command(op,opts,hub)
    for op in ('archive','restore','remove'):
        command(op,[arg('id'),arg('--registry',default='projects.json'),arg('--reason',required=True)],hub)
    command('bind-codex',[arg('id'),arg('--registry',default='projects.json'),arg('--codex-id',required=True),arg('--codex-root',required=True),arg('--name',required=True),arg('--host',default='local')],hub)
    command('relate',[arg('source'),arg('target'),arg('--kind',required=True,choices=('derived_from','related_to','reproduces')),arg('--reason',required=True),arg('--registry',default='projects.json')],hub)
    command('relocate',[arg('id'),arg('path'),arg('--registry',default='projects.json')],hub)
    command('create',[arg('--registry',default='projects.json'),arg('--name',required=True),arg('--question',required=True),arg('--provider',action='append',required=True,choices=literature.ALL_SOURCES),arg('--request-id',required=True)],hub)
    command("trace", [arg("id")])
    command("decide", [arg("target"), arg("action", choices=("continues", "modifies", "prunes", "revives")), arg("--reason", required=True), arg("--evidence", required=True), arg("--revival")])
    command("compare", [arg("left"), arg("right")])
    node = group("node")
    command("add", [arg("kind", choices=KINDS), arg("--title", required=True), arg("--data"), arg("--branch")], node)
    command("show", [arg("id")], node)
    command("list", [arg("--kind", choices=KINDS)], node)
    edge = group("edge")
    for name in ("add", "remove"):
        command(name, [arg("source"), arg("relation", choices=RELATIONS), arg("target")], edge)
    command("list", parent=edge)
    branch = group("branch")
    command("add", [arg("--title", required=True), arg("--parent")], branch)
    command("attach", [arg("branch"), arg("node")], branch)
    command("list", parent=branch)
    command("transition", [arg("id"), arg("state"), arg("--reason", required=True), arg("--evidence"), arg("--revival")])
    db = group("db")
    command("query", [arg("sql"), arg("--params", default="[]")], db)
    for name in ("schema", "repair", "restore"):
        command(name, parent=db)
    command("backup", [arg("path")], db)
    command("search", [arg("query"), arg("--provider", choices=("auto",) + literature.ALL_SOURCES, default="auto"), arg("--limit", type=int, default=10), arg("--offline", action="store_true"), arg("--import", dest="import_results", action="store_true"), arg("--branch")])
    paper = group("paper")
    command("import", [arg("path"), arg("--branch")], paper)
    command("attach", [arg("id"), arg("path")], paper)
    command("expand", [arg("id"), arg("--direction", choices=("references", "citations"), default="references"), arg("--limit", type=int, default=20), arg("--offline", action="store_true"), arg("--import", dest="import_results", action="store_true")], paper)
    command("export", [arg("--format", choices=("csl",), default="csl")], paper)
    command("find", [arg("id"), arg("query")], paper)
    read = group("reading")
    for name in ("packet", "report", "complete"):
        command(name, [arg("id")], read)
    command("triage", [arg("id"), arg("verdict", choices=tuple(sorted(reading.SCREENING_VERDICTS))),
                       arg("--reason", required=True), arg("--basis", choices=tuple(sorted(reading.SCREENING_BASES)), default="title_abstract")], read)
    command("queue", parent=read)
    command("add", [arg("id"), arg("path")], read)
    command("review", [arg("id"), arg("verdict", choices=("accepted", "rejected")), arg("--reason", required=True)], read)
    experiment = group("experiment")
    command("validate", [arg("spec")], experiment)
    command("plan", [arg("hypothesis"), arg("spec")], experiment)
    command("ingest", [arg("id"), arg("metrics"), arg("--config", required=True), arg("--log", required=True), arg("--repo", required=True), arg("--commit", required=True), arg("--seeds", required=True, nargs="+", type=int)], experiment)
    failure = group("failure")
    command("add", [arg("source")] + [arg("--" + f, required=True) for f in ("reason", "evidence", "do-not-repeat", "revival")], failure)
    command("show", [arg("id")], failure)
    artifact = group("artifact")
    command("add", [arg("path"), arg("--title", required=True), arg("--source"), arg("--branch")], artifact)
    integrations = group("integrations")
    command("check", [arg("--network", action="store_true")], integrations)
    command("setup", [arg("--provider", choices=("openalex","s2","wos","scopus","scopus_insttoken","unpaywall")),arg("--backend",choices=("keychain","file"))], integrations)
    command("verify",[arg("provider",choices=("wos","scopus","unpaywall")),arg("--query",required=True)],integrations)
    command("context",[arg("provider",choices=("wos","scopus","unpaywall","campus")),arg("--network",required=True,choices=("campus","off_campus","unknown"))],integrations)
    command("route",[arg("provider",choices=("scopus","wos")),arg("--institution",required=True,choices=("casia","custom","none")),arg("--name",default=""),arg("--portal-url",default=""),arg("--method",required=True,choices=("auto","campus_vpn","browser_portal","institutional_token","public_only")),arg("--network",default="unknown",choices=("campus","off_campus","unknown"))],integrations)
    command("network",parent=integrations)
    command("diagnostics",[arg("path")],integrations)
    command("status", parent=integrations)
    command("record", [arg("name"), arg("--status", required=True, choices=("passed", "partial", "blocked", "unverified")), arg("--level", required=True), arg("--evidence", required=True), arg("--next-step", required=True)], integrations)
    project = group("project")
    command("render", parent=project)
    return p


def root_path(value):
    if value:
        return Path(value).resolve()
    cwd = Path.cwd()
    return next((p for p in [cwd, *cwd.parents] if (p / ".research").is_dir()), cwd)


def mutate(s, a, callback, check=True):
    with s.write(a.cmd + "." + getattr(a, "op", "update"), vars(a), check=check):
        result = callback()
    safe_render(s)
    return result if result is not None else {"ok": True, "revision": s.revision()}


def safe_render(s):
    from . import filelock as fcntl
    with open(s.home / "lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            s.db.execute("BEGIN")
            result = render(s)
            s.db.commit()
            return result
        finally:
            s.db.rollback()
            fcntl.flock(lock, fcntl.LOCK_UN)


def run(a):
    root = root_path(a.project)
    if a.cmd == 'bundle':
        from . import backup
        return backup.create(root,a.path) if a.op=='create' else backup.restore(a.path,a.destination)
    if a.cmd == 'hub':
        from . import hub
        if a.op in ('archive','restore','remove'): return hub.lifecycle(a.registry,a.id,a.op,a.reason)
        if a.op=='bind-codex': return hub.bind_codex(a.registry,a.id,a.codex_id,a.codex_root,a.name,a.host)
        if a.op=='relate': return hub.relate(a.registry,a.source,a.target,a.kind,a.reason)
        if a.op=='relocate': return hub.relocate(a.registry,a.id,a.path)
        if a.op=='create': return hub.create(a.registry,a.name,a.question,a.provider,a.request_id)
        if a.op=='add': return hub.register(a.registry,a.path,a.name)
        if a.op=='list': return hub.catalog(a.registry)
        from .watch import serve
        return serve(root,a.port,a.open,registry=a.registry)
    if a.cmd == "init":
        return safe_render(Store.init(root, a.question))
    if a.cmd == "db" and a.op == "restore":
        return safe_render(Store.restore(root))
    if a.cmd == "watch":
        from .watch import serve
        return serve(root, a.port, a.open)
    s = Store(root)
    if a.cmd == "work":
        from . import activity
        if a.op == 'history': return activity.history(root,a.limit,a.offset,a.since,a.until)
        if a.op == 'recover': return activity.recovery(root,a.id)
        if a.op == "status":
            return activity.snapshot(root, {n['id'] for n in s.rows('nodes')})
        kwargs = {k: getattr(a, k) for k in ('title', 'why', 'state', 'message', 'next_step', 'needs_user', 'nodes', 'previous', 'reason') if hasattr(a, k)}
        return activity.write(s, a.op, ident=getattr(a, 'id', None), **kwargs)
    if a.cmd == 'retrieval':
        from . import retrieval
        if a.op=='start':
            profile=root/'.research/source-profile.json'
            saved=load(profile) if profile.exists() else {}
            selected=a.provider or ((saved.get('providers') or [])+(saved.get('resolvers') or []) if saved else None) or list(literature.COVERAGE_PROVIDERS)
            return retrieval.start(root,a.title,a.query,selected,a.include,a.page_size)
        if a.op=='status': return retrieval.snapshot(root,a.id)
        if a.op=='tick': return retrieval.tick(root,a.run)
        if a.op=='worker': return retrieval.work(root,a.seconds)
        if a.op=='launch': return retrieval.launch(root,a.seconds)
        if a.op in ('pause','resume','exclude','retry'): return retrieval.control(root,a.id,a.op,a.reason)
        if a.op=='backup':
            target=Path(a.path)
            if target.exists(): raise ResearchError('备份目标已存在')
            with retrieval.database(root) as db:
                if db is None: raise ResearchError('尚无检索库')
                dest=sqlite3.connect(target)
                try: db.backup(dest)
                finally: dest.close()
            return {'path':str(target.resolve())}
        data=retrieval.snapshot(root,a.id,True)
        if not data['runs']: raise ResearchError('检索工作不存在')
        if a.op=='export': return data['runs'][0]
        return mutate(s,a,lambda:{'ids':[literature.import_paper(s,p,a.branch) for p in data['runs'][0]['papers']], 'coverage_state':data['runs'][0]['state']})
    if a.cmd == "scout":
        from .workflows import scout, archive_scout
        record = scout(s, a.query, a.provider or list(literature.PROVIDERS), a.limit, a.include, a.offline)
        return mutate(s, a, lambda: archive_scout(s, record))
    if a.cmd == "bibliography":
        from .workflows import bibliography
        return bibliography(s)
    if a.cmd == "graph":
        safe_render(s)
        return {"graph": str(s.root / "research/graph.html"), "revision": s.revision(), "note": "只读关系图；修改关系仍通过 vr 命令"}
    if a.cmd == "progress":
        from .progress import publish
        return publish(s)
    if a.cmd == "integrations":
        from .integrations import check, record
        from . import connections
        if a.op=="diagnostics":
            from . import diagnostics
            return diagnostics.export(root,a.path)
        if a.op in ("verify","context"):
            from . import access
            return access.verify(root,a.provider,a.query) if a.op=="verify" else access.context(root,a.provider,a.network)
        if a.op in ("route","network"):
            from . import network_access
            return network_access.status() if a.op=="network" else network_access.configure(a.provider,a.institution,a.name,a.portal_url,a.method,a.network)
        if a.op == "setup": return connections.setup(a.provider,a.backend)
        if a.op == "status": return connections.status()
        if a.op == "check":
            return check(s, a.network)
        return record(s, a.name, a.status, a.level, a.evidence, a.next_step)
    if a.cmd == "doctor":
        result = s.doctor()
        if not result["ok"]:
            raise ResearchError(dumps(result))
        return result
    if a.cmd == "status":
        return {"project": str(root), "revision": s.revision(), "question": s.db.execute("SELECT value FROM meta WHERE key='question'").fetchone()[0], "branches": s.rows("branches"), "nodes": [{k: n[k] for k in ("id", "kind", "title", "status")} for n in s.rows("nodes")], "next_actions": gaps(s), "recent_events": s.rows("events")[-5:]}
    if a.cmd == "tree":
        return {t: s.rows(t) for t in ("nodes", "branches", "edges", "members")}
    if a.cmd == "trace":
        return s.trace(a.id)
    if a.cmd == "compare":
        left, right = s.get(a.left), s.get(a.right)
        connected_left = s.walk(a.left) | s.walk(a.left, "backward") | {a.left}
        connected_right = s.walk(a.right) | s.walk(a.right, "backward") | {a.right}
        return {"left": left, "right": right, "shared_context": sorted(connected_left & connected_right),
                "left_only": sorted(connected_left - connected_right), "right_only": sorted(connected_right - connected_left),
                "review_dimensions": ["problem", "method", "assumption", "experiment", "result", "limitation", "reproduction"],
                "note": "结构比较与原始数据；方法优劣和研究新颖性需要结合精读证据判断。"}
    if a.cmd == "decide":
        def decide():
            item = s.get(a.target)
            if item.get("kind") != "H" and not a.target.startswith("B"):
                raise ResearchError("决策对象必须是 H 或 B")
            s.get(a.evidence)
            if a.action == "prunes":
                s.transition(a.target, "pruned", a.reason, a.evidence, a.revival)
            elif a.action == "revives":
                if item["status"] not in {"pruned", "rejected", "failed"}:
                    raise ResearchError("只有已剪枝/拒绝/失败的对象可以 revive")
                s.transition(a.target, "active", a.reason, a.evidence)
            elif not a.reason.strip():
                raise ResearchError("决策 reason 不能为空")
            ident = s.add_node("D", a.reason, {"target": a.target, "action": a.action, "evidence": a.evidence, "revival_condition": a.revival})
            if item.get("kind") == "H":
                s.add_edge(ident, a.action, a.target)
            return {"id": ident, "target": a.target, "action": a.action}
        return mutate(s, a, decide)
    if a.cmd == "gaps":
        return gaps(s)
    if a.cmd == "node":
        if a.op == "show":
            return s.get(a.id)
        if a.op == "list":
            return [n for n in s.rows("nodes") if not a.kind or n["kind"] == a.kind]
        return mutate(s, a, lambda: {"id": s.add_node(a.kind, a.title, load(a.data) if a.data else {}, a.branch)})
    if a.cmd == "edge":
        if a.op == "list":
            return s.rows("edges")
        def edit():
            if a.op == "add":
                s.add_edge(a.source, a.relation, a.target)
            else:
                cursor = s.db.execute("DELETE FROM edges WHERE source=? AND relation=? AND target=?", (a.source, a.relation, a.target))
                if not cursor.rowcount:
                    raise ResearchError("边不存在")
        return mutate(s, a, edit)
    if a.cmd == "branch":
        if a.op == "list":
            return s.rows("branches")
        return mutate(s, a, lambda: {"id": s.add_branch(a.title, a.parent)} if a.op == "add" else s.add_member(a.branch, a.node))
    if a.cmd == "transition":
        return mutate(s, a, lambda: s.transition(a.id, a.state, a.reason, a.evidence, a.revival))
    if a.cmd == "db":
        if a.op == "schema":
            return s.query("SELECT name,sql FROM sqlite_master WHERE type='table'")
        if a.op == "query":
            return s.query(a.sql, json.loads(a.params))
        if a.op == "repair":
            return mutate(s, a, lambda: None, check=False)
        if a.op == "backup":
            path = Path(a.path).resolve()
            if path.exists():
                raise ResearchError("备份目标已存在；不会覆盖")
            destination = sqlite3.connect(str(path))
            try:
                s.db.backup(destination)
            finally:
                destination.close()
            return {"backup": str(path), "note": "完整恢复还需 .research/artifacts 附件"}
    if a.cmd == "search":
        result = literature.Router(s, a.offline).search(a.query, a.provider, a.limit)
        if a.import_results:
            result["imported"] = mutate(s, a, lambda: [literature.import_paper(s, p, a.branch) for p in result["papers"]])
        return result
    if a.cmd == "paper":
        if a.op == "find":
            doc = reading.document(s, a.id)
            if not a.query.strip():
                raise ResearchError("查询不能为空")
            return {"document_sha256": doc["sha256"], "matches": [p for p in doc["pages"] if a.query.casefold() in p["text"].casefold()]}
        if a.op == "import":
            return mutate(s, a, lambda: {"id": literature.import_paper(s, load(a.path), a.branch)})
        if a.op == "attach":
            return mutate(s, a, lambda: reading.attach(s, a.id, a.path))
        if a.op == "expand":
            if not 1 <= a.limit <= 100:
                raise ResearchError("limit 须在 1..100")
            result = literature.Router(s, a.offline).expand(s.get(a.id), a.direction, a.limit)
            if a.import_results:
                def imp():
                    ids = [literature.import_paper(s, p) for p in result["papers"]]
                    for ident in ids:
                        if ident != a.id:
                            s.add_edge(a.id if a.direction == "references" else ident, "cites", ident if a.direction == "references" else a.id)
                    return ids
                result["imported"] = mutate(s, a, imp)
            return result
        if a.op == "export":
            papers = []
            for n in s.rows("nodes"):
                if n["kind"] != "P":
                    continue
                bib = n["data"].get("bibliography", {})
                row = {"id": n["id"], "type": "article-journal", "title": n["title"], "author": [{"literal": name} for name in bib.get("authors", [])]}
                if bib.get("doi"):
                    row["DOI"] = literature.clean_doi(bib["doi"])
                if bib.get("year"):
                    row["issued"] = {"date-parts": [[bib["year"]]]}
                if bib.get("url"):
                    row["URL"] = bib["url"]
                papers.append(row)
            return papers
    if a.cmd == "reading":
        if a.op == "queue":
            return reading.queue(s)
        if a.op == "triage":
            return mutate(s, a, lambda: reading.triage(s, a.id, a.verdict, a.reason, a.basis))
        if a.op == "packet":
            return reading.packet(s, a.id)
        if a.op == "report":
            return reading.report(s, a.id)
        if a.op == "add":
            return mutate(s, a, lambda: reading.annotate(s, a.id, load(a.path)))
        if a.op == "review":
            return mutate(s, a, lambda: reading.review(s, a.id, a.verdict, a.reason))
        if a.op == "complete":
            def complete():
                report = reading.report(s, a.id)
                if not report["complete"]:
                    raise ResearchError("尚缺已审阅条目: " + ", ".join(report["missing_sections"]))
                s.update_data(a.id, {"reading_status": "complete"})
                return report
            return mutate(s, a, complete)
    if a.cmd == "experiment":
        if a.op == "validate":
            errors = experiments.validate(load(a.spec))
            if errors:
                raise ResearchError("; ".join(errors))
            return {"ok": True}
        if a.op == "plan":
            return mutate(s, a, lambda: {"id": experiments.plan(s, a.hypothesis, load(a.spec))})
        return mutate(s, a, lambda: {"id": experiments.ingest(s, a.id, a.metrics, a.config, a.log, a.repo, a.commit, a.seeds)})
    if a.cmd == "failure":
        if a.op == "show":
            return s.get(a.id)
        return mutate(s, a, lambda: {"id": experiments.fail(s, a.source, a.reason, a.evidence, a.do_not_repeat, a.revival)})
    if a.cmd == "artifact":
        def add():
            ident = s.add_node("A", a.title, {"artifacts": [s.artifact(a.path)]}, a.branch)
            if a.source:
                s.add_edge(a.source, "produces", ident)
            return {"id": ident}
        return mutate(s, a, add)
    if a.cmd == "project":
        return safe_render(s)
    raise ResearchError("未实现的命令")


def main(argv=None):
    args = parser().parse_args(argv)
    def record(result=None, failed=False):
        from .activity import operation
        try:
            operation(root_path(args.project), args, result, failed)
        except Exception:
            print("工作过程记录未保存；命令的研究结果不受影响。", file=sys.stderr)
    try:
        result = run(args)
        record(result)
        print(dumps(result), end="")
    except (ResearchError, OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        record(failed=True)
        print(dumps({"error": str(exc)}), file=sys.stderr, end="")
        raise SystemExit(2)
