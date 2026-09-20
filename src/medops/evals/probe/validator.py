"""Probe set validator implementing PR-01 .. PR-15 of evals/probe/precise_clause/SPEC.md.

A version directory holds manifest.json, corpus.json, samples.jsonl, review_prompt.md and
optionally acl_probes.jsonl, SHA256SUMS and mappings/. Page texts for PR-05 are read from a
local, never-committed directory laid out as <pages_dir>/<source_hash>/<page>.txt containing
the raw extractor output for that page; the validator applies norm-v1 itself.

Modes: `draft` reports count shortfalls and missing page texts as warnings; `frozen` treats
every rule as an error and additionally runs the PR-10 and PR-12 integrity checks.
Parsing failures never raise; they are reported as PR-01 findings with file and line.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker

from medops.core.canonical import canonical_json, sha256_hex
from medops.evals.probe.pii import PII_RULESET_VERSION, find_pii_spans
from medops.evals.probe.review_provenance import validate_review_provenance
from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, normalize_text

Mode = Literal["draft", "frozen"]
Level = Literal["error", "warning"]
SLICES = ("drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en")
DEPTS = ("MA", "PV", "CO")
LANGS = ("zh-Hans", "zh-Hant", "en", "mixed")
REQUIRED_FILES = ("manifest.json", "corpus.json", "samples.jsonl", "review_prompt.md")
PII_EXCEPTIONS_FILE = "pii_exceptions.json"
SUMS_FILES = ("corpus.json", "samples.jsonl", "review_prompt.md", "acl_probes.jsonl", PII_EXCEPTIONS_FILE)
_SUMS_LINE = re.compile(r"^([0-9a-f]{64})  (\S+)$")


@dataclass(frozen=True)
class Finding:
    rule: str
    level: Level
    message: str
    location: str = ""


@dataclass
class ValidationReport:
    mode: Mode
    version_dir: str
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "version_dir": self.version_dir,
            "passed": self.passed,
            "counts": self.counts,
            "findings": [f.__dict__ for f in self.findings],
        }


Add = Callable[[Finding], None]


class PageTextProvider:
    """Reads raw page text from <root>/<source_hash>/<page>.txt and normalizes it (norm-v1)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def page_text(self, source_hash: str, page: int) -> str | None:
        path = self.root / source_hash / f"{page}.txt"
        if not path.is_file():
            return None
        return normalize_text(path.read_text(encoding="utf-8"))


