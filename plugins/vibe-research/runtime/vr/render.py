"""Obsidian projections: editable research state lives only in the CLI."""
import json
from collections import defaultdict
from .store import atomic, dumps

FOLDERS = {"P": "Papers", "G": "Gaps", "H": "Hypotheses", "X": "Experiments", "R": "Results", "F": "Failures", "D": "Decisions", "V": "Evidence", "A": "Artifacts"}


def render(store):
    nodes, edges, branches = store.rows("nodes"), store.rows("edges"), store.rows("branches")
    root = store.root / "research"
    root.mkdir(exist_ok=True)
    paths = {n["id"]: FOLDERS.get(n["kind"], "Notes") + "/" + n["id"] + ".md" for n in nodes}
    def link(ident):
        return "[[" + paths[ident][:-3] + "|" + ident + "]]"
    for node in nodes:
        ident = node["id"]
        trace = store.trace(ident)
        lines = ["# " + ident + " · " + node["title"], "", "> 由 vr 生成；修改请使用 CLI。", "", "状态：" + node["status"], "",
                 "研究分支：" + ", ".join(trace["branches"]), "", "## 前置路线", "", ", ".join(link(x) for x in trace["ancestors"]) or "无", "", "## 后续路线", "", ", ".join(link(x) for x in trace["descendants"]) or "无", "", "## 有向关系", ""]
        for edge in trace["relations"]:
            lines.append("- " + link(edge["source"]) + " → " + edge["relation"] + " → " + link(edge["target"]) + " (" + edge["layer"] + ")")
        lines += ["", "## 跨文献关联路线", "", "上游：" + (", ".join(link(x) for x in trace["related_upstream"]) or "无"), "", "下游：" + (", ".join(link(x) for x in trace["related_downstream"]) or "无"), "", "## 数据与证据", "", "```json", dumps(node["data"]).rstrip(), "```", ""]
        for art in node["data"].get("artifacts", []):
            # Notes are two levels below project root.
            lines.append("[附件：" + art["name"].replace("]", "") + "](../../" + art["path"] + ")")
        atomic(root / paths[ident], "\n".join(lines) + "\n")
    levels = {n["id"]: 0 for n in nodes}
    for _ in nodes:
        changed = False
        for e in edges:
            if e["layer"] == "process" and levels[e["target"]] <= levels[e["source"]]:
                levels[e["target"]] = levels[e["source"]] + 1
                changed = True
        if not changed:
            break
    lanes = defaultdict(int)
    canvas = {"nodes": [], "edges": []}
    colors = {"rejected": "1", "pruned": "1", "failed": "1", "supported": "4", "active": "5"}
    for n in nodes:
        level = levels[n["id"]]
        canvas["nodes"].append({"id": n["id"], "type": "file", "file": paths[n["id"]], "x": level * 440, "y": lanes[level] * 280, "width": 360, "height": 220, "color": colors.get(n["status"], "3")})
        lanes[level] += 1
    for i, e in enumerate(edges):
        canvas["edges"].append({"id": "e" + str(i), "fromNode": e["source"], "fromSide": "right", "toNode": e["target"], "toSide": "left", "toEnd": "arrow", "label": e["relation"], "color": "5" if e["layer"] == "semantic" else "3"})
    atomic(root / "research.canvas", dumps(canvas))
    question = store.db.execute("SELECT value FROM meta WHERE key='question'").fetchone()[0]
    lines = ["# Vibe Research", "", question, "", "Revision: " + str(store.revision()), "", "[Wiki 关系图](graph.html) · [[Progress|研究进展]] · [[Integrations|工具接入检查]] · [[research.canvas|打开研究有向图]]", "", "## 研究路线", ""]
    for b in branches:
        members = [m["node"] for m in store.rows("members") if m["branch"] == b["id"]]
        lines += ["- **" + b["id"] + " " + b["title"] + "** · " + b["status"] + " · " + ", ".join(link(x) for x in members)]
    lines += ["", "## 当前节点", ""]
    for n in nodes:
        lines += ["- " + link(n["id"]) + " " + n["title"] + " · " + n["status"]]
    lines += ["", "## 下一步", ""]
    for n in nodes:
        if n["kind"] == "P" and n["data"].get("reading_status") != "complete":
            lines.append("- " + link(n["id"]) + "：补全文/精读证据并审阅")
        if n["kind"] == "H" and n["status"] in {"draft", "active"} and not any(e["source"] == n["id"] and e["relation"] == "tested_by" for e in edges):
            lines.append("- " + link(n["id"]) + "：建立可复现实验规范")
    atomic(root / "Home.md", "\n".join(lines) + "\n")
    from .progress import publish
    publish(store)
    from .graph import publish as publish_graph
    publish_graph(store)
    return {"home": str(root / "Home.md"), "canvas": str(root / "research.canvas"), "nodes": len(nodes)}


def gaps(store):
    nodes, edges = store.rows("nodes"), store.rows("edges")
    return {"note": "结构性缺口清单，不代表领域新颖性已经验证。", "gaps": [
        {"gap": n, "evidence": [e for e in edges if e["target"] == n["id"]],
         "proposed_work": [e for e in edges if e["source"] == n["id"]]}
        for n in nodes if n["kind"] == "G"],
        "untested_hypotheses": [n["id"] for n in nodes if n["kind"] == "H" and not any(e["source"] == n["id"] and e["relation"] == "tested_by" for e in edges)],
        "claims_without_evidence": [n["id"] for n in nodes if n["kind"] == "C" and not any(e["target"] == n["id"] and e["relation"] in {"supports", "contradicts"} for e in edges)]}
