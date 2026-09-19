"""Assemble the confirmed drafts plus review verdicts into a draft version directory (SPEC sections 5, 7, 8).

    python evals/probe/precise_clause/drafts/v1/tooling/assemble.py --out evals/probe/precise_clause/v1 \
        --llm-model <model-id> [--llm-version <verified-runtime-description>] [--verdicts drafts/v1/review/verdicts_*.jsonl] \
        [--resolutions drafts/v1/review/resolutions.json] [--batches MA PV CO]

Writes <out>/samples.jsonl (one canonical JSON object per line, ordered by sample_id) and <out>/manifest.json
(status=draft, counts computed like the validator's PR-03, files with SHA-256 of corpus.json, samples.jsonl and
review_prompt.md, dataset_hash=null). Every sample needs a verdict: `agree` -> review.status=agreed;
`dispute` -> the annotator's entry in the resolutions file, either {"accepted": true} after the sample was
changed and re-reviewed, or {"resolution_note": "..."} -> disputed_resolved. Refuses to write into a frozen
directory (SHA256SUMS present or manifest.status != draft). Freezing (SHA256SUMS, dataset_hash, frozen_at)
is a separate, later step.
"""

import argparse
import datetime as dt
import glob
import hashlib
import json
import pathlib
import sys
from collections import Counter

from review_pack import pack_samples
from run_codex_review import record_hash, verify_review

from medops.core.canonical import canonical_json
from medops.evals.probe import extract

