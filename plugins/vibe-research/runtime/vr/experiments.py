import json
import math
import subprocess
from pathlib import Path
from .store import ResearchError


def validate(spec):
    if not isinstance(spec, dict):
        return ["实验规范必须是 JSON 对象"]
    errors = []
    required = {"command", "repo", "config", "seeds", "metrics", "baselines", "held_out_opponents", "cross_play", "population_size", "compute_budget", "fairness", "exploitability"}
    for key in sorted(required - set(spec)):
        errors.append("缺少 " + key)
    seeds = spec.get("seeds", [])
    if not isinstance(seeds, list) or len(seeds) < 2 or any(type(x) is not int for x in seeds) or len(set(str(x) for x in seeds)) != len(seeds):
        errors.append("seeds 需要至少两个不同整数")
    for key in required - {"seeds", "cross_play", "population_size"}:
        if key in spec and not spec[key]:
            errors.append(key + " 不能为空")
    if "cross_play" in spec and (not isinstance(spec["cross_play"], (str, dict)) or not spec["cross_play"]):
        errors.append("cross_play 需描述评估方法或不适用理由，不能只写布尔值")
    if not isinstance(spec.get("metrics", []), list) or not all(isinstance(x, str) for x in spec.get("metrics", [])):
        errors.append("metrics 需要指标名称列表")
    if "population_size" in spec and (type(spec["population_size"]) is not int or spec["population_size"] < 1):
        errors.append("population_size 应为正整数")
    return errors


def plan(store, hypothesis, spec):
    if store.get(hypothesis)["kind"] != "H":
        raise ResearchError("experiment plan 需要 H 节点")
    errors = validate(spec)
    if errors:
        raise ResearchError("MARL 实验规范未通过: " + "; ".join(errors))
    ident = store.add_node("X", spec.get("title", "Test " + hypothesis), {"hypothesis": hypothesis, "spec": spec})
    store.add_edge(hypothesis, "tested_by", ident)
    return ident


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ResearchError("无法读取实验 Git 信息（需要至少一个 commit）")
    return result.stdout.strip()


def ingest(store, experiment, metrics_path, config_path, log_path, repo, commit, seeds):
    item = store.get(experiment)
    if item["kind"] != "X":
        raise ResearchError("ingest 需要 X 节点")
    spec = item["data"].get("spec")
    if not spec:
        raise ResearchError("实验没有规范；请用 experiment plan 创建")
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdefABCDEF" for c in commit):
        raise ResearchError("--commit 必须是执行实验时记录的完整 Git SHA")
    resolved = git(repo, "rev-parse", "--verify", commit + "^{commit}")
    if sorted(seeds) != sorted(spec["seeds"]):
        raise ResearchError("实际 seeds 与实验规范不一致；请创建新实验规范")
    metrics = json.loads(Path(metrics_path).read_text())
    if not isinstance(metrics, dict) or not metrics:
        raise ResearchError("metrics 必须是非空 JSON 对象")
    for key in spec["metrics"]:
        values = metrics.get(key)
        if not isinstance(values, dict) or set(values) != set(map(str, seeds)):
            raise ResearchError("每个指标必须按 seed 提供值，例如 {win_rate: {1: 0.5, 2: 0.6}}: " + key)
        if any(type(v) not in {int, float} or not math.isfinite(v) for v in values.values()):
            raise ResearchError("指标包含非有限数值")
    artifacts = [store.artifact(p) for p in [metrics_path, config_path, log_path]]
    result = store.add_node("R", "Result of " + experiment, {"experiment": experiment, "metrics": metrics,
                            "seeds": seeds, "git_commit": resolved, "repo": str(Path(repo).resolve()),
                            "working_tree_dirty_at_ingest": bool(git(repo, "status", "--porcelain")),
                            "provenance_note": "commit 为调用者声明的运行版本，ingest 不证明命令实际执行；dirty 状态只记录导入时刻。",
                            "artifacts": artifacts})
    store.add_edge(experiment, "produces", result)
    return result


def fail(store, source, reason, evidence, do_not_repeat, revival):
    if not all([reason.strip(), evidence, do_not_repeat.strip(), revival.strip()]):
        raise ResearchError("失败需 reason/evidence/do-not-repeat/revival")
    store.get(evidence)
    failure = store.add_node("F", reason, {"source": source, "evidence": evidence, "do_not_repeat": do_not_repeat, "revival_condition": revival})
    store.add_edge(source, "fails_as", failure)
    return failure
