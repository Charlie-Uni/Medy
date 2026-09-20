"""Builds a synthetic, fully frozen main-set (spec-m1) version directory for validator tests.

Layout under `root`: the probe fixture at evals/probe/precise_clause/v1 (72 `pc-` samples, imported verbatim) and
the main set at evals/main_set/main-v1-provisional with 21 extra documents (MA zh-Hant x10, PV en x6, CO en x5,
two of the CO documents registered as synthetic conflict fixtures), 8 non-derived samples per new document (one
long-context clause each), English twins for every English-document sample, and 40 no-answer samples. Everything
is fictional; the numbers are chosen to satisfy the spec-m1 minimums so that frozen validation passes.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from medops.core.canonical import canonical_json
from medops.retrieval.lexical.normalization import normalize_text
from tests.unit.evals.fixture_builder import PROMPT as PROBE_PROMPT
from tests.unit.evals.fixture_builder import build as build_probe

SLICES = ["drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en"]
NEW_SLICES = ["version_conflict", "no_answer", "long_context"]
MAIN_PROMPT = "示意主集复核 prompt：有答案五项、无答案四项、孪生对照 parent_query。\n"
NEW_DOCS = [("MA", "zh-Hant", "label")] * 10 + [("PV", "en", "guideline")] * 6 + [("CO", "en", "guideline")] * 5
CONFLICT_DOCS = {"mdoc-32", "mdoc-33"}  # the last two CO documents (English, so their twins inherit the slice)
REVIEW = {
    "annotator": {"kind": "human", "id": "annotator-01"},
    "second_reviewer": {
        "kind": "llm",
        "id": "reviewer-llm-02",
        "model": "claude-opus-5",
        "model_version": "claude-opus-5",
        "prompt_hash": hashlib.sha256(MAIN_PROMPT.encode()).hexdigest(),
    },
    "status": "agreed",
    "resolution_note": None,
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def raw_page_text(d: int, page: int) -> str:
    if page == 1:
        return (
            "第 1 节 主集示意\n"
            + "\n".join(f"条款 M{d}-{j}：MKEY{d:02d}{j} 每 日 {j + 1} 次。" for j in range(7))
            + "\n"
        )
    return f"第 2 节 长条款\n長條款 MLONG{d:02d} " + "要件" * 800 + "。\n"


def build_main(root: Path, pages_root: Path) -> Path:
    probe_version = build_probe(root / "evals/probe/precise_clause", pages_root)
    probe_manifest = json.loads((probe_version / "manifest.json").read_text(encoding="utf-8"))
    probe_samples_raw = (probe_version / "samples.jsonl").read_bytes()
    probe_docs = json.loads((probe_version / "corpus.json").read_text(encoding="utf-8"))["documents"]
    imported = [json.loads(line) for line in probe_samples_raw.decode("utf-8").splitlines() if line.strip()]

    version = root / "evals/main_set/main-v1-provisional"
    version.mkdir(parents=True)
    docs = list(probe_docs)
    samples: list[dict] = []
    twins: list[dict] = []
    n = 0

    def next_id() -> str:
        nonlocal n
        n += 1
        return f"ms-{n:04d}"

    for i, (dept, lang, kind) in enumerate(NEW_DOCS, start=13):
        key = f"mdoc-{i}"
        source_hash = sha(f"mdoc{i}".encode())
        docs.append(
            {
                "document_key": key,
                "title": f"主集示意文档 {i}",
                "doc_type": kind,
                "owner_dept": dept,
                "language": lang,
                "source_url": f"https://example.invalid/mdoc{i}.pdf",
                "publisher": "示意发布方",
                "license_status": "eligible",
                "license_or_terms": {
                    "name_or_summary": "示意开放许可 CC BY 4.0",
                    "permitted_scope": "保存、索引、引用、展示",
                    "attribution_required": True,
                    "attribution_text": "示意发布方",
                    "third_party_content_checked": True,
                    "third_party_note": None,
                    "verified_at": "2026-09-01",
                    "verified_by": "reviewer-01",
                },
                "terms_url": "https://example.invalid/terms",
                "retrieved_at": "2026-09-01",
                "version_label": "v1",
                "source_hash": source_hash,
                "byte_size": 1000,
                "mime": "application/pdf",
                "pages": 2,
                "pii_scan": {
                    "status": "clean",
                    "method": "regex",
                    "ruleset_version": "pii-rules-v1",
                    "scanned_at": "2026-09-01",
                },
                "notes": "用于 PV 部门不良事件报告时限条款检索（示意）" if dept == "PV" else "示意文档",
            }
        )
        for page in (1, 2):
            p = pages_root / source_hash
            p.mkdir(parents=True, exist_ok=True)
            (p / f"{page}.txt").write_text(raw_page_text(i, page), encoding="utf-8")
        conflict = key in CONFLICT_DOCS
        for j in range(8):
            sid = next_id()
            long = j == 7
            page = 2 if long else 1
            page_text = normalize_text(raw_page_text(i, page))
            if long:
                key_text = f"MLONG{i:02d}"
                span_text = page_text[page_text.index("長條款") :]
            else:
                key_text = f"MKEY{i:02d}{j}"
                span_text = normalize_text(f"条款 M{i}-{j}：MKEY{i:02d}{j} 每 日 {j + 1} 次。")
            start = page_text.index(span_text)
            slc = SLICES[j % 6]
            if lang == "en" and slc == "drug_name_zh":
                slc = "time_window"
            slices = [slc] + (["long_context"] if long else []) + (["version_conflict"] if conflict else [])
            language = "mixed" if slc == "mixed_zh_en" else "zh"
            sample = {
                "sample_id": sid,
                "query": f"主集文档{i}第{j}条的用法是什么",
                "dept": dept,
                "language": language,
                "slices": slices,
                "required_gold_evidence": [
                    {
                        "gold_id": f"{sid}-g1",
                        "source_hash": source_hash,
                        "version_label": "v1",
                        "page": page,
                        "printed_page_label": None,
                        "section": f"第 {page} 节",
                        "key_text": key_text,
                        "evidence_span": {"text": span_text, "char_start": start, "char_end": start + len(span_text)},
                    }
                ],
                "review": REVIEW,
                "notes": "合成冲突：旧版与现行版正文相同，只检验版本状态过滤" if conflict else "",
                "drafted_by": {"kind": "llm", "id": "drafter-llm-03", "model": "claude-sonnet-5"},
            }
            if conflict:
                sample["conflict"] = {
                    "family_document_keys": [key, f"{key}--synthetic-old"],
                    "current_document_key": key,
                    "clause_topic": f"条款 {j}",
                    "synthetic": True,
                }
            samples.append(sample)
            if lang == "en":
                tid = next_id()
                twin = json.loads(json.dumps(sample, ensure_ascii=False))
                twin.update(
                    sample_id=tid,
                    query=f"What does clause {j} of main document {i} require?",
                    language="en",
                    derived_from=sid,
                )
                twin["required_gold_evidence"][0]["gold_id"] = f"{tid}-g1"
                twins.append(twin)
    samples.extend(twins)
    by_dept_docs = {dept: [d for d in docs if d["owner_dept"] == dept] for dept in ("MA", "PV", "CO")}
    for k in range(40):
        dept = ("MA", "PV", "CO")[k % 3]
        doc = by_dept_docs[dept][k % len(by_dept_docs[dept])]
        sid = next_id()
        samples.append(
            {
                "sample_id": sid,
                "query": f"{doc['title']}是否说明了第{k}项未记载事项",
                "dept": dept,
                "language": "zh",
                "slices": ["no_answer"],
                "required_gold_evidence": [],
                "answerable": False,
                "expected_behaviour": "insufficient_evidence",
                "abstention": {
                    "scope_document_key": doc["document_key"],
                    "topic": f"未记载事项 {k}",
                    "absence_check": "关键词在文档全部页文本中均未出现",
                    "document_pages": [1, 2],
                },
                "review": REVIEW,
                "notes": "",
                "drafted_by": {"kind": "llm", "id": "drafter-llm-03", "model": "claude-sonnet-5"},
            }
        )
    all_samples = imported + samples
    all_samples.sort(key=lambda s: s["sample_id"])
    corpus_b = (canonical_json({"dataset_version": "main-v1-provisional", "documents": docs}) + "\n").encode()
    samples_b = "".join(canonical_json(s) + "\n" for s in all_samples).encode()
    prompt_b = MAIN_PROMPT.encode()
    (version / "corpus.json").write_bytes(corpus_b)
    (version / "samples.jsonl").write_bytes(samples_b)
    (version / "review_prompt.md").write_bytes(prompt_b)
    sums = "".join(
        f"{sha(b)}  {name}\n"
        for name, b in sorted(
            {"corpus.json": corpus_b, "samples.jsonl": samples_b, "review_prompt.md": prompt_b}.items()
        )
    )
    (version / "SHA256SUMS").write_bytes(sums.encode())
    lang_of = {d["source_hash"]: d["language"] for d in docs}
    lang_by_key = {d["document_key"]: d["language"] for d in docs}

    def language(s: dict) -> str:
        if s["required_gold_evidence"]:
            return lang_of[s["required_gold_evidence"][0]["source_hash"]]
        return lang_by_key[s["abstention"]["scope_document_key"]]

    per_slice = Counter(sl for s in all_samples for sl in s["slices"])
    per_dept = Counter(s["dept"] for s in all_samples)
    per_language = Counter(language(s) for s in all_samples)
    params = {"layout": "text"}
    manifest = {
        "dataset_id": "precise_clause_main",
        "dataset_version": "main-v1-provisional",
        "spec_version": "spec-m1",
        "status": "frozen",
        "created_at": "2026-09-21",
        "frozen_at": "2026-09-22",
        "purpose": "validator fixture: synthetic frozen main set (not real data)",
        "source_store": {"kind": "local_path", "location": str(pages_root)},
        "extraction": {
            "extractor": "fixture",
            "extractor_version": "1",
            "params": params,
            "params_hash": sha(canonical_json(params).encode()),
        },
        "normalization": "norm-v1",
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
        "counts": {
            "samples": len(all_samples),
            "answerable": sum(s.get("answerable", True) is not False for s in all_samples),
            "no_answer": sum(s.get("answerable", True) is False for s in all_samples),
            "conflict": sum("version_conflict" in s["slices"] for s in all_samples),
            "derived": sum(bool(s.get("derived_from")) for s in all_samples),
            "imported": len(imported),
            "documents": len(docs),
            "per_slice": {k: per_slice.get(k, 0) for k in SLICES + NEW_SLICES},
            "per_dept": {k: per_dept.get(k, 0) for k in ("MA", "PV", "CO")},
            "per_language": {k: per_language.get(k, 0) for k in ("zh-Hans", "zh-Hant", "en", "mixed")},
        },
        "reviewers": [
            {"role": "annotator", "kind": "human", "id": "annotator-01"},
            {
                "role": "second_reviewer",
                "kind": "llm",
                "id": "reviewer-llm-02",
                "model": "claude-opus-5",
                "model_version": "claude-opus-5",
                "prompt_hash": sha(prompt_b),
            },
        ],
        "review_policy": {
            "human_reviewers": 1,
            "llm_reviewers": 1,
            "statement": "人工标注加 LLM 独立复核；不等同于两名独立人工复核。",
        },
        "pii_ruleset_version": "pii-rules-v1",
        "files": [
            {"path": "corpus.json", "sha256": sha(corpus_b)},
            {"path": "review_prompt.md", "sha256": sha(prompt_b)},
            {"path": "samples.jsonl", "sha256": sha(samples_b)},
        ],
        "dataset_hash": sha(sums.encode()),
        "supersedes": "v1",
        "change_reason": "spec-m1 主集：并入探针 v1 全部样本并新增主集样本（示意）",
        "derived_samples": {
            "rule": "English query twins of every sample whose gold document is English; gold, dept and slices inherited",
            "count": len(twins),
            "query_language": "en",
            "drafted_by": {"kind": "llm", "id": "drafter-llm-03", "model": "claude-sonnet-5"},
            "human_confirmation": {"status": "confirmed", "annotator_id": "annotator-01", "confirmed_on": "2026-09-21"},
        },
        "imported_samples": {
            "dataset_id": "precise_clause_probe",
            "dataset_version": probe_manifest["dataset_version"],
            "dataset_hash": probe_manifest["dataset_hash"],
            "path": "evals/probe/precise_clause/v1/samples.jsonl",
            "samples_sha256": sha(probe_samples_raw),
            "count": len(imported),
            "prompt_hash": sha(PROBE_PROMPT.encode()),
            "reviewer_id": "reviewer-llm-01",
            "statement": "探针样本原样并入，保留探针版本的复核记录与提示哈希；主集报告单列探针子集。",
        },
        "second_human_review": {
            "status": "pending",
            "reviewer_id": None,
            "statement": "第二人工复核人暂无（决策人 2026-09-21）；本集只能以 provisional 运行。",
        },
        "conflict_fixtures": [
            {
                "document_key": k,
                "archived_document_keys": [f"{k}--synthetic-old"],
                "synthetic": True,
                "source": "同一 PDF 以两个 document_key 入库并归档旧版（示意）",
            }
            for k in sorted(CONFLICT_DOCS)
        ],
    }
    (version / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return version
