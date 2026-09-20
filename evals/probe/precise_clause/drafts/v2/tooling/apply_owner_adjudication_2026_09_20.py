# -*- coding: utf-8 -*-
"""Apply annotator-01's adjudication of the 21 v2 review disputes (document supplied 2026-09-20, reply "好了").

Explicit, auditable encoding of every decision: 13 接受, 4 修正后执行, 4 保留. Gold/slices changes are applied
to parent and twin together (SPEC 5.1 / PR-15); query changes only to the named sample. Every new key_text is
checked to occur exactly once in the norm-v1 page text and to lie inside the evidence_span; the pc-0027 span is
recomputed from the page text. Kept disputes (pc-0088/0089/0090 negation) become resolutions after the
re-review of the changed families (their verdict bindings are unchanged, so they are written now).
"""

import json
import pathlib

from medops.retrieval.lexical.normalization import normalize_text

REPO = pathlib.Path(__file__).resolve().parents[6]
DRAFTS = REPO / "evals/probe/precise_clause/drafts/v2"
REVIEW = DRAFTS / "review"
PAGES = REPO / "evals/probe/precise_clause/v1/pages"
BATCHES = ("MA", "PV", "CO", "EN")

K = {
    "K1": "does not include the exposure to one of the ingredients during the manufacturing process before the release as finished product",
    "K2": "This should be done by the PRAC Rapporteur or the (lead) Member State within 30 days from receipt of the validated signal",
    "K3": "the two IND safety reporting provisions (§ 312.32(c)(1)(i)(C) and (c)(1)(iv)) that require assessment of aggregate data",
    "K4": "投予劑量、劑量單位，例如:「10mg」、「5mg/kg」",
    "K5": "Essential records should be retained securely by sponsors and investigators for the required period in accordance with applicable regulatory requirements",
    "K6": "Investigational products should be used in accordance with the protocol and relevant trial documents",
    "K7": "all study procedures and assessments are necessary from a scientific viewpoint and do not place undue burden on study participants",
    # page-text forms (norm-v1 of the PDF rendering the owner quoted; punctuation as extracted)
    "A23": "初步的急救方法,係靜脈注射1〜2mg Atropine sulfate;倘若還未能達到滿意效果時,在使用 Atropine 後可接著投與升壓劑,例如metaraminol 或 noradrenaline",
    "B27": "對食道未發炎之患者 20 mg 每天 1次;若 4週後仍有症狀時,則應進一步檢查患者",
}
B27_SPAN = "胃食道逆流性疾病之症狀治療:對食道未發炎之患者 20 mg 每天 1次;若 4週後仍有症狀時,則應進一步檢查患者。"
Q = {
    "pc-0033": "编码时发现现有 MedDRA 术语不能准确表达个案内容，团队可以自行制定临时处理规则吗？",
    "pc-0047": "按 GVP Module IX，收到信号确认结果后，能否在流程记录中把该信号标记为“完整评估已完成”？",
    "pc-0092": "When selecting procedures and assessments for a study, what does ICH E8(R1) require the team to consider about why they are needed and the demands they place on participants?",
    "pc-0027": "依胃所樂腸溶膜衣錠仿單，成人及 12 歲以上青少年若有胃食道逆流症狀、但食道沒有發炎，每日用量如何安排？治療多久仍有症狀時應進一步檢查？",
}
SLICES = {
    "pc-0008": ["dose_unit", "mixed_zh_en"],
    "pc-0012": ["protocol_id"],
    "pc-0022": ["time_window", "drug_name_zh"],
    # pc-0036: SPEC section 7 lists bounded windows (14 天内, 给药后 24 小时, ±3 天) for time_window and dose/frequency for
    # dose_unit; a liver-enzyme monitoring interval is neither, so both labels are removed per the owner's rule.
    "pc-0036": ["mixed_zh_en", "negation"],
}
KEY = {
    "pc-0044": "K1", "pc-0079": "K1",
    "pc-0045": "K2", "pc-0080": "K2",
    "pc-0050": "K3", "pc-0085": "K3",
    "pc-0058": "K4",
    "pc-0067": "K5", "pc-0099": "K5",
    "pc-0069": "K6", "pc-0101": "K6",
    "pc-0060": "K7", "pc-0092": "K7",
    "pc-0023": "A23",
    "pc-0027": "B27",
}
KEEP = {  # dispute kept: resolution_note from the owner's document
    "pc-0088": "保留 negation：“no later than 7 calendar days”含不可越过的时间上限；time_window 与 negation 分别标记时间约束与否定式边界，不能仅以已有前者为由删除后者。保留起算点、首次通知与后续补报的区别。若 SPEC 明文排除纯比较上限，应先统一修改规则并按同族重标。",
    "pc-0089": "保留 negation：“no longer than one year”是下一份 DSUR 覆盖期的否定式上限，不是提交期限。不能仅因它可改写为“至多一年”就断言不存在否定语义。",
    "pc-0090": "保留 negation：“no later than 60 calendar days”是以数据锁定点为起点的否定式截止限制；与 pc-0088/0089 采用同一切片解释，不以标签重叠为由局部删除。",
}


