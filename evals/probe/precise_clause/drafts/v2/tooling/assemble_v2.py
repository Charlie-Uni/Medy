# -*- coding: utf-8 -*-
"""Assemble probe v2 (spec-v1.1): the 75 frozen v1 samples plus the 32 English twins, all re-reviewed by one
pinned LLM second reviewer (claude-opus-5 via Claude Code CLI), into a draft version directory.

    python evals/probe/precise_clause/drafts/v2/tooling/assemble_v2.py --out evals/probe/precise_clause/v2 \
        [--human-confirmed YYYY-MM-DD] [--created-at YYYY-MM-DD]

Inputs: v1/samples.jsonl, drafts/v2/samples_draft_EN.json, drafts/v2/review/{run,verdicts}_{MA,PV,CO,EN}.*,
drafts/v2/review/resolutions.json (human adjudications of disputes; a disputed sample without one refuses the
assembly). Output: <out>/samples.jsonl, manifest.json (status=draft, dataset_hash=null), corpus.json and
review_prompt.md copied byte-identical from v1, pii_exceptions.json re-versioned, review_evidence/ with the ten
hashed artifacts. Refuses to write into an existing frozen directory. Freezing is a separate step.
"""

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import shutil
import sys
from collections import Counter

from medops.core.canonical import canonical_json

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("v2_codex_tooling", HERE / "run_codex_review.py")
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)

REPO = codex.REPO
V1 = REPO / "evals/probe/precise_clause/v1"
DRAFTS = REPO / "evals/probe/precise_clause/drafts/v2"
REVIEW = DRAFTS / "review"
BATCHES = ("MA", "PV", "CO", "EN")
SLICES = ["drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en"]
DEPTS = ["MA", "PV", "CO"]
LANGS = ["zh-Hans", "zh-Hant", "en", "mixed"]
ANNOTATOR = {"id": "annotator-01", "kind": "human"}
REVIEWER_ID = "reviewer-llm-02"
LIMITATION = (
    "复核通过 Claude Code CLI 以固定模型标识 claude-opus-5 调用，标识由 CLI 在 modelUsage 中回显；"
    "工具关闭、会话不持久化、不加载用户设置、固定中性系统提示（哈希已记录）；reasoning effort 为请求参数，CLI 不回显。"
    "同一标识不保证服务端权重永不变化；复核输入与实际提示的哈希已逐条绑定，可据此复核一致性。"
)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_runs() -> tuple[dict[str, dict], dict[str, dict], dict[str, bytes]]:
    runs, verdicts, evidence = {}, {}, {}
    for batch in BATCHES:
        run_path, v_path = REVIEW / f"run_{batch}.json", REVIEW / f"verdicts_{batch}.jsonl"
        if not run_path.exists() or not v_path.exists():
            raise SystemExit(f"{batch}: review run or verdicts missing")
        run = json.loads(run_path.read_text(encoding="utf-8"))
        if run.get("active_review"):
            raise SystemExit(f"{batch}: review unfinished (pending {run['active_review']['pending_ids'][:5]}...)")
        runs[batch] = run
        current = codex.current_verdicts(run)
        mirrored = {v["sample_id"]: v for v in codex.load_records(v_path)}
        if mirrored != current:
            raise SystemExit(f"{batch}: verdict mirror differs from run record")
        verdicts.update(current)
        evidence[f"run_{batch}.json"] = run_path.read_bytes()
        evidence[f"verdicts_{batch}.jsonl"] = v_path.read_bytes()
    return runs, verdicts, evidence