REPO = pathlib.Path(__file__).resolve().parents[6]
DRAFTS = REPO / "evals/probe/precise_clause/drafts/v1"
SLICES = ["drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en"]
DEPTS = ["MA", "PV", "CO"]
LANGS = ["zh-Hans", "zh-Hant", "en", "mixed"]
MINIMUMS = {
    "samples": 60,
    "target_samples": 72,
    "per_slice": 8,
    "per_dept": 15,
    "zh_hans_samples": 8,
    "documents": 10,
    "documents_per_dept": 3,
    "max_samples_per_document": 6,
}
ANNOTATOR = {"id": "annotator-01", "kind": "human", "role": "annotator"}


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verdicts(patterns: list[str]) -> dict[str, dict]:
    verdicts: dict[str, dict] = {}
    for pattern in patterns:
        for name in sorted(glob.glob(str(REPO / pattern))):
            for n, line in enumerate(pathlib.Path(name).read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                v = json.loads(line)
                if v["sample_id"] in verdicts:
                    sys.exit(f"duplicate verdict for {v['sample_id']} ({name}:{n})")
                if v["verdict"] not in ("agree", "dispute"):
                    sys.exit(f"bad verdict {v['verdict']!r} for {v['sample_id']} ({name}:{n})")
                verdicts[v["sample_id"]] = v
    return verdicts


def verify_batch_run(
    run: dict,
    records: list[dict],
    verdicts: dict[str, dict],
    prompt_hash: str,
    model: str,
    prompt_text: str | None = None,
    input_dir: pathlib.Path = DRAFTS / "review",
) -> None:
    """A completed high-effort review must bind to the exact current prompt and reviewed inputs."""
    if prompt_text is None:
        prompt_text = (REPO / "evals/probe/precise_clause/v1/review_prompt.md").read_bytes().decode("utf-8")
    if hashlib.sha256(prompt_text.encode("utf-8")).hexdigest() != prompt_hash:
        raise ValueError("review_prompt_sha256 does not match supplied prompt text")
    verify_review(run, records, verdicts, prompt_text, model, "high", input_dir=input_dir)


def verify_resolution(resolution: dict, record: dict, verdict: dict) -> None:
    if resolution.get("sample_input_sha256") != record_hash(record) or resolution.get("verdict_sha256") != record_hash(
        verdict
    ):
        raise ValueError("resolution must bind the exact current reviewed input and verdict")


def build_provenance(
    runs: dict[str, dict], evidence: dict[str, bytes], model: str, requested_version: str | None
) -> tuple[str, dict, dict[str, bytes]]:
    """Snapshot already verified review evidence and describe only the observed model identity.

    The current CLI records a service alias, not a backend snapshot. A caller cannot upgrade
    that evidence into a pinned model version by supplying an arbitrary CLI argument.
    """
    version = f"service-alias:{model};backend-version:not-exposed"
    if requested_version is not None and requested_version != version:
        raise ValueError("--llm-version is unsupported by the observed runs; backend version was not exposed")
    required = {f"{kind}_{batch}.{ext}" for batch in DEPTS for kind, ext in (("run", "json"), ("verdicts", "jsonl"))}
    required.add("resolutions.json")
    if set(runs) != set(DEPTS) or set(evidence) != required:
        raise ValueError("review provenance requires all three batches and the resolutions record")
    chunks = []
    for batch, run in runs.items():
        if json.loads(evidence[f"run_{batch}.json"]) != run:
            raise ValueError("review run changed while assembling its evidence")
        if run.get("model") != model or run.get("active_review") or not run.get("latest"):
            raise ValueError("review provenance requires complete runs for the requested model")
        if run.get("backend_model_version") is not None:
            raise ValueError("backend version metadata requires explicit verification support before use")
        chunks.extend(run["chunks"])
    if not chunks or any(
        c.get("model") != model
        or c.get("reasoning_effort") != "high"
        or c.get("returncode") != 0
        or not c.get("session_id")
        or not c.get("cli_version")
        or c.get("backend_model_version") is not None
        for c in chunks
    ):
        raise ValueError("review invocation metadata is incomplete or differs from the claimed runtime")
    limitation = (
        "已核验观察到的服务别名、调用参数及输入输出；后端模型版本未在运行元数据中暴露，"
        "此标识不代表固定模型快照，也不保证再次调用同一后端。CLI 版本单独记录。"
    )
    runtime = {
        "model_service_alias": model,
        "backend_model_version": None,
        "backend_model_version_status": "not exposed by observed CLI outputs; CLI version is not a model version",
        "cli_versions": sorted({c["cli_version"] for c in chunks}),
        "reasoning_effort": "high",
        "first_started_at": min(c["started_at"] for c in chunks),
        "last_finished_at": max(c["finished_at"] for c in chunks),
        "observed_successful_calls": len(chunks),
        "current_reviewed_samples": sum(len(run["latest"]) for run in runs.values()),
        "reproducibility_limitations": limitation,
    }
    snapshot = dict(evidence)
    snapshot["reviewer_runtime_metadata.json"] = (canonical_json(runtime) + "\n").encode("utf-8")
    provenance = {
        "reviewer_id": "reviewer-llm-01",
        "version_source": "service_alias",
        "backend_model_version": None,
        "reproducibility_limitations": limitation,
        "artifacts": [
            {"path": f"review_evidence/{name}", "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(snapshot.items())
        ],
    }
    return version, provenance, snapshot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--llm-model", required=True)
    ap.add_argument(
        "--llm-version", help="optional; must equal the version description derived from actual run evidence"
    )
    ap.add_argument("--verdicts", nargs="*", default=["evals/probe/precise_clause/drafts/v1/review/verdicts_*.jsonl"])
    ap.add_argument("--resolutions", default="evals/probe/precise_clause/drafts/v1/review/resolutions.json")
    ap.add_argument("--batches", nargs="*", default=DEPTS)
    ap.add_argument("--created-at", default=dt.date.today().isoformat())
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    if (out / "SHA256SUMS").exists():
        sys.exit(f"refused: {out} already has SHA256SUMS (frozen)")
    manifest_path = out / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")).get("status") != "draft":
        sys.exit(f"refused: {manifest_path} is not a draft")
    prompt_path = out / "review_prompt.md"
    corpus_path = out / "corpus.json"
    for p in (prompt_path, corpus_path):
        if not p.is_file():
            sys.exit(f"missing {p}")
    prompt_hash = sha256_file(prompt_path)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    docs = {d["source_hash"]: d for d in corpus["documents"]}

    verdicts = load_verdicts(args.verdicts)
    reviewed_records = {}
    samples_by_batch = {}
    runs, evidence = {}, {}
    for batch in args.batches:
        samples = json.loads((DRAFTS / f"samples_draft_{batch}.json").read_text(encoding="utf-8"))
        samples_by_batch[batch] = samples
        records = pack_samples(samples, docs, out / "pages")
        reviewed_records.update({r["sample_id"]: r for r in records})
        run_path = DRAFTS / "review" / f"run_{batch}.json"
        if not run_path.is_file():
            sys.exit(f"missing review provenance: {run_path}")
        run_bytes = run_path.read_bytes()
        run = json.loads(run_bytes)
        verdict_path = DRAFTS / "review" / f"verdicts_{batch}.jsonl"
        mirror_bytes = verdict_path.read_bytes()
        mirror_rows = [json.loads(line) for line in mirror_bytes.decode("utf-8").splitlines() if line.strip()]
        mirror = {v["sample_id"]: v for v in mirror_rows}
        if len(mirror) != len(mirror_rows) or mirror != {r["sample_id"]: verdicts.get(r["sample_id"]) for r in records}:
            sys.exit(f"{batch}: default verdict evidence differs from the verified input verdicts")
        try:
            verify_batch_run(
                run,
                records,
                verdicts,
                prompt_hash,
                args.llm_model,
                prompt_path.read_bytes().decode("utf-8"),
            )
        except ValueError as exc:
            sys.exit(f"{batch}: {exc}")
        runs[batch] = run
        evidence[run_path.name] = run_bytes
        evidence[verdict_path.name] = mirror_bytes
    res_path = REPO / args.resolutions
    resolution_bytes = res_path.read_bytes() if res_path.is_file() else b"{}\n"
    resolutions = json.loads(resolution_bytes)
    evidence["resolutions.json"] = resolution_bytes
    try:
        model_version, provenance, evidence = build_provenance(runs, evidence, args.llm_model, args.llm_version)
    except ValueError as exc:
        sys.exit(str(exc))
    second = {
        "id": "reviewer-llm-01",
        "kind": "llm",
        "role": "second_reviewer",
        "model": args.llm_model,
        "model_version": model_version,
        "prompt_hash": prompt_hash,
    }

    samples, problems = [], []
    for batch in args.batches:
        for s in samples_by_batch[batch]:
            sid = s["sample_id"]
            v = verdicts.get(sid)
            if v is None:
                problems.append(f"{sid}: no verdict")
                continue
            if v["verdict"] == "agree":
                status, note = "agreed", None
            else:
                r = resolutions.get(sid)
                if r is None:
                    problems.append(f"{sid}: disputed but no resolution")
                    continue
                if r.get("accepted"):
                    problems.append(
                        f"{sid}: dispute accepted -> sample must be changed and re-reviewed, not assembled from the old verdict"
                    )
                    continue
                note = r.get("resolution_note", "")
                if not note:
                    problems.append(f"{sid}: disputed_resolved needs resolution_note")
                    continue
                try:
                    verify_resolution(r, reviewed_records[sid], v)
                except ValueError as exc:
                    problems.append(f"{sid}: {exc}")
                    continue
                status = "disputed_resolved"
            record = {
                k: s[k] for k in ("sample_id", "query", "dept", "language", "slices", "required_gold_evidence", "notes")
            }
            # probe_sample.schema.json reviewer objects carry no `role`; manifest.reviewers do (PR-09 matches id/model/version/hash)
            record["review"] = {
                "annotator": {k: ANNOTATOR[k] for k in ("id", "kind")},
                "second_reviewer": {k: v for k, v in second.items() if k != "role"},
                "status": status,
                "resolution_note": note,
            }
            samples.append(record)
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  ", p)
        sys.exit(1)
    samples.sort(key=lambda x: x["sample_id"])
    ids = Counter(x["sample_id"] for x in samples)
    if any(n > 1 for n in ids.values()):
        sys.exit("duplicate sample_id")

    # extraction metadata must agree with every per-document extraction.json
    extraction = {
        "extractor": extract.EXTRACTOR,
        "extractor_version": extract.EXTRACTOR_VERSION,
        "params": extract.PARAMS,
        "params_hash": extract.PARAMS_HASH,
    }
    for h in docs:
        meta_path = out / "pages" / h / "extraction.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for k in ("extractor", "extractor_version", "params_hash"):
                if meta.get(k) != extraction[k]:
                    sys.exit(
                        f"extraction.json for {h[:12]} has {k}={meta.get(k)!r}, manifest would say {extraction[k]!r}"
                    )

    def sample_language(s: dict) -> str:
        langs = {docs[g["source_hash"]]["language"] for g in s["required_gold_evidence"]}
        return langs.pop() if len(langs) == 1 else "mixed"

    per_slice = Counter(sl for s in samples for sl in s["slices"])
    per_dept = Counter(s["dept"] for s in samples)
    per_language = Counter(sample_language(s) for s in samples)
    counts = {
        "samples": len(samples),
        "documents": len(docs),
        "per_slice": {k: per_slice.get(k, 0) for k in SLICES},
        "per_dept": {k: per_dept.get(k, 0) for k in DEPTS},
        "per_language": {k: per_language.get(k, 0) for k in LANGS},
    }

    samples_path = out / "samples.jsonl"
    for name, data in evidence.items():
        destination = out / "review_evidence" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    samples_path.write_bytes(("\n".join(canonical_json(x) for x in samples) + "\n").encode("utf-8"))
    included = [corpus_path, samples_path, prompt_path]
    included.extend(out / name for name in ("acl_probes.jsonl", "pii_exceptions.json") if (out / name).is_file())
    files = [{"path": p.name, "sha256": sha256_file(p)} for p in sorted(included)]
    manifest = {
        "dataset_id": "precise_clause_probe",
        "dataset_version": corpus["dataset_version"],
        "spec_version": "spec-v1",
        "status": "draft",
        "created_at": args.created_at,
        "frozen_at": None,
        "purpose": "精确条款探针集 v1：DEC-001 词法检索选型实验的固定输入；16 份已签署许可的公开文档，人工标注加 LLM 独立复核。",
        "source_store": {
            "kind": "local_path",
            "location": "v1/sources（本地目录，不进入 Git；完整性由 corpus.json 的 source_hash 校验）",
        },
        "extraction": extraction,
        "normalization": "norm-v1",
        "minimums": MINIMUMS,
        "counts": counts,
        "reviewers": [ANNOTATOR, second],
        "review_provenance": provenance,
        "review_policy": {
            "human_reviewers": 1,
            "llm_reviewers": 1,
            "statement": "人工标注加 LLM 独立复核；不等同于两名独立人工复核。",
        },
        "pii_ruleset_version": "pii-rules-v1",
        "files": files,
        "dataset_hash": None,
        "supersedes": None,
        "change_reason": None,
    }
    manifest_path.write_bytes((canonical_json(manifest) + "\n").encode("utf-8"))
    print(f"wrote {samples_path} ({len(samples)} samples) and {manifest_path}")
    print("counts:", json.dumps(counts, ensure_ascii=False))
    print("review status:", dict(Counter(x["review"]["status"] for x in samples)))


if __name__ == "__main__":
    main()