class ProbeSetValidator:
    def __init__(
        self, schema_dir: Path, pages: PageTextProvider | None = None, *, approval_records_root: Path | None = None
    ) -> None:
        self.schema_dir = Path(schema_dir)
        self.pages = pages
        self.approval_records_root = (
            Path(approval_records_root) if approval_records_root is not None else Path(__file__).resolve().parents[4]
        ).resolve()
        self._schemas: dict[str, Draft202012Validator] = {}
        for name in ("manifest", "corpus", "probe_sample", "acl_probe", "chunk_mapping", "pii_exceptions"):
            schema = json.loads((self.schema_dir / f"{name}.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self._schemas[name] = Draft202012Validator(schema, format_checker=FormatChecker())

    # ---------------------------------------------------------------- entry
    def validate(self, version_dir: Path, mode: Mode = "draft") -> ValidationReport:
        version_dir = Path(version_dir)
        report = ValidationReport(mode=mode, version_dir=str(version_dir))
        add = report.findings.append

        for name in REQUIRED_FILES:
            if not (version_dir / name).is_file():
                add(Finding("PR-01", "error", f"missing required file {name}", name))
        if report.errors:
            return report

        manifest = self._load_json(version_dir / "manifest.json", add)
        corpus = self._load_json(version_dir / "corpus.json", add)
        samples = self._load_jsonl(version_dir / "samples.jsonl", add)
        exceptions = None
        has_exceptions = (version_dir / PII_EXCEPTIONS_FILE).exists()
        if has_exceptions:
            exceptions = self._load_json(version_dir / PII_EXCEPTIONS_FILE, add, reject_duplicate_keys=True)
        acl_probes: list[dict[str, Any]] = []
        if (version_dir / "acl_probes.jsonl").is_file():
            acl_probes = self._load_jsonl(version_dir / "acl_probes.jsonl", add)
        mappings = {}
        for path in sorted((version_dir / "mappings").glob("chunk_mapping.*.json")):
            loaded = self._load_json(path, add)
            if loaded is not None:
                mappings[path.name] = loaded
        if report.errors or manifest is None or corpus is None:
            return report

        self._pr01_schemas(manifest, corpus, samples, acl_probes, mappings, add)
        if has_exceptions:
            for err in self._schemas["pii_exceptions"].iter_errors(exceptions):
                add(
                    Finding(
                        "PR-01",
                        "error",
                        f"invalid PII exception structure ({err.validator})",
                        PII_EXCEPTIONS_FILE + "/" + "/".join(map(str, err.path)),
                    )
                )
        if report.errors:
            return report  # structural errors make the remaining rules meaningless

        docs = self._pr01_corpus_index(manifest, corpus, add)
        self._pr02_ids(samples, acl_probes, add)
        report.counts = self._pr03_counts(manifest, samples, docs, mode, add)
        self._pr04_corpus_refs(samples, docs, mode, add)
        self._pr05_anchoring(samples, mode, add)
        self._pr06_dept(samples, docs, add)
        self._pr07_pii(manifest, samples, add, exceptions=exceptions, version_dir=version_dir)
        self._pr08_queries(samples, add)
        self._pr09_review(manifest, samples, version_dir, add)
        report.findings.extend(validate_review_provenance(version_dir, manifest, pages=self.pages))
        self._pr11_language(samples, add)
        self._pr15_derived(manifest, samples, docs, add)
        self._pr13_corpus_license(manifest, corpus, mode, add)
        self._pr14_selfcheck(manifest, add)
        if mode == "frozen":
            self._pr10_frozen(manifest, version_dir, add)
            self._pr12_mappings(manifest, samples, mappings, add)
        return report

    # ---------------------------------------------------------------- loading
    @staticmethod
    def _load_json(path: Path, add: Add, *, reject_duplicate_keys: bool = False) -> Any | None:
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON property")
                result[key] = value
            return result

        try:
            return json.loads(
                path.read_bytes().decode("utf-8"), object_pairs_hook=unique_object if reject_duplicate_keys else None
            )
        except UnicodeDecodeError as exc:
            add(Finding("PR-01", "error", f"not valid UTF-8: {exc.reason} at byte {exc.start}", path.name))
        except json.JSONDecodeError as exc:
            add(Finding("PR-01", "error", f"invalid JSON: {exc.msg}", f"{path.name}:{exc.lineno}"))
        except (OSError, ValueError) as exc:
            add(Finding("PR-01", "error", f"cannot load JSON: {exc}", path.name))
        return None

    @staticmethod
    def _load_jsonl(path: Path, add: Add) -> list[dict[str, Any]]:
        """Strict JSONL: UTF-8, LF, no blank lines, trailing newline, every line canonical JSON."""
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            add(Finding("PR-01", "error", f"not valid UTF-8: {exc.reason} at byte {exc.start}", path.name))
            return []
        if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
            add(Finding("PR-01", "error", "must be UTF-8 without BOM and use LF line endings", path.name))
        if not raw.endswith(b"\n"):
            add(Finding("PR-01", "error", "must end with a newline", path.name))
        records: list[dict[str, Any]] = []
        for lineno, line in enumerate(text.split("\n")[:-1] if text.endswith("\n") else text.split("\n"), start=1):
            if not line.strip():
                add(Finding("PR-01", "error", "blank line is not allowed in JSONL", f"{path.name}:{lineno}"))
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                add(Finding("PR-01", "error", f"invalid JSON: {exc.msg}", f"{path.name}:{lineno}"))
                continue
            if not isinstance(obj, dict):
                add(Finding("PR-01", "error", "each JSONL line must be an object", f"{path.name}:{lineno}"))
                continue
            try:
                if canonical_json(obj) != line:
                    add(
                        Finding(
                            "PR-01",
                            "error",
                            "line is not canonical JSON (sorted keys, compact, ensure_ascii=false)",
                            f"{path.name}:{lineno}",
                        )
                    )
            except (TypeError, ValueError) as exc:
                add(Finding("PR-01", "error", f"not canonicalizable: {exc}", f"{path.name}:{lineno}"))
            records.append(obj)
        return records

    # ---------------------------------------------------------------- rules
    def _pr01_schemas(self, manifest, corpus, samples, acl_probes, mappings, add: Add) -> None:
        def check(name: str, instance: Any, where: str) -> None:
            for err in self._schemas[name].iter_errors(instance):
                add(Finding("PR-01", "error", err.message[:200], where + "/" + "/".join(map(str, err.path))))

        check("manifest", manifest, "manifest.json")
        check("corpus", corpus, "corpus.json")
        for i, sample in enumerate(samples, start=1):
            check("probe_sample", sample, f"samples.jsonl:{i}")
        for i, probe in enumerate(acl_probes, start=1):
            check("acl_probe", probe, f"acl_probes.jsonl:{i}")
        for name, mapping in mappings.items():
            check("chunk_mapping", mapping, name)

    def _pr01_corpus_index(self, manifest, corpus, add: Add) -> dict[str, dict[str, Any]]:
        """Cross-file structure: corpus version equals manifest version; hashes and keys unique."""
        if corpus["dataset_version"] != manifest["dataset_version"]:
            add(
                Finding(
                    "PR-01",
                    "error",
                    f"corpus dataset_version {corpus['dataset_version']} != manifest {manifest['dataset_version']}",
                    "corpus.json/dataset_version",
                )
            )
        docs: dict[str, dict[str, Any]] = {}
        keys: set[str] = set()
        for d in corpus["documents"]:
            if d["source_hash"] in docs:
                add(Finding("PR-01", "error", f"duplicate source_hash {d['source_hash'][:12]}", d["document_key"]))
                continue
            if d["document_key"] in keys:
                add(Finding("PR-01", "error", f"duplicate document_key {d['document_key']}", d["document_key"]))
            keys.add(d["document_key"])
            docs[d["source_hash"]] = d
        return docs

    def _pr02_ids(self, samples, acl_probes, add: Add) -> None:
        ids = [s["sample_id"] for s in samples]
        if len(set(ids)) != len(ids):
            add(Finding("PR-02", "error", "sample_id values are not unique", "samples.jsonl"))
        if ids != sorted(ids):
            add(Finding("PR-02", "error", "samples.jsonl is not sorted by sample_id", "samples.jsonl"))
        for s in samples:
            gold_ids = [g["gold_id"] for g in s["required_gold_evidence"]]
            if len(set(gold_ids)) != len(gold_ids):
                add(Finding("PR-02", "error", "gold_id values repeat within a sample", s["sample_id"]))
            for gid in gold_ids:
                if not gid.startswith(s["sample_id"] + "-g"):
                    add(Finding("PR-02", "error", f"gold_id {gid} does not carry the sample_id prefix", s["sample_id"]))
        pids = [p["probe_id"] for p in acl_probes]
        if len(set(pids)) != len(pids):
            add(Finding("PR-02", "error", "probe_id values are not unique", "acl_probes.jsonl"))
        if pids != sorted(pids):
            add(Finding("PR-02", "error", "acl_probes.jsonl is not sorted by probe_id", "acl_probes.jsonl"))
        sample_ids = set(ids)
        for p in acl_probes:
            ref = p.get("derived_from_sample")
            if ref is not None and ref not in sample_ids:
                add(Finding("PR-02", "error", f"derived_from_sample {ref} does not exist", p["probe_id"]))

    @staticmethod
    def _sample_language(sample, docs) -> str:
        langs = {
            docs[g["source_hash"]]["language"] for g in sample["required_gold_evidence"] if g["source_hash"] in docs
        }
        return langs.pop() if len(langs) == 1 else "mixed"

    def _pr03_counts(self, manifest, samples, docs, mode: Mode, add: Add) -> dict[str, Any]:
        level: Level = "error" if mode == "frozen" else "warning"
        mins = manifest["minimums"]
        per_slice = Counter(sl for s in samples for sl in s["slices"])
        per_dept = Counter(s["dept"] for s in samples)
        per_language = Counter(self._sample_language(s, docs) for s in samples)
        actual: dict[str, Any] = {
            "samples": len(samples),
            "documents": len(docs),
            "per_slice": {k: per_slice.get(k, 0) for k in SLICES},
            "per_dept": {k: per_dept.get(k, 0) for k in DEPTS},
            "per_language": {k: per_language.get(k, 0) for k in LANGS},
        }
        if len(samples) < mins["samples"]:
            add(Finding("PR-03", level, f"{len(samples)} samples < minimum {mins['samples']}"))
        for k in SLICES:
            if actual["per_slice"][k] < mins["per_slice"]:
                add(Finding("PR-03", level, f"slice {k} has {actual['per_slice'][k]} < {mins['per_slice']}"))
        for k in DEPTS:
            if actual["per_dept"][k] < mins["per_dept"]:
                add(Finding("PR-03", level, f"dept {k} has {actual['per_dept'][k]} < {mins['per_dept']}"))
        if actual["per_language"]["zh-Hans"] < mins["zh_hans_samples"]:
            add(
                Finding(
                    "PR-03", level, f"zh-Hans samples {actual['per_language']['zh-Hans']} < {mins['zh_hans_samples']}"
                )
            )
        if manifest["counts"] != actual:
            add(
                Finding(
                    "PR-03", "error", f"manifest.counts {manifest['counts']} != actual {actual}", "manifest.json/counts"
                )
            )
        return actual

    def _pr04_corpus_refs(self, samples, docs, mode: Mode, add: Add) -> None:
        level: Level = "error" if mode == "frozen" else "warning"
        per_doc: Counter[str] = Counter()
        for s in samples:
            for g in s["required_gold_evidence"]:
                doc = docs.get(g["source_hash"])
                if doc is None:
                    add(
                        Finding("PR-04", "error", f"gold {g['gold_id']} references unknown source_hash", s["sample_id"])
                    )
                    continue
                if g["version_label"] != doc["version_label"]:
                    add(
                        Finding(
                            "PR-04",
                            "error",
                            f"gold version_label {g['version_label']!r} != document {doc['version_label']!r}",
                            g["gold_id"],
                        )
                    )
                if g["page"] > doc["pages"]:
                    add(
                        Finding(
                            "PR-04",
                            "error",
                            f"gold page {g['page']} exceeds document pages {doc['pages']}",
                            g["gold_id"],
                        )
                    )
            for h in {g["source_hash"] for g in s["required_gold_evidence"]}:
                per_doc[h] += 1
        for h, n in per_doc.items():
            if n > 6:
                add(Finding("PR-04", "error", f"document {h[:12]} contributes {n} samples > 6"))
        if len(docs) < 10:
            add(Finding("PR-04", level, f"{len(docs)} documents < minimum 10"))
        docs_per_dept = Counter(d["owner_dept"] for d in docs.values())
        for k in DEPTS:
            if docs_per_dept.get(k, 0) < 3:
                add(Finding("PR-04", level, f"dept {k} has {docs_per_dept.get(k, 0)} documents < 3"))

    def _pr05_anchoring(self, samples, mode: Mode, add: Add) -> None:
        """Page-independent checks always run; page-text checks run when texts are available."""
        missing_level: Level = "error" if mode == "frozen" else "warning"
        if self.pages is None:
            add(Finding("PR-05", missing_level, "page texts not provided; page anchoring not verified"))
        for s in samples:
            for g in s["required_gold_evidence"]:
                loc = g["gold_id"]
                key, span = g["key_text"], g["evidence_span"]
                if key != normalize_text(key):
                    add(Finding("PR-05", "error", "key_text is not in norm-v1 form", loc))
                if span["text"] != normalize_text(span["text"]):
                    add(Finding("PR-05", "error", "evidence_span.text is not in norm-v1 form", loc))
                if key not in span["text"]:
                    add(Finding("PR-05", "error", "evidence_span.text does not contain key_text", loc))
                if span["char_end"] - span["char_start"] != len(span["text"]):
                    add(Finding("PR-05", "error", "evidence_span offsets do not match text length", loc))
                if self.pages is None:
                    continue
                page_text = self.pages.page_text(g["source_hash"], g["page"])
                if page_text is None:
                    add(
                        Finding(
                            "PR-05", missing_level, f"page text missing for {g['source_hash'][:12]} p{g['page']}", loc
                        )
                    )
                    continue
                occurrences = page_text.count(key)
                if occurrences != 1:
                    add(
                        Finding(
                            "PR-05", "error", f"key_text occurs {occurrences} times on page (must be exactly 1)", loc
                        )
                    )
                if page_text[span["char_start"] : span["char_end"]] != span["text"]:
                    add(
                        Finding(
                            "PR-05", "error", "page text at evidence_span offsets differs from evidence_span.text", loc
                        )
                    )

    def _pr06_dept(self, samples, docs, add: Add) -> None:
        for s in samples:
            for g in s["required_gold_evidence"]:
                doc = docs.get(g["source_hash"])
                if doc and doc["owner_dept"] != s["dept"]:
                    add(
                        Finding(
                            "PR-06",
                            "error",
                            f"sample dept {s['dept']} != document owner_dept {doc['owner_dept']}",
                            g["gold_id"],
                        )
                    )

    def _pr07_pii(self, manifest, samples, add: Add, *, exceptions=None, version_dir: Path | None = None) -> None:
        if manifest["pii_ruleset_version"] != PII_RULESET_VERSION:
            add(
                Finding(
                    "PR-07",
                    "error",
                    f"unsupported pii_ruleset_version {manifest['pii_ruleset_version']} (validator implements {PII_RULESET_VERSION})",
                    "manifest.json",
                )
            )
        allowed = self._pii_exception_keys(manifest, exceptions, version_dir, add)
        consumed: set[tuple] = set()
        for s in samples:
            texts = [("query", "", "", s["query"]), ("notes", "", "", s["notes"])]
            for g in s["required_gold_evidence"]:
                texts.extend(
                    [
                        ("key_text", g["gold_id"], g["source_hash"], g["key_text"]),
                        ("evidence_span.text", g["gold_id"], g["source_hash"], g["evidence_span"]["text"]),
                    ]
                )
            for field_name, gold_id, source_hash, text in texts:
                field_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                for rule, match, start, end in find_pii_spans(text):
                    key = (s["sample_id"], gold_id, source_hash, field_name, field_hash, rule, match, start, end)
                    where = "/".join(x for x in (s["sample_id"], gold_id, field_name) if x)
                    if key in allowed and key not in consumed:
                        consumed.add(key)
                    else:
                        add(
                            Finding(
                                "PR-07",
                                "error",
                                f"PII pattern {rule} matched at [{start}, {end}) without an exact reviewed exception",
                                where,
                            )
                        )
        for key in allowed - consumed:
            add(
                Finding(
                    "PR-07",
                    "error",
                    "unused or stale PII exception does not match a current hit",
                    f"{PII_EXCEPTIONS_FILE}/{key[0]}/{key[1]}/{key[3]}",
                )
            )

    def _pii_exception_keys(self, manifest, exceptions, version_dir: Path | None, add: Add) -> set[tuple]:
        """Exceptions are explicit human decisions, never inferred from sample or corpus notes."""
        files = [f for f in manifest["files"] if f["path"] == PII_EXCEPTIONS_FILE]
        if exceptions is None:
            if files:
                add(Finding("PR-07", "error", "manifest declares a missing PII exception file", PII_EXCEPTIONS_FILE))
            return set()
        if (
            version_dir is None
            or len(files) != 1
            or files[0]["sha256"] != hashlib.sha256((version_dir / PII_EXCEPTIONS_FILE).read_bytes()).hexdigest()
        ):
            add(
                Finding(
                    "PR-07", "error", "PII exception file must be hash-bound in manifest.files", PII_EXCEPTIONS_FILE
                )
            )
            return set()
        if (
            exceptions["dataset_version"] != manifest["dataset_version"]
            or exceptions["pii_ruleset_version"] != manifest["pii_ruleset_version"]
        ):
            add(Finding("PR-07", "error", "PII exception dataset or rule version is stale", PII_EXCEPTIONS_FILE))
            return set()
        annotator = next(
            (r["id"] for r in manifest["reviewers"] if r["role"] == "annotator" and r["kind"] == "human"), None
        )
        allowed: set[tuple] = set()
        seen: set[tuple] = set()
        for index, entry in enumerate(exceptions["exceptions"]):
            loc = f"{PII_EXCEPTIONS_FILE}/exceptions/{index}"
            review = entry["human_review"]
            key = tuple(
                entry[k]
                for k in (
                    "sample_id",
                    "gold_id",
                    "source_hash",
                    "field",
                    "field_sha256",
                    "rule",
                    "match",
                    "char_start",
                    "char_end",
                )
            )
            identity = (entry["sample_id"], entry["gold_id"], entry["field"], entry["char_start"], entry["char_end"])
            if identity in seen:
                add(Finding("PR-07", "error", "duplicate PII exception for the same hit", loc))
                continue
            seen.add(identity)
            if (
                review["reviewer_id"] != annotator
                or review["reviewed_at"] > dt.date.today().isoformat()
                or (manifest.get("frozen_at") and review["reviewed_at"] > manifest["frozen_at"])
            ):
                add(
                    Finding(
                        "PR-07",
                        "error",
                        "PII exception must be reviewed by the human annotator, not in the future or after freezing",
                        loc,
                    )
                )
                continue
            if find_pii_spans(review["reason"]):
                add(Finding("PR-07", "error", "PII exception reason must not introduce additional PII matches", loc))
                continue
            record = self.approval_records_root / review["approval_record"]
            try:
                resolved_record = record.resolve()
                if not resolved_record.is_relative_to(self.approval_records_root) or not resolved_record.is_file():
                    raise ValueError("approval record is missing or outside the approval records root")
                if hashlib.sha256(resolved_record.read_bytes()).hexdigest() != review["approval_record_sha256"]:
                    raise ValueError("approval record sha256 does not match the reviewed basis")
            except (OSError, ValueError, RuntimeError) as exc:
                add(Finding("PR-07", "error", str(exc), loc))
                continue
            allowed.add(key)
        return allowed

    def _pr08_queries(self, samples, add: Add) -> None:
        all_keys = {normalize_text(g["key_text"]) for s in samples for g in s["required_gold_evidence"]}
        seen: dict[str, str] = {}
        for s in samples:
            q = normalize_text(s["query"])
            if q in seen:
                add(Finding("PR-08", "error", f"query duplicates {seen[q]} after normalization", s["sample_id"]))
            seen[q] = s["sample_id"]
            if q in all_keys:
                add(Finding("PR-08", "error", "query equals a key_text of the set after normalization", s["sample_id"]))

    def _pr09_review(self, manifest, samples, version_dir: Path, add: Add) -> None:
        reviewers = {r["role"]: r for r in manifest["reviewers"]}
        annot, second = reviewers.get("annotator"), reviewers.get("second_reviewer")
        raw = (version_dir / "review_prompt.md").read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            add(
                Finding(
                    "PR-09",
                    "error",
                    f"review_prompt.md is not valid UTF-8: {exc.reason} at byte {exc.start}",
                    "review_prompt.md",
                )
            )
        if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
            add(
                Finding(
                    "PR-09",
                    "error",
                    "review_prompt.md must be UTF-8 without BOM, LF line endings and end with a newline",
                    "review_prompt.md",
                )
            )
        prompt_hash = hashlib.sha256(raw).hexdigest()
        if second and second.get("prompt_hash") != prompt_hash:
            add(
                Finding(
                    "PR-09",
                    "error",
                    "manifest second_reviewer.prompt_hash != sha256(review_prompt.md)",
                    "manifest.json/reviewers",
                )
            )
        policy = manifest["review_policy"]
        if not annot or annot["kind"] != "human" or not second or second["kind"] != "llm":
            add(
                Finding(
                    "PR-09",
                    "error",
                    "reviewers must be exactly one human annotator and one llm second_reviewer",
                    "manifest.json/reviewers",
                )
            )
        elif policy["human_reviewers"] != 1 or policy["llm_reviewers"] != 1:
            add(Finding("PR-09", "error", "review_policy inconsistent with reviewers", "manifest.json/review_policy"))
        for s in samples:
            rv = s["review"]
            if annot and rv["annotator"]["id"] != annot["id"]:
                add(Finding("PR-09", "error", "sample annotator id differs from manifest", s["sample_id"]))
            if second:
                sr = rv["second_reviewer"]
                for key in ("id", "model", "model_version", "prompt_hash"):
                    if sr.get(key) != second.get(key):
                        add(
                            Finding(
                                "PR-09", "error", f"sample second_reviewer.{key} differs from manifest", s["sample_id"]
                            )
                        )
            if rv["status"] == "disputed_resolved" and not (rv.get("resolution_note") or "").strip():
                add(Finding("PR-09", "error", "disputed_resolved requires resolution_note", s["sample_id"]))

    def _pr10_frozen(self, manifest, version_dir: Path, add: Add) -> None:
        if manifest["status"] != "frozen" or not manifest.get("frozen_at"):
            add(Finding("PR-10", "error", "frozen validation requires status=frozen and frozen_at", "manifest.json"))
        for p in version_dir.iterdir():
            if ".example." in p.name:
                add(Finding("PR-10", "error", f"example file {p.name} inside a version directory", p.name))
        sums_path = version_dir / "SHA256SUMS"
        if not sums_path.is_file():
            add(Finding("PR-10", "error", "SHA256SUMS missing", "SHA256SUMS"))
            return
        sums_raw = sums_path.read_bytes()
        try:
            lines = sums_raw.decode("utf-8").split("\n")
        except UnicodeDecodeError as exc:
            add(Finding("PR-10", "error", f"SHA256SUMS is not valid UTF-8: {exc.reason}", "SHA256SUMS"))
            return
        if not sums_raw.endswith(b"\n"):
            add(Finding("PR-10", "error", "SHA256SUMS must end with a newline", "SHA256SUMS"))
        entries: dict[str, str] = {}
        order: list[str] = []
        for lineno, line in enumerate(lines[:-1] if sums_raw.endswith(b"\n") else lines, start=1):
            m = _SUMS_LINE.match(line)
            if not m:
                add(Finding("PR-10", "error", "malformed line (expected '<64 hex>  <path>')", f"SHA256SUMS:{lineno}"))
                continue
            digest, name = m.group(1), m.group(2)
            if name in entries:
                add(Finding("PR-10", "error", f"duplicate path {name}", f"SHA256SUMS:{lineno}"))
                continue
            if name not in SUMS_FILES:
                add(Finding("PR-10", "error", f"unexpected path {name}", f"SHA256SUMS:{lineno}"))
                continue
            entries[name] = digest
            order.append(name)
        expected = [n for n in SUMS_FILES if (version_dir / n).is_file()]
        if order != sorted(order):
            add(Finding("PR-10", "error", "SHA256SUMS lines must be sorted by path", "SHA256SUMS"))
        if set(order) != set(expected):
            add(Finding("PR-10", "error", f"SHA256SUMS must list exactly {sorted(expected)}", "SHA256SUMS"))
        for name, digest in entries.items():
            path = version_dir / name
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                add(Finding("PR-10", "error", f"SHA256SUMS digest mismatch for {name}", name))
        manifest_files = {f["path"]: f["sha256"] for f in manifest["files"]}
        if manifest_files != entries:
            add(
                Finding(
                    "PR-10", "error", "manifest.files differs from SHA256SUMS (paths or digests)", "manifest.json/files"
                )
            )
        if manifest.get("dataset_hash") != hashlib.sha256(sums_raw).hexdigest():
            add(Finding("PR-10", "error", "dataset_hash != sha256(SHA256SUMS bytes)", "manifest.json/dataset_hash"))

    def _pr11_language(self, samples, add: Add) -> None:
        for s in samples:
            if "mixed_zh_en" in s["slices"] and s["language"] != "mixed" and not s.get("derived_from"):
                # spec-v1.1: derived English twins inherit the parent's slices for comparability (PR-15)
                add(Finding("PR-11", "error", "mixed_zh_en samples must have language=mixed", s["sample_id"]))
            if s["language"] == "en" and "drug_name_zh" in s["slices"]:
                add(Finding("PR-11", "error", "language=en samples must not carry drug_name_zh", s["sample_id"]))

    def _pr15_derived(self, manifest, samples, docs, add: Add) -> None:
        """spec-v1.1 derived English twins: same gold (new gold_id prefix), dept and slices as a confirmed
        parent whose gold document is English; language=en; count matches manifest.derived_samples."""
        by_id = {s["sample_id"]: s for s in samples}
        derived = [s for s in samples if s.get("derived_from")]
        declared = manifest.get("derived_samples")
        if manifest["spec_version"] == "spec-v1":
            if derived or declared:
                add(Finding("PR-15", "error", "derived samples require spec-v1.1", "manifest.json/spec_version"))
            return
        if declared is None:
            if derived:
                add(
                    Finding(
                        "PR-15",
                        "error",
                        "derived samples present but manifest.derived_samples missing",
                        "manifest.json",
                    )
                )
            return
        if declared["count"] != len(derived):
            add(
                Finding(
                    "PR-15",
                    "error",
                    f"manifest.derived_samples.count {declared['count']} != actual {len(derived)}",
                    "manifest.json/derived_samples",
                )
            )
        for s in derived:
            loc = s["sample_id"]
            parent = by_id.get(s["derived_from"])
            if parent is None or parent.get("derived_from"):
                add(Finding("PR-15", "error", "derived_from must name an existing non-derived sample", loc))
                continue
            if s["language"] != "en":
                add(Finding("PR-15", "error", "derived twins must have language=en", loc))
            if s["dept"] != parent["dept"] or list(s["slices"]) != list(parent["slices"]):
                add(Finding("PR-15", "error", "derived twins must inherit dept and slices unchanged", loc))
            if len(s["required_gold_evidence"]) != len(parent["required_gold_evidence"]):
                add(Finding("PR-15", "error", "derived twins must carry the same number of golds", loc))
                continue
            for mine, theirs in zip(s["required_gold_evidence"], parent["required_gold_evidence"], strict=True):
                if {k: v for k, v in mine.items() if k != "gold_id"} != {
                    k: v for k, v in theirs.items() if k != "gold_id"
                }:
                    add(Finding("PR-15", "error", "derived twin gold differs from the parent gold", loc))
                if theirs["source_hash"] in docs and docs[theirs["source_hash"]]["language"] != "en":
                    add(Finding("PR-15", "error", "derived twins are only allowed for English gold documents", loc))
            if normalize_text(s["query"]) == normalize_text(parent["query"]):
                add(Finding("PR-15", "error", "derived twin query equals the parent query", loc))

    def _pr12_mappings(self, manifest, samples, mappings, add: Add) -> None:
        gold_ids = {g["gold_id"] for s in samples for g in s["required_gold_evidence"]}
        ext = manifest["extraction"]
        for name, mapping in mappings.items():
            if mapping["dataset_version"] != manifest["dataset_version"] or mapping["dataset_hash"] != manifest.get(
                "dataset_hash"
            ):
                add(Finding("PR-12", "error", "mapping dataset_version/dataset_hash differ from manifest", name))
            mext = mapping["extraction"]
            for key in ("extractor", "extractor_version", "params_hash"):
                if mext.get(key) != ext.get(key):
                    add(
                        Finding(
                            "PR-12",
                            "error",
                            f"mapping extraction.{key} {mext.get(key)!r} != manifest {ext.get(key)!r}",
                            name,
                        )
                    )
            if mapping["normalization"] != manifest["normalization"]:
                add(Finding("PR-12", "error", "mapping normalization differs from manifest", name))
            seen = Counter(e["gold_id"] for e in mapping["entries"])
            missing, extra = gold_ids - set(seen), set(seen) - gold_ids
            dup = [g for g, n in seen.items() if n > 1]
            if missing or extra or dup:
                add(
                    Finding(
                        "PR-12",
                        "error",
                        f"mapping must have exactly one entry per gold (missing={len(missing)}, extra={len(extra)}, duplicate={len(dup)})",
                        name,
                    )
                )

    def _pr13_corpus_license(self, manifest, corpus, mode: Mode, add: Add) -> None:
        frozen_at = manifest.get("frozen_at")
        pv_docs = [d for d in corpus["documents"] if d["owner_dept"] == "PV"]
        for d in corpus["documents"]:
            if frozen_at and d["license_or_terms"]["verified_at"] > frozen_at:
                add(Finding("PR-13", "error", "license verified_at is later than frozen_at", d["document_key"]))
        keys = {d["document_key"] for d in pv_docs}
        hashes = {d["source_hash"] for d in pv_docs}
        if len(pv_docs) < 3 or len(keys) < 3 or len(hashes) < 3:
            add(
                Finding(
                    "PR-13",
                    "error" if mode == "frozen" else "warning",
                    f"PV needs >= 3 independent documents, found {len(pv_docs)}",
                )
            )

    def _pr14_selfcheck(self, manifest, add: Add) -> None:
        if manifest["normalization"] != NORMALIZATION_VERSION:
            add(
                Finding(
                    "PR-14",
                    "error",
                    f"manifest normalization {manifest['normalization']} != validator {NORMALIZATION_VERSION}",
                    "manifest.json",
                )
            )
        ext = manifest["extraction"]
        if ext["params_hash"] != sha256_hex(canonical_json(ext["params"])):
            add(
                Finding(
                    "PR-14",
                    "error",
                    "extraction.params_hash != sha256(canonical_json(params))",
                    "manifest.json/extraction",
                )
            )
