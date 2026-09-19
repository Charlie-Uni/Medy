"""Builds a synthetic, fully frozen probe-set version directory for validator tests.

12 documents (MA 4 zh-Hans, PV 4 zh-Hant, CO 4 en), 6 samples each = 72 samples, two synthetic
pages per document with unique key phrases. Everything is fictional; no real drug or document.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from medops.core.canonical import canonical_json
from medops.retrieval.lexical.normalization import normalize_text

SLICES = ["drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en"]
DEPT_LANG = {"MA": "zh-Hans", "PV": "zh-Hant", "CO": "en"}
PROMPT = "示意复核 prompt：核对 query、切片、key_text 唯一性、evidence_span、部门归属。\n"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def raw_page_text(d: int, page: int) -> str:
    # Deliberately contains extraction whitespace and full-width punctuation so that the
    # validator must apply norm-v1 before matching.
    clauses = [f"条款 {d}-{j}：KEY{d:02d}{j} 每 日 {j + 1} 次。" for j in range(6) if j % 2 + 1 == page]
    return f"第 {page} 节  示意文本\n" + "\n".join(clauses) + "\n"


def build(root: Path, pages_root: Path) -> Path:
    version = root / "v1"
    version.mkdir(parents=True)
    docs, samples = [], []
    d = 0
    for dept in ("MA", "PV", "CO"):
        for _ in range(4):
            d += 1
            source_hash = sha(f"doc{d}".encode())
            docs.append(
                {
                    "document_key": f"doc-{d:02d}",
                    "title": f"示意文档 {d}",
                    "doc_type": "label" if dept == "MA" else "guideline",
                    "owner_dept": dept,
                    "language": DEPT_LANG[dept],
                    "source_url": f"https://example.invalid/doc{d}.pdf",
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
                (p / f"{page}.txt").write_text(raw_page_text(d, page), encoding="utf-8")
            for j in range(6):
                n = len(samples) + 1
                slc = SLICES[j % 6]
                if DEPT_LANG[dept] == "en" and slc == "drug_name_zh":
                    slc = "time_window"
                language = "mixed" if slc == "mixed_zh_en" else ("en" if DEPT_LANG[dept] == "en" else "zh")
                page = j % 2 + 1
                page_text = normalize_text(raw_page_text(d, page))
                span_text = normalize_text(f"条款 {d}-{j}：KEY{d:02d}{j} 每 日 {j + 1} 次。")
                start = page_text.index(span_text)
                samples.append(
                    {
                        "sample_id": f"pc-{n:04d}",
                        "query": f"示意文档{d}第{j}条的用法是什么",
                        "dept": dept,
                        "language": language,
                        "slices": [slc],
                        "required_gold_evidence": [
                            {
                                "gold_id": f"pc-{n:04d}-g1",
                                "source_hash": source_hash,
                                "version_label": "v1",
                                "page": page,
                                "printed_page_label": None,
                                "section": f"第 {page} 节",
                                "key_text": f"KEY{d:02d}{j}",
                                "evidence_span": {
                                    "text": span_text,
                                    "char_start": start,
                                    "char_end": start + len(span_text),
                                },
                            }
                        ],
                        "review": {
                            "annotator": {"kind": "human", "id": "annotator-01"},
                            "second_reviewer": {
                                "kind": "llm",
                                "id": "reviewer-llm-01",
                                "model": "<model>",
                                "model_version": "<v>",
                                "prompt_hash": sha(PROMPT.encode()),
                            },
                            "status": "agreed",
                            "resolution_note": None,
                        },
                        "notes": "",
                    }
                )
    corpus_b = (canonical_json({"dataset_version": "v1", "documents": docs}) + "\n").encode()
    samples_b = "".join(canonical_json(s) + "\n" for s in samples).encode()
    prompt_b = PROMPT.encode()
    (version / "corpus.json").write_bytes(corpus_b)
    (version / "samples.jsonl").write_bytes(samples_b)
    (version / "review_prompt.md").write_bytes(prompt_b)
    sums = "".join(
        f"{sha(b)}  {n}\n"
        for n, b in sorted({"corpus.json": corpus_b, "samples.jsonl": samples_b, "review_prompt.md": prompt_b}.items())
    )
    (version / "SHA256SUMS").write_bytes(sums.encode())
    from collections import Counter

    per_slice = Counter(s["slices"][0] for s in samples)
    per_dept = Counter(s["dept"] for s in samples)
    langs = {doc["source_hash"]: doc["language"] for doc in docs}
    per_language = Counter(langs[s["required_gold_evidence"][0]["source_hash"]] for s in samples)
    params = {"layout": "text"}
    manifest = {
        "dataset_id": "precise_clause_probe",
        "dataset_version": "v1",
        "spec_version": "spec-v1",
        "status": "frozen",
        "created_at": "2026-09-01",
        "frozen_at": "2026-09-02",
        "purpose": "validator fixture: synthetic frozen probe set (not real data)",
        "source_store": {"kind": "local_path", "location": str(pages_root)},
        "extraction": {
            "extractor": "fixture",
            "extractor_version": "1",
            "params": params,
            "params_hash": sha(canonical_json(params).encode()),
        },
        "normalization": "norm-v1",
        "minimums": {
            "samples": 60,
            "target_samples": 72,
            "per_slice": 8,
            "per_dept": 15,
            "max_samples_per_document": 6,
            "documents": 10,
            "documents_per_dept": 3,
            "zh_hans_samples": 8,
        },
        "counts": {
            "samples": len(samples),
            "documents": len(docs),
            "per_slice": {k: per_slice.get(k, 0) for k in SLICES},
            "per_dept": {k: per_dept.get(k, 0) for k in ("MA", "PV", "CO")},
            "per_language": {k: per_language.get(k, 0) for k in ("zh-Hans", "zh-Hant", "en", "mixed")},
        },
        "reviewers": [
            {"role": "annotator", "kind": "human", "id": "annotator-01"},
            {
                "role": "second_reviewer",
                "kind": "llm",
                "id": "reviewer-llm-01",
                "model": "<model>",
                "model_version": "<v>",
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
        "supersedes": None,
        "change_reason": None,
    }
    (version / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (version / "mappings").mkdir()
    mapping = {
        "dataset_version": "v1",
        "dataset_hash": manifest["dataset_hash"],
        "chunker_version": "fixture-chunker-1",
        "extraction": dict(manifest["extraction"]),
        "normalization": "norm-v1",
        "generated_at": "2026-09-02T00:00:00Z",
        "generator": "fixture",
        "entries": [
            {
                "gold_id": s["required_gold_evidence"][0]["gold_id"],
                "status": "mapped",
                "chunk_ids": [f"chunk-{i}"],
                "reason": None,
            }
            for i, s in enumerate(samples)
        ],
    }
    mapping["extraction"] = {k: v for k, v in manifest["extraction"].items() if k != "params"}
    (version / "mappings" / "chunk_mapping.fixture-chunker-1.json").write_text(
        json.dumps(mapping, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return version


def refreeze(version: Path) -> None:
    """Recompute SHA256SUMS, manifest.files and dataset_hash after a fixture mutation."""
    names = [
        n
        for n in ("acl_probes.jsonl", "corpus.json", "pii_exceptions.json", "review_prompt.md", "samples.jsonl")
        if (version / n).is_file()
    ]
    sums = "".join(f"{sha((version / n).read_bytes())}  {n}\n" for n in names)
    (version / "SHA256SUMS").write_bytes(sums.encode())
    manifest = json.loads((version / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"] = [{"path": n, "sha256": sha((version / n).read_bytes())} for n in names]
    manifest["dataset_hash"] = sha(sums.encode())
    (version / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for m in (version / "mappings").glob("*.json"):
        data = json.loads(m.read_text(encoding="utf-8"))
        data["dataset_hash"] = manifest["dataset_hash"]
        m.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