def review_block(sid: str, verdict: dict, resolutions: dict, model: str, prompt_hash: str) -> dict:
    second = {"id": REVIEWER_ID, "kind": "llm", "model": model, "model_version": model, "prompt_hash": prompt_hash}
    if verdict["verdict"] == "agree":
        return {"annotator": ANNOTATOR, "second_reviewer": second, "status": "agreed", "resolution_note": None}
    res = resolutions.get(sid)
    if not res:
        raise SystemExit(f"{sid}: disputed by the reviewer and no human resolution recorded (reason: {verdict['reason'][:160]})")
    if res.get("accepted"):
        raise SystemExit(f"{sid}: accepted dispute must be re-reviewed until the reviewer agrees before assembly")
    expected_scope = {k for k, v in verdict["items"].items() if v == "issue"}
    if set(res.get("issue_scope", [])) != expected_scope or res.get("verdict_sha256") != codex.record_hash(verdict):
        raise SystemExit(f"{sid}: resolution is stale (verdict or issue scope changed)")
    note = str(res.get("resolution_note", "")).strip()
    if len(note) < 5:
        raise SystemExit(f"{sid}: resolution_note too short")
    return {"annotator": ANNOTATOR, "second_reviewer": second, "status": "disputed_resolved", "resolution_note": note}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--human-confirmed", default=None, help="date annotator-01 confirmed the 32 English twins")
    ap.add_argument("--created-at", default=dt.date.today().isoformat())
    args = ap.parse_args()
    out = args.out
    if (out / "SHA256SUMS").exists():
        raise SystemExit("refusing to write into a frozen version directory")
    if (out / "manifest.json").exists() and json.loads((out / "manifest.json").read_text(encoding="utf-8")).get("status") != "draft":
        raise SystemExit("refusing to overwrite a non-draft manifest")

    v1_manifest = json.loads((V1 / "manifest.json").read_text(encoding="utf-8"))
    v1_samples = [json.loads(l) for l in (V1 / "samples.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    twins = json.loads((DRAFTS / "samples_draft_EN.json").read_text(encoding="utf-8"))
    corpus = json.loads((V1 / "corpus.json").read_text(encoding="utf-8"))
    docs = {d["source_hash"]: d for d in corpus["documents"]}
    prompt_raw = (V1 / "review_prompt.md").read_bytes()
    prompt_hash = sha(prompt_raw)
    runs, verdicts, evidence = load_runs()
    models = {run["model"] for run in runs.values()}
    efforts = {run["reasoning_effort_requested"] for run in runs.values()}
    if len(models) != 1 or len(efforts) != 1 or any(run["review_prompt_sha256"] != prompt_hash for run in runs.values()):
        raise SystemExit("all batches must share one model, one effort and the v2 review prompt hash")
    model, effort = models.pop(), efforts.pop()
    resolutions_path = REVIEW / "resolutions.json"
    resolutions = json.loads(resolutions_path.read_text(encoding="utf-8")) if resolutions_path.exists() else {}

    samples = []
    for s in v1_samples:
        base = {k: v for k, v in s.items() if k != "review"}
        base["review"] = review_block(s["sample_id"], verdicts[s["sample_id"]], resolutions, model, prompt_hash)
        samples.append(base)
    for t in twins:
        base = dict(t)
        base["review"] = review_block(t["sample_id"], verdicts[t["sample_id"]], resolutions, model, prompt_hash)
        samples.append(base)
    samples.sort(key=lambda s: s["sample_id"])
    if set(verdicts) != {s["sample_id"] for s in samples}:
        raise SystemExit("verdict coverage differs from the assembled sample set")
    disputed = {s["sample_id"] for s in samples if s["review"]["status"] == "disputed_resolved"}
    if set(resolutions) != disputed:
        raise SystemExit(f"resolutions must cover exactly the disputed samples (extra: {sorted(set(resolutions) - disputed)[:5]})")

    def language_of(s):
        langs = {docs[g["source_hash"]]["language"] for g in s["required_gold_evidence"]}
        return langs.pop() if len(langs) == 1 else "mixed"

    counts = {
        "samples": len(samples),
        "documents": len(docs),
        "per_slice": {k: Counter(sl for s in samples for sl in s["slices"]).get(k, 0) for k in SLICES},
        "per_dept": {k: Counter(s["dept"] for s in samples).get(k, 0) for k in DEPTS},
        "per_language": {k: Counter(language_of(s) for s in samples).get(k, 0) for k in LANGS},
    }
    chunks = [c for run in runs.values() for c in run["chunks"]]
    runtime = {
        "model": model,
        "model_version_source": "pinned_model_id",
        "backend_model_version": model,
        "backend_model_version_status": "pinned model identifier echoed by the Claude Code CLI (modelUsage); CLI version recorded separately",
        "cli": "claude-code",
        "cli_versions": sorted({c["cli_version"] for c in chunks}),
        "system_prompt_sha256": sorted({c["system_prompt_sha256"] for c in chunks}),
        "reasoning_effort": effort,
        "first_started_at": min(c["started_at"] for c in chunks),
        "last_finished_at": max(c["finished_at"] for c in chunks),
        "observed_successful_calls": len(chunks),
        "current_reviewed_samples": len(samples),
        "total_cost_usd": round(sum(float(c.get("cost_usd") or 0) for c in chunks), 4),
        "reproducibility_limitations": LIMITATION,
    }
    evidence["resolutions.json"] = (canonical_json(resolutions) + "\n").encode("utf-8")
    evidence["reviewer_runtime_metadata.json"] = (canonical_json(runtime) + "\n").encode("utf-8")

    out.mkdir(parents=True, exist_ok=True)
    (out / "review_evidence").mkdir(exist_ok=True)
    for name, data in evidence.items():
        (out / "review_evidence" / name).write_bytes(data)
    shutil.copyfile(V1 / "corpus.json", out / "corpus.json")
    (out / "review_prompt.md").write_bytes(prompt_raw)
    pii = json.loads((V1 / "pii_exceptions.json").read_text(encoding="utf-8"))
    pii["dataset_version"] = "v2"
    (out / "pii_exceptions.json").write_text(canonical_json(pii) + "\n", encoding="utf-8")
    (out / "samples.jsonl").write_text("".join(canonical_json(s) + "\n" for s in samples), encoding="utf-8")
    files = ["corpus.json", "pii_exceptions.json", "review_prompt.md", "samples.jsonl"]
    manifest = {
        "dataset_id": v1_manifest["dataset_id"],
        "dataset_version": "v2",
        "spec_version": "spec-v1.1",
        "status": "draft",
        "created_at": args.created_at,
        "frozen_at": None,
        "purpose": "精确条款探针集 v2：v1 的 75 条冻结样本原样保留，另为 32 条英文 gold 样本派生英文查询孪生（spec-v1.1），全部 107 条由同一固定模型 LLM 第二复核人重新复核；用于 ADR-0002 修订 1 的语言一致门禁与跨语言切片分报。",
        "source_store": v1_manifest["source_store"],
        "extraction": v1_manifest["extraction"],
        "normalization": v1_manifest["normalization"],
        "minimums": v1_manifest["minimums"],
        "counts": counts,
        "reviewers": [
            {**ANNOTATOR, "role": "annotator"},
            {"id": REVIEWER_ID, "kind": "llm", "model": model, "model_version": model, "prompt_hash": prompt_hash, "role": "second_reviewer"},
        ],
        "review_policy": {"human_reviewers": 1, "llm_reviewers": 1, "statement": "人工标注加 LLM 独立复核；不等同于两名独立人工复核。"},
        "review_provenance": {
            "reviewer_id": REVIEWER_ID,
            "version_source": "pinned_model_id",
            "backend_model_version": model,
            "reasoning_effort": effort,
            "reproducibility_limitations": LIMITATION,
            "artifacts": [{"path": f"review_evidence/{n}", "sha256": sha(d)} for n, d in sorted(evidence.items())],
        },
        "derived_samples": {
            "rule": "32 English query twins of the v1 samples whose gold document is English; gold, dept and slices inherited unchanged; language=en (SPEC 5.1)",
            "count": len(twins),
            "query_language": "en",
            "drafted_by": {"kind": "llm", "id": "drafter-llm-01", "model": "claude-fable-5-1"},
            "human_confirmation": {
                "status": "confirmed" if args.human_confirmed else "pending",
                "annotator_id": "annotator-01",
                "confirmed_on": args.human_confirmed,
            },
        },
        "pii_ruleset_version": v1_manifest["pii_ruleset_version"],
        "files": [{"path": n, "sha256": sha((out / n).read_bytes())} for n in files],
        "dataset_hash": None,
        "supersedes": "v1",
        "change_reason": "ADR-0002 修订 1（2026-09-20）：门禁改按语言一致子集计算；为英文 gold 样本派生英文查询孪生；第二复核人改为固定模型 claude-opus-5 并对全部样本重新复核（决策人方案 2）。",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"assembled {len(samples)} samples ({len(disputed)} disputed_resolved) -> {out}; counts {counts['per_dept']} {counts['per_language']}")


if __name__ == "__main__":
    main()
