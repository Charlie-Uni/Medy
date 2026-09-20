# -*- coding: utf-8 -*-
"""Round-3 adjudication of the six disputes raised during the neighbour re-review (2026-09-20).

Recommended plan (to be executed only after the annotator's approval):
- key_text extensions on P1 grounds, family-synchronised: pc-0039; pc-0064 + twin pc-0096; pc-0093 + parent
  pc-0061; pc-0102 + parent pc-0070.
- keep with resolution notes (query wording judged natural by the annotator's stated principle that plain
  yes/no questions are not automatically invalid): pc-0032, pc-0095; pc-0093's query is kept for the same reason
  (its key_text still changes).
Changed samples and every sample whose latest review chunk contained a changed input are re-reviewed with --only.
"""

import hashlib
import json
import pathlib
import subprocess
import sys

from medops.retrieval.lexical.normalization import normalize_text

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[5]
DRAFTS = HERE.parent
REVIEW = DRAFTS / "review"
PAGES = REPO / "evals/probe/precise_clause/v1/pages"
BATCHES = ("MA", "PV", "CO", "EN")
KEY = {
    "pc-0039": "数据库结构可能不允许次 SOC 路径的输出或者展示",
    "pc-0064": "designing quality into the study protocol and processes",
    "pc-0096": "designing quality into the study protocol and processes",
    "pc-0061": "even when combined with audits, they are not sufficient to ensure quality of a clinical study",
    "pc-0093": "even when combined with audits, they are not sufficient to ensure quality of a clinical study",
    "pc-0070": "retain all relevant records (e.g. , documented procedures, membership lists, lists of occupations/affiliations of members, submitted documents, minutes of meetings and correspondence)",
    "pc-0102": "retain all relevant records (e.g. , documented procedures, membership lists, lists of occupations/affiliations of members, submitted documents, minutes of meetings and correspondence)",
}
KEEP_QUERY = {
    "pc-0032": "保留 query：问题是 PV 编码人员的自然提问（能否使用非现行 LLT），复用 LLT/MedDRA 属必要术语；决策人 2026-09-20 裁决原则“普通的是非题并不自动无效，判断重点是问题是否自然、是否真正需要证据、是否与原始信息需求等价”。gold 与切片不变。",
    "pc-0095": "保留 query：“Which topics does Section 6 of ICH E8(R1) address?”是自然的检索式提问；key_text 作为锚点保留对象与动作，完整三项主题由 evidence_span 覆盖（决策人 2026-09-20 审校稿已确认该 span 须覆盖三项）。",
}


def rh(r):
    return hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    dry = "--dry-run" in sys.argv
    drafts = {b: json.loads((DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}
    by_id = {s["sample_id"]: (b, s) for b, rows in drafts.items() for s in rows}
    changed = []
    for sid, text in KEY.items():
        b, s = by_id[sid]; g = s["required_gold_evidence"][0]
        new = normalize_text(text)
        page = normalize_text((PAGES / g["source_hash"] / f"{g['page']}.txt").read_text(encoding="utf-8"))
        assert page.count(new) == 1 and new in g["evidence_span"]["text"], sid
        if g["key_text"] != new:
            g["key_text"] = new; changed.append(sid)
    for sid, (_, s) in by_id.items():
        if s.get("derived_from"):
            _, p = by_id[s["derived_from"]]
            for a, b_ in zip(s["required_gold_evidence"], p["required_gold_evidence"], strict=True):
                assert {k: v for k, v in a.items() if k != "gold_id"} == {k: v for k, v in b_.items() if k != "gold_id"}, sid
    print("changed:", changed)
    if dry:
        return 0
    for b, rows in drafts.items():
        (DRAFTS / f"samples_draft_{b}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(HERE / "review_pack.py"), *BATCHES], check=True)
    # keep-decisions become resolutions bound to the current verdicts (their inputs do not change)
    res = json.loads((REVIEW / "resolutions.json").read_text(encoding="utf-8"))
    for sid, note in KEEP_QUERY.items():
        b, _ = by_id[sid]
        run = json.loads((REVIEW / f"run_{b}.json").read_text(encoding="utf-8"))
        latest = run["latest"][sid]; chunk = run["chunks"][latest["chunk_index"]]
        verdict = next(v for v in chunk["verdicts"] if v["sample_id"] == sid)
        res[sid] = {"sample_input_sha256": latest["sample_input_sha256"], "verdict_sha256": latest["verdict_sha256"], "resolution_note": note,
                    "issue_scope": sorted(k for k, x in verdict["items"].items() if x == "issue"), "approval_source": "round 3 adjudication 2026-09-20 (annotator-01)"}
    for sid in changed:
        res.pop(sid, None)
    (REVIEW / "resolutions.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # re-review: changed samples + neighbours whose latest chunk holds a superseded input
    for b in BATCHES:
        run = json.loads((REVIEW / f"run_{b}.json").read_text(encoding="utf-8"))
        current = {json.loads(l)["sample_id"]: rh(json.loads(l)) for l in (REVIEW / f"input_{b}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
        need = sorted({sid for sid, ref in run["latest"].items() if any(current.get(m) != h for m, h in run["chunks"][ref["chunk_index"]]["sample_input_sha256"].items())})
        if need:
            print(f"{b}: re-review {need}")
            subprocess.run([sys.executable, str(HERE / "run_claude_review.py"), b, "--only", *need], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
