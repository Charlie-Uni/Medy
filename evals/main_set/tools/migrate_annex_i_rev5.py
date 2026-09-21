"""One-off (2026-09-22, record 50 §11): move the GVP Annex I samples from the superseded Rev 4 to Rev 5.

Rev 5 was ingested as the successor of Rev 4 through the publish flow, so the family now reads
synthetic-old (archived) -> Rev 4 (archived) -> Rev 5 (active): a real revision pair. This script replaces the
corpus record, re-anchors every sample whose gold lies in Rev 4 on the Rev 5 page text (key_text must be unique on
exactly one page, the span must locate there), rewrites the conflict blocks (synthetic=false, all archived keys),
moves the no-answer sample's scope and re-runs its absence check, and updates conflict_fixtures/fixtures.json.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import jsonschema

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402
import draft_llm  # noqa: E402
from draft_noanswer import term_hits  # noqa: E402

OLD_KEY, NEW_KEY = "ema-gvp-annex-i-rev4", "ema-gvp-annex-i-rev5"
FIX = json.loads((dc.MAIN / "version_fixes/gvp-annex-i-rev5.json").read_text(encoding="utf-8"))["documents"][0]
NEW = {k: v for k, v in FIX.items() if k != "replaces_source_hash"}
OLD_SHA, NEW_SHA = FIX["replaces_source_hash"], FIX["source_hash"]
FAMILY = [NEW_KEY, OLD_KEY, f"{OLD_KEY}--synthetic-old"]
NOTE = (
    "真实修订对（记录 50 §11）：GVP Annex I Rev 4（EMA/876333/2011 Rev 4，PDF 页眉标注 superseded）经 M1-11 发布流程被 Rev 5（2024-07-26）替代并归档，"
    "family 中另有 Rev 4 的合成旧版 ema-gvp-annex-i-rev4--synthetic-old（正文与 Rev 4 相同，2026-09-21 归档）；gold 落在现行版 Rev 5，检验版本状态与时效过滤（INV-DATA-03）。"
)


def find_page(key: str) -> list[int]:
    return [p for p in range(1, NEW["pages"] + 1) if (dc.page_text(NEW_SHA, p) or "").count(key) == 1]


def main() -> int:
    cp = dc.MAIN / "corpus.json"
    corpus = json.loads(cp.read_text(encoding="utf-8"))
    corpus["documents"] = [NEW if d["source_hash"] == OLD_SHA else d for d in corpus["documents"]]
    jsonschema.validate(
        corpus,
        json.loads((dc.REPO / "evals/probe/precise_clause/schema/corpus.schema.json").read_text(encoding="utf-8")),
    )
    cp.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    moved, problems = [], []
    for b in ("MA", "PV", "CO", "EN", "NA"):
        path = dc.DRAFTS / f"samples_draft_{b}.json"
        arr = json.loads(path.read_text(encoding="utf-8"))
        for s in arr:
            for g in s["required_gold_evidence"]:
                if g["source_hash"] != OLD_SHA:
                    continue
                pages = find_page(g["key_text"])
                if len(pages) != 1:
                    problems.append(f"{s['sample_id']}: key_text unique on {len(pages)} Rev 5 pages")
                    continue
                text = dc.page_text(NEW_SHA, pages[0]) or ""
                status, pos, span = dc.locate(text, g["evidence_span"]["text"])
                if not status.startswith(("exact", "tolerant")) or g["key_text"] not in span:
                    problems.append(f"{s['sample_id']}: span {status} on Rev 5 p{pages[0]}")
                    continue
                g.update(source_hash=NEW_SHA, version_label=NEW["version_label"], page=pages[0])
                g["evidence_span"] = {"text": span, "char_start": pos, "char_end": pos + len(span)}
                s["conflict"] = {
                    "family_document_keys": FAMILY,
                    "current_document_key": NEW_KEY,
                    "clause_topic": g["section"][:200],
                    "synthetic": False,
                }
                s["notes"] = NOTE
                s["_draft"]["document_key"] = NEW_KEY
                s["_draft"]["decision"] = (
                    s["_draft"].get("decision", "") + "; gold moved to Rev 5 (record 50 §11)"
                ).lstrip("; ")
                moved.append(s["sample_id"])
            if s.get("abstention", {}).get("scope_document_key") == OLD_KEY:
                ab = s["abstention"]
                terms = list(s["_draft"].get("absence_hits", {}).keys())
                hits = {t: term_hits(t, {NEW_KEY: NEW}) for t in terms}
                present = [t for t, h in hits.items() if h.get(NEW_KEY)]
                pages, _total = draft_llm.select_pages(NEW)
                ab["scope_document_key"] = NEW_KEY
                ab["document_pages"] = pages
                ab["absence_check"] = (
                    f"absence_terms {terms} 在 {NEW_KEY} 全部 {NEW['pages']} 页 norm-v1 页文本中出现 {'0 次' if not present else '命中: ' + str(present)}"
                    f"（工具复查 {dt.date.today().isoformat()}，scope 自 Rev 4 迁至 Rev 5）"
                )[:800]
                s["_draft"]["document_key"] = NEW_KEY
                s["_draft"]["decision"] = (s["_draft"].get("decision", "") + "; scope moved to Rev 5").lstrip("; ")
                if present:
                    problems.append(f"{s['sample_id']}: absence terms now present in Rev 5: {present}")
                moved.append(s["sample_id"])
        path.write_text(json.dumps(arr, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fx_path = dc.MAIN / "conflict_fixtures/fixtures.json"
    fx = json.loads(fx_path.read_text(encoding="utf-8"))
    for f in fx["fixtures"]:
        if f["document_key"] == OLD_KEY:
            f.update(
                document_key=NEW_KEY,
                archived_document_keys=[OLD_KEY, f["synthetic_old_key"]],
                synthetic=False,
                effective_from_current="2024-07-26",
                source_hash=NEW_SHA,
                source="真实修订对：Rev 4（2017-10-09，页眉 superseded）→ Rev 5（2024-07-26）经发布流程替代；family 另含 Rev 4 的合成旧版（记录 50 §11）",
            )
    fx_path.write_text(json.dumps(fx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("moved:", moved)
    for p in problems:
        print("PROBLEM", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
