"""Validate recorded review evidence without claiming an unavailable model snapshot.

The assembler verifies actual prompts against local page text. This check deliberately
does not read input packs: it verifies the frozen sample coverage, v2 result bindings,
human resolutions and the eight hashed execution artifacts copied into the version.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from medops.core.canonical import canonical_json

if TYPE_CHECKING:
    from medops.evals.probe.validator import Finding, PageTextProvider

BATCHES = ("MA", "PV", "CO")
DERIVED_BATCH = "EN"  # spec-v1.1: derived English twins are reviewed as their own batch
NO_ANSWER_BATCH = "NA"  # spec-m1: no-answer samples are reviewed as their own batch (different record shape)


def is_main_set(manifest: Mapping[str, Any]) -> bool:
    return manifest.get("spec_version") == "spec-m1"


def batches_for(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    if is_main_set(manifest):
        return BATCHES + (DERIVED_BATCH, NO_ANSWER_BATCH)
    return BATCHES + (DERIVED_BATCH,) if manifest.get("spec_version") == "spec-v1.1" else BATCHES


def imported_sample(sample: Mapping[str, Any]) -> bool:
    """spec-m1: merged probe samples keep their `pc-` ids and their probe review evidence (validator PR-16)."""
    return str(sample["sample_id"]).startswith("pc-")


def batch_of(sample: Mapping[str, Any]) -> str:
    if sample.get("answerable", True) is False:
        return NO_ANSWER_BATCH
    return DERIVED_BATCH if sample.get("derived_from") else str(sample["dept"])


def evidence_names(batches: tuple[str, ...]) -> tuple[str, ...]:
    return (
        tuple(f"run_{batch}.json" for batch in batches)
        + tuple(f"verdicts_{batch}.jsonl" for batch in batches)
        + ("resolutions.json", "reviewer_runtime_metadata.json")
    )


EVIDENCE_NAMES = evidence_names(BATCHES)
EVIDENCE_PATHS = tuple(f"review_evidence/{name}" for name in EVIDENCE_NAMES)
ITEM_KEYS = {"query", "slices", "key_text", "evidence_span", "dept"}
ITEM_KEYS_NO_ANSWER = {"query", "absence", "slices", "dept"}  # spec-m1 no-answer verdicts
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def service_alias_version(model: str) -> str:
    """Explicitly describe observed identity and missing metadata, not a pinned version."""
    return f"service-alias:{model};backend-version:not-exposed"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _hashes(value: Any, ids: set[str], label: str) -> None:
    _require(isinstance(value, dict) and set(value) == ids, f"{label}: hash coverage mismatch")
    _require(all(isinstance(v, str) and _SHA256.fullmatch(v) for v in value.values()), f"{label}: invalid hash")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON object key in review evidence")
        result[key] = value
    return result


def _json(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)


def _jsonl(data: bytes) -> list[dict[str, Any]]:
    rows = [_json(line) for line in data.splitlines() if line.strip()]
    _require(all(isinstance(row, dict) for row in rows), "JSONL review evidence must contain objects")
    return rows


def _verdicts(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        _require(set(row) == {"sample_id", "verdict", "items", "reason", "suggestion"}, "invalid verdict fields")
        sid = row["sample_id"]
        _require(isinstance(sid, str) and sid not in result, "duplicate or invalid verdict sample_id")
        items = row["items"]
        _require(
            isinstance(items, dict) and set(items) in (ITEM_KEYS, ITEM_KEYS_NO_ANSWER), f"{sid}: invalid verdict items"
        )
        _require(all(value in ("ok", "issue") for value in items.values()), f"{sid}: invalid verdict item value")
        expected = "dispute" if "issue" in items.values() else "agree"
        _require(row["verdict"] == expected, f"{sid}: verdict disagrees with its issue items")
        _require(isinstance(row["reason"], str) and isinstance(row["suggestion"], str), f"{sid}: invalid verdict text")
        _require(expected != "dispute" or bool(row["reason"].strip()), f"{sid}: disputed verdict needs a reason")
        result[sid] = row
    return result


def _read_artifacts(version_dir: Path, provenance: dict[str, Any], batches: tuple[str, ...]) -> dict[str, bytes]:
    names = evidence_names(batches)
    required_paths = tuple(f"review_evidence/{name}" for name in names)
    entries = provenance["artifacts"]
    _require(
        isinstance(entries, list) and len(entries) == len(required_paths),
        f"review evidence must contain {len(names)} artifacts",
    )
    paths = [entry["path"] for entry in entries]
    _require(
        len(set(paths)) == len(paths) and set(paths) == set(required_paths),
        "review evidence paths must match the required files",
    )
    root = version_dir.resolve()
    evidence_dir = version_dir / "review_evidence"
    _require(not evidence_dir.is_symlink(), "review_evidence directory must not be a symlink")
    result = {}
    for entry in entries:
        relative = entry["path"]
        path = version_dir / relative
        _require(
            not path.is_symlink() and path.resolve().is_relative_to(root),
            f"{relative}: artifact escapes version directory or is a symlink",
        )
        raw = path.read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == entry["sha256"], f"{relative}: artifact SHA-256 mismatch")
        result[Path(relative).name] = raw
    return result


def _current_records(
    version_dir: Path, samples: list[dict[str, Any]], pages: PageTextProvider | None
) -> dict[str, dict[str, Any]] | None:
    if pages is None:
        return None
    corpus = _json((version_dir / "corpus.json").read_bytes())
    docs = {d["source_hash"]: d for d in corpus["documents"]}
    by_key = {d["document_key"]: d for d in corpus["documents"]}
    by_id = {s["sample_id"]: s for s in samples}
    main_set = any(str(s["sample_id"]).startswith("ms-") for s in samples)
    result = {}
    for sample in samples:
        if sample.get("answerable", True) is False:
            # spec-m1 no-answer record: the scope document's packed pages instead of a gold page
            record = _no_answer_record(sample, by_key, pages)
            if record is None:
                return None
            result[sample["sample_id"]] = record
            continue
        _require(len(sample["required_gold_evidence"]) == 1, "recorded review protocol requires one gold per sample")
        gold = sample["required_gold_evidence"][0]
        doc = docs[gold["source_hash"]]
        text = pages.page_text(gold["source_hash"], gold["page"])
        if text is None:
            return None
        if main_set and sample.get("derived_from"):
            parent = by_id.get(sample["derived_from"])
            _require(parent is not None, f"{sample['sample_id']}: derived_from parent missing from the review scope")
        result[sample["sample_id"]] = {
            "sample_id": sample["sample_id"],
            "query": sample["query"],
            "dept": sample["dept"],
            "language": sample["language"],
            "slices": sample["slices"],
            "gold": {
                "page": gold["page"],
                "section": gold["section"],
                "key_text": gold["key_text"],
                "evidence_span": {key: gold["evidence_span"][key] for key in ("text", "char_start", "char_end")},
            },
            "document": {
                "document_key": doc["document_key"],
                "title": doc["title"],
                "doc_type": doc["doc_type"],
                "language": doc["language"],
            },
            "page_text": text,
        }
        if main_set and sample.get("conflict"):
            result[sample["sample_id"]]["conflict"] = sample["conflict"]
        if main_set and sample.get("notes"):
            result[sample["sample_id"]]["notes"] = sample["notes"]
        if main_set and sample.get("derived_from"):
            result[sample["sample_id"]]["parent_query"] = by_id[sample["derived_from"]]["query"]
    return result


def no_answer_document_text(pages: PageTextProvider, source_hash: str, page_numbers: list[int]) -> str | None:
    parts = []
    for p in page_numbers:
        text = pages.page_text(source_hash, p)
        if text is None:
            return None
        parts.append(f"=== 第 {p} 页 ===\n{text}")
    return "\n".join(parts)


def _no_answer_record(
    sample: Mapping[str, Any], by_key: Mapping[str, Any], pages: PageTextProvider
) -> dict[str, Any] | None:
    ab = sample["abstention"]
    doc = by_key[ab["scope_document_key"]]
    text = no_answer_document_text(pages, doc["source_hash"], list(ab["document_pages"]))
    if text is None:
        return None
    return {
        "sample_id": sample["sample_id"],
        "query": sample["query"],
        "dept": sample["dept"],
        "language": sample["language"],
        "slices": sample["slices"],
        "answerable": False,
        "abstention": {k: ab[k] for k in ("scope_document_key", "topic", "absence_check")},
        "document": {
            "document_key": doc["document_key"],
            "title": doc["title"],
            "doc_type": doc["doc_type"],
            "language": doc["language"],
        },
        "document_text": text,
    }


def _span_variants(record: dict[str, Any]) -> list[dict[str, Any]]:
    if "gold" not in record:
        return [record]
    """The two serialisations an input pack may have used for evidence_span: the explicit
    (text, char_start, char_end) order of the v1 drafting tools, or canonical sorted keys when the pack
    was re-exported from a canonical samples.jsonl (v2). Content is identical; only key order differs."""
    span = record["gold"]["evidence_span"]
    ordered = {"text": span["text"], "char_start": span["char_start"], "char_end": span["char_end"]}
    canonical = {k: span[k] for k in sorted(span)}
    out = []
    for variant in (ordered, canonical):
        r = dict(record)
        r["gold"] = dict(record["gold"])
        r["gold"]["evidence_span"] = variant
        out.append(r)
    return out


def _actual_prompt_hashes(prompt_text: str, records: list[dict[str, Any]]) -> set[str]:
    """Prompt hashes for every per-record key-order combination of evidence_span (a pack may mix records
    re-exported from canonical JSON with records edited by the drafting tools). Chunks are at most a
    handful of records, so the product stays small; larger packs fall back to the two uniform variants."""
    variants = [_span_variants(r) for r in records]
    if len(records) > 8:
        return {_actual_prompt_hash(prompt_text, [v[i] for v in variants]) for i in range(2)}
    return {
        _actual_prompt_hash(prompt_text, [v[i] for v, i in zip(variants, choice, strict=True)])
        for choice in itertools.product((0, 1), repeat=len(records))
    }


def _actual_prompt_hash(prompt_text: str, records: list[dict[str, Any]]) -> str:
    """Frozen v2 invocation wire format; keep its byte order, including JSON key order."""
    parts = [
        "下面第一部分是复核提示原文，第二部分是本轮要复核的样本（每条含 gold 页的页文本）。",
        f"严格按复核提示的输出格式作答：只输出 JSON 行，每条样本一行，共 {len(records)} 行，不要任何其他文字或代码围栏。",
        "",
        "===== 第一部分：复核提示 =====",
        prompt_text.rstrip("\n"),
        "",
        "===== 第二部分：样本 =====",
    ]
    parts.extend(json.dumps(record, ensure_ascii=False) for record in records)
    parts.extend(["", f"===== 结束：请输出 {len(records)} 行 JSON ====="])
    return hashlib.sha256(("\n".join(parts) + "\n").encode("utf-8")).hexdigest()


def _validate(
    version_dir: Path, manifest: dict[str, Any], second: dict[str, Any], pages: PageTextProvider | None
) -> bool:
    model = second["model"]
    provenance = manifest.get("review_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("LLM review evidence requires review_provenance")
    source = provenance.get("version_source")
    _require(source in ("service_alias", "pinned_model_id"), "unknown review_provenance version_source")
    pinned = source == "pinned_model_id"
    if pinned:
        # spec-v1.1 (record 35): the CLI exposes a fixed model identifier, so model_version IS that identifier
        _require(
            second["model_version"] == model == provenance.get("backend_model_version"),
            "pinned model_version must equal the model identifier and backend_model_version",
        )
    else:
        _require(
            second["model_version"] == service_alias_version(model),
            "model_version must exactly describe the observed service alias and unexposed backend",
        )
        _require(
            "backend_model_version" in provenance and provenance["backend_model_version"] is None,
            "unexposed backend_model_version must be explicitly null",
        )
    effort = provenance.get("reasoning_effort", "high")
    _require(isinstance(effort, str) and bool(effort.strip()), "review_provenance must declare the reasoning effort")
    _require(provenance["reviewer_id"] == second["id"], "review_provenance reviewer_id differs from manifest")
    limitation = provenance["reproducibility_limitations"]
    _require(
        isinstance(limitation, str) and len(limitation.strip()) >= 20,
        "review_provenance needs an explicit reproducibility limitation",
    )
    batches = batches_for(manifest)
    artifacts = _read_artifacts(version_dir, provenance, batches)
    all_samples = _jsonl((version_dir / "samples.jsonl").read_bytes())
    sample_ids = [s["sample_id"] for s in all_samples]
    main_set = is_main_set(manifest)
    # spec-m1: imported probe samples carry probe review evidence (validator PR-16), not this version's
    samples = [s for s in all_samples if not (main_set and imported_sample(s))]
    expected_total = manifest["counts"]["samples"] - (manifest["counts"]["imported"] if main_set else 0)
    _require(
        len(set(sample_ids)) == len(all_samples) and len(samples) == expected_total,
        "review evidence sample coverage differs from manifest",
    )
    _require(all(batch_of(s) in batches for s in samples), "review evidence has an unknown sample batch")
    records = _current_records(version_dir, samples, pages)
    prompt_raw = (version_dir / "review_prompt.md").read_bytes()
    _require(
        hashlib.sha256(prompt_raw).hexdigest() == second["prompt_hash"], "review_prompt.md hash differs from manifest"
    )
    prompt_text = prompt_raw.decode("utf-8")
    resolutions = _json(artifacts["resolutions.json"])
    _require(isinstance(resolutions, dict), "resolutions must be an object")
    disputed = set()
    all_chunks = []
    for batch in batches:
        group = {s["sample_id"]: s for s in samples if batch_of(s) == batch}
        if main_set:
            if batch == DERIVED_BATCH:
                expected_size = int(manifest.get("derived_samples", {}).get("count", 0)) - sum(
                    1 for s in all_samples if imported_sample(s) and s.get("derived_from")
                )
            elif batch == NO_ANSWER_BATCH:
                expected_size = int(manifest["counts"]["no_answer"])
            else:
                expected_size = sum(
                    1
                    for s in samples
                    if s["dept"] == batch and not s.get("derived_from") and s.get("answerable", True) is not False
                )
        elif batch == DERIVED_BATCH:
            expected_size = int(manifest.get("derived_samples", {}).get("count", 0))
        elif manifest.get("spec_version") == "spec-v1.1":
            expected_size = sum(1 for s in samples if s["dept"] == batch and not s.get("derived_from"))
        else:
            expected_size = manifest["counts"]["per_dept"][batch]
        _require(bool(group) and len(group) == expected_size, f"{batch}: sample count mismatch")
        run = _json(artifacts[f"run_{batch}.json"])
        _require(
            run["batch"] == batch and run["provenance_version"] == 2, f"{batch}: requires matching v2 run evidence"
        )
        _require(run["active_review"] is None, f"{batch}: review is unfinished")
        _require(
            run["model"] == model and run["reasoning_effort_requested"] == effort, f"{batch}: model or effort mismatch"
        )
        _require(run["review_prompt_sha256"] == second["prompt_hash"], f"{batch}: review prompt hash mismatch")
        _require(
            run.get("backend_model_version") is None, f"{batch}: backend version is exposed, sentinel is inappropriate"
        )
        _hashes(run["sample_input_sha256"], set(group), batch)
        if records is not None:
            _require(
                run["sample_input_sha256"] == {sid: _digest(records[sid]) for sid in group},
                f"{batch}: current sample/page input hash differs from review",
            )
        latest, chunks = run["latest"], run["chunks"]
        _require(isinstance(latest, dict) and set(latest) == set(group), f"{batch}: latest coverage mismatch")
        _require(isinstance(chunks, list) and bool(chunks), f"{batch}: missing invocation evidence")
        current = _verdicts(_jsonl(artifacts[f"verdicts_{batch}.jsonl"]))
        _require(set(current) == set(group), f"{batch}: verdict coverage mismatch")
        for chunk in chunks:
            _require(
                chunk["model"] == model and chunk["reasoning_effort"] == effort and chunk["returncode"] == 0,
                f"{batch}: unsuccessful or mismatched invocation",
            )
            _require(
                all(
                    isinstance(chunk.get(k), str) and chunk[k].strip()
                    for k in ("session_id", "cli_version", "started_at", "finished_at")
                ),
                f"{batch}: missing invocation metadata",
            )
            _require(chunk.get("backend_model_version") is None, f"{batch}: invocation exposes a backend version")
            ids = chunk["sample_ids"]
            _require(
                isinstance(ids, list) and bool(ids) and len(ids) == len(set(ids)) and set(ids).issubset(group),
                f"{batch}: invalid invocation sample coverage",
            )
            _hashes(chunk["sample_input_sha256"], set(ids), batch)
            _require(
                isinstance(chunk["prompt_sha256"], str) and bool(_SHA256.fullmatch(chunk["prompt_sha256"])),
                f"{batch}: missing actual prompt hash",
            )
            _require(set(_verdicts(chunk["verdicts"])).issubset(ids), f"{batch}: invocation verdict coverage mismatch")
        all_chunks.extend(chunks)
        last_invocation = {sid: index for index, chunk in enumerate(chunks) for sid in chunk["sample_ids"]}
        for sid, sample in group.items():
            reference = latest[sid]
            index = reference["chunk_index"]
            _require(type(index) is int and 0 <= index < len(chunks), f"{sid}: invalid latest chunk index")
            _require(index == last_invocation.get(sid), f"{sid}: latest must reference the last appended invocation")
            chunk = chunks[index]
            _require(sid in chunk["sample_ids"], f"{sid}: latest points to an unrelated invocation")
            verdict = current[sid]
            _require(
                _verdicts(chunk["verdicts"]).get(sid) == verdict, f"{sid}: current verdict differs from invocation"
            )
            expected = {
                "chunk_index": index,
                "sample_input_sha256": chunk["sample_input_sha256"][sid],
                "prompt_sha256": chunk["prompt_sha256"],
                "verdict_sha256": _digest(verdict),
            }
            _require(
                reference == expected and reference["sample_input_sha256"] == run["sample_input_sha256"][sid],
                f"{sid}: latest binding mismatch",
            )
            if records is not None:
                inputs = [records[member] for member in chunk["sample_ids"]]
                _require(
                    chunk["sample_input_sha256"] == {record["sample_id"]: _digest(record) for record in inputs},
                    f"{sid}: latest invocation also contains superseded input; rereview before freezing",
                )
                _require(
                    chunk["prompt_sha256"] in _actual_prompt_hashes(prompt_text, inputs),
                    f"{sid}: actual prompt hash differs from current input",
                )
            reviewer = sample["review"]["second_reviewer"]
            _require(
                all(reviewer[k] == second[k] for k in ("id", "model", "model_version", "prompt_hash")),
                f"{sid}: sample reviewer differs from manifest",
            )
            if verdict["verdict"] == "agree":
                _require(sample["review"]["status"] == "agreed", f"{sid}: sample status disagrees with current verdict")
                continue
            disputed.add(sid)
            resolution = resolutions[sid]
            _require(not resolution.get("accepted"), f"{sid}: pending accepted dispute requires rereview")
            _require(
                resolution["sample_input_sha256"] == reference["sample_input_sha256"]
                and resolution["verdict_sha256"] == _digest(verdict),
                f"{sid}: stale resolution binding",
            )
            note = resolution["resolution_note"]
            _require(
                isinstance(note, str) and len(note.strip()) >= 5 and sample["review"]["resolution_note"] == note,
                f"{sid}: resolution note differs from sample",
            )
            _require(sample["review"]["status"] == "disputed_resolved", f"{sid}: disputed sample is not resolved")
            _require(
                set(resolution["issue_scope"]) == {k for k, v in verdict["items"].items() if v == "issue"},
                f"{sid}: resolution issue scope mismatch",
            )
    _require(set(resolutions) == disputed, "resolutions must cover exactly the current disputed samples")
    runtime = _json(artifacts["reviewer_runtime_metadata.json"])
    if pinned:
        _require(
            runtime.get("model") == model and runtime["backend_model_version"] == model,
            "runtime model identity differs from manifest",
        )
        _require(
            "pinned" in str(runtime["backend_model_version_status"]).lower(), "runtime must state the pinned identifier"
        )
    else:
        _require(
            runtime["model_service_alias"] == model and runtime["backend_model_version"] is None,
            "runtime model identity differs from manifest",
        )
        _require(
            "not exposed" in runtime["backend_model_version_status"].lower(),
            "runtime must disclose the unexposed backend version",
        )
    _require(runtime["reasoning_effort"] == effort, "runtime effort differs from invocations")
    _require(
        runtime["cli_versions"] == sorted({chunk["cli_version"] for chunk in all_chunks}),
        "runtime CLI versions differ from invocations",
    )
    _require(
        type(runtime["observed_successful_calls"]) is int and runtime["observed_successful_calls"] == len(all_chunks),
        "runtime invocation count differs from evidence",
    )
    _require(
        runtime["first_started_at"] == min(c["started_at"] for c in all_chunks)
        and runtime["last_finished_at"] == max(c["finished_at"] for c in all_chunks),
        "runtime time range differs from invocations",
    )
    if "current_reviewed_samples" in runtime:
        _require(
            runtime["current_reviewed_samples"] == len(samples), "runtime current sample count differs from dataset"
        )
    return records is not None


def validate_review_provenance(
    version_dir: Path, manifest: Mapping[str, Any], *, pages: PageTextProvider | None = None
) -> list[Finding]:
    """Return PR-09 findings; ordinary recorded model versions remain backwards compatible."""
    from medops.evals.probe.validator import Finding

    seconds = [
        r for r in manifest.get("reviewers", []) if r.get("role") == "second_reviewer" and r.get("kind") == "llm"
    ]
    special = any(
        str(r.get("model_version", "")).startswith("service-alias:")
        or "backend-version:" in str(r.get("model_version", ""))
        for r in seconds
    )
    evidence_dir = Path(version_dir) / "review_evidence"
    has_evidence = evidence_dir.exists() or evidence_dir.is_symlink()
    if not special and "review_provenance" not in manifest and not has_evidence:
        return []
    try:
        _require(len(seconds) == 1, "review_provenance requires exactly one LLM reviewer")
        complete = _validate(Path(version_dir), dict(manifest), seconds[0], pages)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        return [Finding("PR-09", "error", f"invalid review provenance: {exc}", "manifest.json/review_provenance")]
    if not complete:
        return [
            Finding(
                "PR-09",
                "warning",
                "page texts unavailable: current input and actual prompt hashes were not reconstructed; PR-05 blocks frozen validation",
                "manifest.json/review_provenance",
            )
        ]
    return []
