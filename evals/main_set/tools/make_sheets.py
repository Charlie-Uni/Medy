"""Turn curated drafting candidates into annotator-01 confirmation sheets and draft sample files (spec-m1 §4 step 2).

    python evals/main_set/tools/make_sheets.py

Inputs: drafts/main-v1/candidates_{MA,PV,CO}.json (from draft_llm.py verify, after manual curation of the
`_draft.selected` flags), candidates_NA.json (from draft_noanswer.py verify), conflict_fixtures/fixtures.json.
Outputs: drafts/main-v1/samples_draft_{MA,PV,CO,EN,NA}.json (draft samples with stable `ms-` ids) and the
matching .md sheets (one row per sample, a 结论 column for OK / rewrite). English twins (batch EN) are derived
from every selected sample whose document is English; conflict-fixture samples carry the version_conflict slice
and the conflict block; long_context is already mechanical. Ids are assigned once and kept in ids.json so that
re-running after curation never renumbers a confirmed sample.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

from medops.evals.probe.pii import find_pii_spans  # noqa: E402

IDS = dc.DRAFTS / "ids.json"
FIXTURES = dc.MAIN / "conflict_fixtures/fixtures.json"
DRAFTER = {"kind": "llm", "id": "drafter-llm-03", "model": "claude-sonnet-5"}
DEPT_ORDER = ("MA", "PV", "CO")


def load_ids() -> dict[str, str]:
    return json.loads(IDS.read_text(encoding="utf-8")) if IDS.exists() else {}


def assign(ids: dict[str, str], handle: str) -> str:
    if handle not in ids:
        used = {int(v[3:]) for v in ids.values()}
        ids[handle] = f"ms-{(max(used) + 1 if used else 1):04d}"
    return ids[handle]


def main() -> int:
    if "--sheets-only" in sys.argv[1:]:
        # regenerate the .md sheets from the (possibly edited) JSON drafts without touching ids or selections
        for batch in ("MA", "PV", "CO", "EN", "NA"):
            path = dc.DRAFTS / f"samples_draft_{batch}.json"
            if path.exists():
                samples = json.loads(path.read_text(encoding="utf-8"))
                write_sheet(batch, samples)
                print(f"{batch}: {len(samples)} samples -> sheet regenerated")
        return 0
    corpus = dc.load_corpus()
    fixtures = (
        {f["document_key"]: f for f in json.loads(FIXTURES.read_text(encoding="utf-8"))["fixtures"]}
        if FIXTURES.exists()
        else {}
    )
    ids = load_ids()
    batches: dict[str, list[dict]] = {b: [] for b in ("MA", "PV", "CO", "EN", "NA")}
    for dept in DEPT_ORDER:
        path = dc.DRAFTS / f"candidates_{dept}.json"
        if not path.exists():
            continue
        for c in json.loads(path.read_text(encoding="utf-8")):
            d = c["_draft"]
            if d["status"] != "ok" or not d.get("selected"):
                continue
            pii = [
                (field, rule, match)
                for field, text in (("query", c["query"]), ("query_en", d.get("query_en") or ""))
                for rule, match, _s, _e in find_pii_spans(text)
            ]
            if pii:  # PR-07 allows no exception on query fields: the candidate is not selectable
                print(f"skip {d['document_key']}#{d['rank']}: PII in {pii[0][0]} ({pii[0][1]})")
                continue
            handle = f"{d['document_key']}#{d['rank']}"
            sid = assign(ids, handle)
            doc = corpus[d["document_key"]]
            gold = dict(c["required_gold_evidence"][0], gold_id=f"{sid}-g1")
            slices, curation = curate_slices(c)
            sample = {
                "sample_id": sid,
                "query": c["query"],
                "dept": c["dept"],
                "language": c["language"],
                "slices": slices,
                "required_gold_evidence": [gold],
                "notes": c.get("notes", ""),
                "drafted_by": DRAFTER,
                "_draft": {
                    **{
                        k: d[k]
                        for k in ("document_key", "title", "rank", "warnings", "rationale", "key_status", "span_status")
                    },
                    "curation": curation,
                },
            }
            fx = fixtures.get(d["document_key"])
            if fx:
                sample["slices"] = slices + ["version_conflict"]
                sample["conflict"] = {
                    "family_document_keys": [fx["document_key"], fx["synthetic_old_key"]],
                    "current_document_key": fx["document_key"],
                    "clause_topic": gold["section"][:200],
                    "synthetic": True,
                }
                sample["notes"] = (
                    f"合成冲突（spec-m1 §5）：{fx['synthetic_old_key']} 为同一 PDF 的合成旧版（effective_from {fx['effective_from_old']}），"
                    f"发布现行版（effective_from {fx['effective_from_current']}）时归档；正文相同，检验版本状态与时效过滤（INV-DATA-03），不检验内容差异。"
                )
            batches[dept].append(sample)
            if doc["language"] == "en" and d.get("query_en"):
                tid = assign(ids, handle + "#en")
                twin = json.loads(json.dumps(sample, ensure_ascii=False))
                twin.update(sample_id=tid, query=d["query_en"], language="en", derived_from=sid)
                twin["required_gold_evidence"][0]["gold_id"] = f"{tid}-g1"
                twin["_draft"] = {**twin["_draft"], "parent_query": sample["query"]}
                batches["EN"].append(twin)
    na_path = dc.DRAFTS / "candidates_NA.json"
    if na_path.exists():
        for c in json.loads(na_path.read_text(encoding="utf-8")):
            d = c["_draft"]
            if d["status"] != "ok" or not d.get("selected"):
                continue
            sid = assign(ids, f"NA:{d['document_key']}#{d['rank']}")
            sample = {k: v for k, v in c.items() if k != "_draft"}
            sample["sample_id"] = sid
            sample["drafted_by"] = DRAFTER
            sample["_draft"] = {
                k: d[k]
                for k in ("document_key", "title", "rank", "warnings", "rationale", "absence_hits", "nearest_clause")
            }
            batches["NA"].append(sample)
    IDS.write_text(json.dumps(ids, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for batch, samples in batches.items():
        samples.sort(key=lambda s: s["sample_id"])
        (dc.DRAFTS / f"samples_draft_{batch}.json").write_text(
            json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_sheet(batch, samples)
        print(f"{batch}: {len(samples)} samples; slices {dict(Counter(sl for s in samples for sl in s['slices']))}")
    return 0


def curate_slices(c: dict) -> tuple[list[str], list[str]]:
    """Mechanical curation before the annotator sees the sheet (P3): `protocol_id` is kept only when the query
    actually contains an identifier pattern; other advisory warnings stay visible for the human decision."""
    slices = list(c["slices"])
    curation = []
    if "protocol_id" in slices and any(w.startswith("protocol_id:") for w in c["_draft"]["warnings"]):
        if len(slices) > 1:
            slices.remove("protocol_id")
            curation.append("dropped protocol_id: query carries no identifier (P3)")
        else:
            curation.append("protocol_id kept as the only slice; annotator must decide")
    return slices, curation


def cell(text: str, limit: int = 160) -> str:
    t = str(text).replace("|", "\\|").replace("\n", " ")
    return t[:limit] + ("…" if len(t) > limit else "")


def write_sheet(batch: str, samples: list[dict]) -> None:
    lines = [f"# 主评测集 main-v1 样本草稿：{batch} 批次（{len(samples)} 条，待 annotator-01 逐条确认）", ""]
    if batch == "NA":
        lines += [
            "> 每条请判断四件事：问题在范围内且自然；文档确实没有回答（工具已核查 absence_terms 在该文档全部页文本中缺席；`nearest_clause` 是起草者给出的最接近条款）；切片；部门。",
            "> 确认方式：在「结论」列填 OK，或直接改写 query / topic；要删除的写 DROP。",
            "",
            "| ID | 文档 | 切片 | query | topic | absence_terms（语料内命中文档数） | nearest_clause | 结论 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in samples:
            d = s["_draft"]
            hits = "; ".join(f"{t}({n})" for t, n in d["absence_hits"].items())
            nc = d.get("nearest_clause") or {}
            nc_cell = f"p{nc.get('page')}: {cell(nc.get('text', ''), 120)}" if nc else "—"
            lines.append(
                f"| {s['sample_id']} | {d['document_key']} | {', '.join(s['slices'])} | {cell(s['query'], 200)} | {cell(s['abstention']['topic'], 40)} | {cell(hits, 120)} | {nc_cell} | {cell(d.get('decision', ''), 60)} |"
            )
    elif batch == "EN":
        lines += [
            "> 孪生样本：gold、部门、切片继承自父样本，只需判断英文问法是否与父样本问同一件事、限定条件一致、英文自然。",
            "> 确认方式：在「结论」列填 OK，或直接改写英文 query；要删除的写 DROP。",
            "",
            "| ID | 父样本 | 文档 | 页 | 切片 | 父样本中文问题 | 英文问题 | key_text（预览） | 结论 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in samples:
            g = s["required_gold_evidence"][0]
            lines.append(
                f"| {s['sample_id']} | {s['derived_from']} | {s['_draft']['document_key']} | {g['page']} | {', '.join(s['slices'])} | {cell(s['_draft']['parent_query'], 200)} | {cell(s['query'], 200)} | {cell(g['key_text'], 100)} | {cell(s['_draft'].get('decision', ''), 60)} |"
            )
    else:
        lines += [
            "> 每条请判断五件事：问题自然且只有这一句能回答；key_text 最短且页内唯一（工具已核对唯一）；span 是完整条款；切片标签；部门归属。",
            "> 确认方式：在「结论」列填 OK，或直接改写 query / key_text / span / slices；要删除的写 DROP；改动的条目我重新计算偏移并复核唯一性。「结论」列已预填的内容是外部审校（ChatGPT，2026-09-21）已应用的状态，覆盖即可。",
            "> 带 `version_conflict` 的样本来自合成冲突 fixture（同一 PDF 的旧版已归档），只需按普通样本判断。",
            "",
            "| ID | 文档 | 页 | 切片 | query | key_text | evidence_span | 章节 | 工具提示 | 结论 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in samples:
            g = s["required_gold_evidence"][0]
            warn = "; ".join(s["_draft"].get("curation", []) + s["_draft"]["warnings"]) or "—"
            lines.append(
                f"| {s['sample_id']} | {s['_draft']['document_key']} | {g['page']} | {', '.join(s['slices'])} | {cell(s['query'], 200)} | {cell(g['key_text'], 120)} | {cell(g['evidence_span']['text'], 160)} | {cell(g['section'], 40)} | {cell(warn, 80)} | {cell(s['_draft'].get('decision', ''), 60)} |"
            )
    by_slice = Counter(sl for s in samples for sl in s["slices"])
    lines += [
        "",
        f"切片计数：{dict(by_slice)}；部门：{dict(Counter(s['dept'] for s in samples))}；语言：{dict(Counter(s['language'] for s in samples))}",
        "",
    ]
    (dc.DRAFTS / f"samples_draft_{batch}.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