def page_text(g):
    return normalize_text((PAGES / g["source_hash"] / f"{g['page']}.txt").read_text(encoding="utf-8"))


def main() -> None:
    drafts = {b: json.loads((DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}
    by_id = {s["sample_id"]: (b, s) for b, rows in drafts.items() for s in rows}
    changed: dict[str, list[str]] = {}

    def mark(sid, field):
        changed.setdefault(sid, [])
        if field not in changed[sid]:
            changed[sid].append(field)

    for sid, slices in SLICES.items():
        _, s = by_id[sid]
        if s["slices"] != slices:
            s["slices"] = slices; mark(sid, "slices")
    # pc-0027 span shrink first (key must lie inside the new span)
    _, s27 = by_id["pc-0027"]; g27 = s27["required_gold_evidence"][0]; pg = page_text(g27)
    start = g27["evidence_span"]["char_start"]
    assert pg.startswith(B27_SPAN, start), "pc-0027: new span does not start at the current span start"
    assert pg.count(B27_SPAN) == 1
    g27["evidence_span"] = {"text": B27_SPAN, "char_start": start, "char_end": start + len(B27_SPAN)}; mark("pc-0027", "evidence_span")
    for sid, kname in KEY.items():
        _, s = by_id[sid]; g = s["required_gold_evidence"][0]
        new = normalize_text(K[kname]); text = page_text(g)
        assert text.count(new) == 1, f"{sid}: {kname} occurs {text.count(new)} times"
        assert new in g["evidence_span"]["text"], f"{sid}: {kname} not inside evidence_span"
        assert text[g["evidence_span"]["char_start"]:g["evidence_span"]["char_end"]] == g["evidence_span"]["text"], f"{sid}: span offsets stale"
        if g["key_text"] != new:
            g["key_text"] = new; mark(sid, "key_text")
    for sid, query in Q.items():
        _, s = by_id[sid]
        assert 4 <= len(query) <= 300, f"{sid}: query length {len(query)}"
        if s["query"] != query:
            s["query"] = query; mark(sid, "query")
    # family consistency + global query checks
    keys = {normalize_text(g["key_text"]) for _, s in by_id.values() for g in s["required_gold_evidence"]}
    seen = {}
    for sid, (_, s) in by_id.items():
        nq = normalize_text(s["query"])
        assert nq not in keys, f"{sid}: query equals a key_text"
        assert nq not in seen, f"{sid}: duplicate query with {seen.get(nq)}"
        seen[nq] = sid
        if s.get("derived_from"):
            _, p = by_id[s["derived_from"]]
            assert s["slices"] == p["slices"], f"{sid}: slices differ from parent"
            for a, b_ in zip(s["required_gold_evidence"], p["required_gold_evidence"], strict=True):
                assert {k: v for k, v in a.items() if k != "gold_id"} == {k: v for k, v in b_.items() if k != "gold_id"}, f"{sid}: gold differs from parent"
    for b, rows in drafts.items():
        (DRAFTS / f"samples_draft_{b}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # resolutions for kept disputes (bindings from the current run records)
    res_path = REVIEW / "resolutions.json"
    resolutions = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
    for sid, note in KEEP.items():
        b, _ = by_id[sid]
        run = json.loads((REVIEW / f"run_{b}.json").read_text(encoding="utf-8"))
        latest = run["latest"][sid]
        verdict = next(v for c in run["chunks"] for v in c["verdicts"] if v["sample_id"] == sid and run["chunks"].index(c) == latest["chunk_index"])
        resolutions[sid] = {
            "sample_input_sha256": latest["sample_input_sha256"],
            "verdict_sha256": latest["verdict_sha256"],
            "resolution_note": note,
            "issue_scope": sorted(k for k, x in verdict["items"].items() if x == "issue"),
            "approval_source": "drafts/v2/review/owner_adjudication_2026-09-20.md（annotator-01，2026-09-20 “好了”）",
        }
    res_path.write_text(json.dumps(resolutions, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (REVIEW / "owner_adjudication_changes_2026-09-20.json").write_text(
        json.dumps({"changed": changed, "kept_with_resolution": sorted(KEEP), "slices": SLICES, "key_texts": {k: normalize_text(v) for k, v in K.items()}, "queries": Q, "pc-0027_span": B27_SPAN}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    by_batch = {}
    for sid in changed:
        by_batch.setdefault(by_id[sid][0], []).append(sid)
    print(json.dumps({"changed": changed, "rereview": {b: sorted(v) for b, v in by_batch.items()}, "resolutions": sorted(resolutions)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
