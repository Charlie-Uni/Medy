"""Assemble the main evaluation set (spec-m1) into a draft version directory (SPEC §4 step 6, before freezing).

    python evals/main_set/tools/assemble.py --out evals/main_set/main-v1-provisional [--created-at YYYY-MM-DD]

Inputs: the frozen probe v2 (imported verbatim: samples, PII exceptions, extraction record), the confirmed main-set
drafts drafts/main-v1/samples_draft_{MA,PV,CO,EN,NA}.json, the LLM review runs/verdicts for those five batches,
review/resolutions.json (human adjudications of disputes), evals/main_set/corpus.json, drafts/main-v1/review_prompt.md
and conflict_fixtures/fixtures.json. Output: <out>/{corpus.json, samples.jsonl, review_prompt.md, pii_exceptions.json,
manifest.json (status=draft), review_evidence/*}. Refuses to write into a frozen directory; freezing is freeze.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

from medops.core.canonical import canonical_json  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "v2_codex_tooling", dc.REPO / "evals/probe/precise_clause/drafts/v2/tooling/run_codex_review.py"
)
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)

PROBE_V2 = dc.REPO / "evals/probe/precise_clause/v2"
REVIEW = dc.DRAFTS / "review"
BATCHES = ("MA", "PV", "CO", "EN", "NA")
SLICES = [
    "drug_name_zh",
    "dose_unit",
    "negation",
    "time_window",
    "protocol_id",
    "mixed_zh_en",
    "version_conflict",
    "no_answer",
    "long_context",
]
DEPTS = ["MA", "PV", "CO"]
LANGS = ["zh-Hans", "zh-Hant", "en", "mixed"]
ANNOTATOR = {"id": "annotator-01", "kind": "human"}
REVIEWER_ID = "reviewer-llm-02"
DATASET_VERSION = "main-v1-provisional"
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
            raise SystemExit(f"{batch}: review unfinished")
        current = codex.current_verdicts(run)
        mirror = {v["sample_id"]: v for v in codex.load_records(v_path)}
        if mirror != current:
            raise SystemExit(f"{batch}: verdicts file differs from the run record")
        runs[batch] = run
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
        raise SystemExit(f"{sid}: disputed and no human resolution recorded (reason: {verdict['reason'][:160]})")
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
    ap.add_argument("--created-at", default=dt.date.today().isoformat())
    ap.add_argument(
        "--human-confirmed", required=True, help="date annotator-01 confirmed the draft sheets (all batches)"
    )
    args = ap.parse_args()
    out = args.out
    if (out / "SHA256SUMS").exists():
        raise SystemExit("refusing to write into a frozen version directory")
    if (out / "manifest.json").exists() and json.loads((out / "manifest.json").read_text(encoding="utf-8")).get(
        "status"
    ) != "draft":
        raise SystemExit("refusing to overwrite a non-draft manifest")

    probe_manifest = json.loads((PROBE_V2 / "manifest.json").read_text(encoding="utf-8"))
    if probe_manifest.get("status") != "frozen":
        raise SystemExit("probe v2 is not frozen")
    probe_raw = (PROBE_V2 / "samples.jsonl").read_bytes()
    imported = [json.loads(line) for line in probe_raw.decode("utf-8").splitlines() if line.strip()]
    corpus = json.loads(dc.CORPUS.read_text(encoding="utf-8"))
    if corpus["dataset_version"] != DATASET_VERSION:
        raise SystemExit("corpus dataset_version differs from the assembled version")
    docs = {d["source_hash"]: d for d in corpus["documents"]}
    by_key = {d["document_key"]: d for d in corpus["documents"]}
    prompt_raw = (dc.DRAFTS / "review_prompt.md").read_bytes()
    prompt_hash = sha(prompt_raw)
    runs, verdicts, evidence = load_runs()
    models = {run["model"] for run in runs.values()}
    efforts = {run["reasoning_effort_requested"] for run in runs.values()}
    if (
        len(models) != 1
        or len(efforts) != 1
        or any(run["review_prompt_sha256"] != prompt_hash for run in runs.values())
    ):
        raise SystemExit("all batches must share one model, one effort and the main-set review prompt hash")
    model, effort = models.pop(), efforts.pop()
    resolutions_path = REVIEW / "resolutions.json"
    resolutions = json.loads(resolutions_path.read_text(encoding="utf-8")) if resolutions_path.exists() else {}

    new_samples = []
    for batch in BATCHES:
        for s in json.loads((dc.DRAFTS / f"samples_draft_{batch}.json").read_text(encoding="utf-8")):
            base = {k: v for k, v in s.items() if k not in ("review", "_draft")}
            base["review"] = review_block(s["sample_id"], verdicts[s["sample_id"]], resolutions, model, prompt_hash)
            new_samples.append(base)
    dropped_path = REVIEW / "dropped_after_review.json"
    dropped_after = json.loads(dropped_path.read_text(encoding="utf-8")) if dropped_path.exists() else {}
    if set(dropped_after) & {s["sample_id"] for s in new_samples}:
        raise SystemExit("dropped_after_review lists a sample that is still in the drafts")
    if set(verdicts) - set(dropped_after) != {s["sample_id"] for s in new_samples}:
        raise SystemExit("verdict coverage differs from the assembled new samples")
    disputed = {s["sample_id"] for s in new_samples if s["review"]["status"] == "disputed_resolved"}
    resolutions = {k: v for k, v in resolutions.items() if k not in dropped_after}
    if set(resolutions) != disputed:
        raise SystemExit(
            f"resolutions must cover exactly the disputed samples (extra: {sorted(set(resolutions) - disputed)[:5]})"
        )
    samples = sorted(imported + new_samples, key=lambda s: s["sample_id"])

    def language_of(s: dict) -> str:
        if not s["required_gold_evidence"]:
            return by_key[s["abstention"]["scope_document_key"]]["language"]
        langs = {docs[g["source_hash"]]["language"] for g in s["required_gold_evidence"]}
        return langs.pop() if len(langs) == 1 else "mixed"

    derived = [s for s in samples if s.get("derived_from")]
    counts = {
        "samples": len(samples),
        "answerable": sum(s.get("answerable", True) is not False for s in samples),
        "no_answer": sum(s.get("answerable", True) is False for s in samples),
        "conflict": sum("version_conflict" in s["slices"] for s in samples),
        "derived": len(derived),
        "imported": len(imported),
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
        "current_reviewed_samples": len(new_samples),
        "imported_samples_not_rereviewed": len(imported),
        "total_cost_usd": round(sum(float(c.get("cost_usd") or 0) for c in chunks), 4),
        "reproducibility_limitations": LIMITATION,
    }
    evidence["resolutions.json"] = (canonical_json(resolutions) + "\n").encode("utf-8")
    evidence["reviewer_runtime_metadata.json"] = (canonical_json(runtime) + "\n").encode("utf-8")

    out.mkdir(parents=True, exist_ok=True)
    (out / "review_evidence").mkdir(exist_ok=True)
    for name, data in evidence.items():
        (out / "review_evidence" / name).write_bytes(data)
    (out / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "review_prompt.md").write_bytes(prompt_raw)
    pii = json.loads((PROBE_V2 / "pii_exceptions.json").read_text(encoding="utf-8"))
    pii["dataset_version"] = DATASET_VERSION
    extra_path = dc.DRAFTS / "pii_exceptions_new.json"
    if extra_path.exists():  # reviewed exceptions for new samples (same record shape; approval record in docs/reviews)
        pii["exceptions"] += json.loads(extra_path.read_text(encoding="utf-8"))["exceptions"]
    pii["exceptions"] = sorted(pii["exceptions"], key=lambda e: (e["sample_id"], e["gold_id"], e["char_start"]))
    (out / "pii_exceptions.json").write_text(canonical_json(pii) + "\n", encoding="utf-8")
    (out / "samples.jsonl").write_text("".join(canonical_json(s) + "\n" for s in samples), encoding="utf-8")
    fixtures = json.loads((dc.MAIN / "conflict_fixtures/fixtures.json").read_text(encoding="utf-8"))["fixtures"]
    files = ["corpus.json", "pii_exceptions.json", "review_prompt.md", "samples.jsonl"]
    manifest = {
        "dataset_id": "precise_clause_main",
        "dataset_version": DATASET_VERSION,
        "spec_version": "spec-m1",
        "status": "draft",
        "created_at": args.created_at,
        "frozen_at": None,
        "purpose": (
            "主评测集 main-v1（临时版）：并入探针 v2 全部 107 条样本，另按 spec-m1 新增有答案样本（含英文孪生、合成版本冲突样本、长条款样本）"
            "与无答案样本；用于基线 M1-21 端到端门禁（Recall@5 ≥ 85%、失效版本引用率 0、abstention accuracy ≥ 90%）。第二人工复核未完成，故为 provisional。"
        ),
        "source_store": {
            "kind": "local_path",
            "location": "main_set/sources_staging 与 probe/precise_clause/v1/sources（本地目录，不进入 Git；完整性由 corpus.json 的 source_hash 校验）",
        },
        "extraction": probe_manifest["extraction"],
        "normalization": probe_manifest["normalization"],
        "minimums": {
            "answerable_samples": 300,
            "no_answer_samples": 40,
            "conflict_samples": 20,
            "per_slice": 20,
            "per_dept": 60,
            "max_samples_per_document": 8,
            "documents": 10,
            "documents_per_dept": 3,
            "zh_hans_samples": 20,
            "zh_hant_samples": 80,
            "en_samples": 150,
        },
        "gates": {
            "recall_at_5": 0.85,
            "abstention_accuracy": 0.9,
            "invalid_version_citation_rate": 0.0,
            "conflict_current_cited_rate": 1.0,
        },
        "counts": counts,
        "reviewers": [
            {**ANNOTATOR, "role": "annotator"},
            {
                "id": REVIEWER_ID,
                "kind": "llm",
                "model": model,
                "model_version": model,
                "prompt_hash": prompt_hash,
                "role": "second_reviewer",
            },
        ],
        "review_policy": {
            "human_reviewers": 1,
            "llm_reviewers": 1,
            "statement": "人工标注加 LLM 独立复核；不等同于两名独立人工复核。",
        },
        "review_provenance": {
            "reviewer_id": REVIEWER_ID,
            "version_source": "pinned_model_id",
            "backend_model_version": model,
            "reasoning_effort": effort,
            "reproducibility_limitations": LIMITATION,
            "artifacts": [
                {"path": f"review_evidence/{name}", "sha256": sha(data)} for name, data in sorted(evidence.items())
            ],
        },
        "pii_ruleset_version": probe_manifest["pii_ruleset_version"],
        "files": [{"path": name, "sha256": sha((out / name).read_bytes())} for name in files],
        "dataset_hash": None,
        "supersedes": None,
        "change_reason": None,
        "derived_samples": {
            "rule": (
                "English query twins of samples whose gold document is English: gold, dept and slices inherited unchanged, language=en "
                "(spec-v1.1 §5.1); the 32 probe v2 twins are imported as-is and the new twins were drafted by drafter-llm-03"
            ),
            "count": len(derived),
            "query_language": "en",
            "drafted_by": {"kind": "llm", "id": "drafter-llm-03", "model": "claude-sonnet-5"},
            "human_confirmation": {
                "status": "confirmed",
                "annotator_id": "annotator-01",
                "confirmed_on": args.human_confirmed,
            },
        },
        "imported_samples": {
            "dataset_id": probe_manifest["dataset_id"],
            "dataset_version": probe_manifest["dataset_version"],
            "dataset_hash": probe_manifest["dataset_hash"],
            "path": "evals/probe/precise_clause/v2/samples.jsonl",
            "samples_sha256": sha(probe_raw),
            "count": len(imported),
            "prompt_hash": next(
                r["prompt_hash"] for r in probe_manifest["reviewers"] if r["role"] == "second_reviewer"
            ),
            "reviewer_id": next(r["id"] for r in probe_manifest["reviewers"] if r["role"] == "second_reviewer"),
            "statement": "探针 v2 的 107 条样本原样并入（canonical 字节一致），保留其探针复核记录与提示哈希；报告中探针子集单列。",
        },
        "second_human_review": {
            "status": "pending",
            "reviewer_id": None,
            "statement": "决策人 2026-09-21 答复“第二人工复核人暂无”；基线 5.9 的第二人工复核未完成，本集只能以 provisional 运行，报告须标注。",
        },
        "dropped_after_review": dropped_after,
        "conflict_fixtures": [
            {
                "document_key": f["document_key"],
                "archived_document_keys": f.get("archived_document_keys", [f["synthetic_old_key"]]),
                "synthetic": f.get("synthetic", True),
                "source": f.get(
                    "source",
                    f"同一 PDF 以两个 document_key 入库；旧版 effective_from {f['effective_from_old']}，发布现行版（{f['effective_from_current']}）时归档（记录 50）",
                ),
            }
            for f in fixtures
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"assembled {len(samples)} samples ({len(imported)} imported, {len(new_samples)} new, {len(derived)} derived, {counts['no_answer']} no-answer, {counts['conflict']} conflict) -> {out}"
    )
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
