"""Prepare reviewable candidate edits; never overwrite drafts or mark disputes resolved."""

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from medops.retrieval.lexical.normalization import normalize_text

REPO = Path(__file__).resolve().parents[6]
ROOT = REPO / "evals/probe/precise_clause"
DRAFTS = ROOT / "drafts/v1"
REVIEW = DRAFTS / "review"
TAGS = ("dose_unit", "drug_name_zh", "negation", "time_window", "mixed_zh_en", "protocol_id")

# Short natural questions and exact anchors proposed by the continuation author, pending human review.
OVERRIDES = {
    "pc-0026": {"key_text": "立即或在 30 分鐘之內將水連同小藥球喝下"},
    "pc-0039": {"query": "按 HLT 或 HLGT 导出多轴性 PT 数据时，次 SOC 分支缺失可能与什么数据库限制有关？"},
    "pc-0065": {"query": "按 ICH E6(R3) 设计研究流程时，申办方应如何控制受试者和研究者的额外负担？"},
    "pc-0053": {
        "key_text": "Regulatory agencies should be notified (e.g., by telephone, facsimile transmission, or in writing) as soon as possible but no later than 7 calendar days"
    },
    "pc-0071": {
        "key_text": "important protocol deviation is a subset of protocol 118 deviations that might significantly affect the completeness, accuracy, and/or reliability of the 119 study data"
    },
    "pc-0073": {
        "key_text": "any deviation from the 210 investigational plan to protect the life or physical well-being of a subject in an emergency as 211 soon as possible but no later than 5 working days"
    },
}


def main() -> None:
    corpus = {d["source_hash"]: d for d in json.loads((ROOT / "v1/corpus.json").read_text())["documents"]}
    checker = Draft202012Validator(json.loads((ROOT / "schema/probe_sample.schema.json").read_text()))
    changes, errors, candidates, counts = [], [], [], Counter()
    fingerprints = {}
    for batch in ("MA", "PV", "CO"):
        path = DRAFTS / f"samples_draft_{batch}.json"
        fingerprints[batch] = hashlib.sha256(path.read_bytes()).hexdigest()
        verdicts = {
            v["sample_id"]: v
            for line in (REVIEW / f"verdicts_{batch}.jsonl").read_text().splitlines()
            if (v := json.loads(line))
        }
        for original in json.loads(path.read_text()):
            s = copy.deepcopy(original)
            sid = s["sample_id"]
            v = verdicts.get(sid)
            if not v or v["verdict"] == "agree":
                candidates.append(s)
                continue
            g = s["required_gold_evidence"][0]
            page = normalize_text((ROOT / "v1/pages" / g["source_hash"] / f"{g['page']}.txt").read_text())
            text = v["suggestion"]
            override = OVERRIDES.get(sid, {})
            notes = []
            if v["items"]["key_text"] == "issue":
                quotes = re.findall(r"[“「]([^”」]+)[”」]", text)
                options = [normalize_text(q) for q in quotes if page.count(normalize_text(q)) == 1]
                if sid == "pc-0043":
                    a = page.index("non-serious valid ICSRs")
                    ending = "within 90 days from the date of receipt of the reports"
                    options = [page[a : page.index(ending, a) + len(ending)]]
                if not options and "：" in text:
                    options = [normalize_text(text.split("：", 1)[1].rstrip("。"))]
                key = override.get("key_text", options[0] if len(options) == 1 else None)
                if key is None:
                    errors.append(f"{sid}: key proposal requires manual selection")
                elif not (2 <= len(key) <= 200 and page.count(key) == 1):
                    errors.append(f"{sid}: proposed key not valid/unique or outside 2..200 chars ({len(key)})")
                else:
                    g["key_text"] = key
            if v["items"]["slices"] == "issue":
                s["slices"] += [tag for tag in TAGS if tag in text and tag not in s["slices"]]
                for tag in TAGS:
                    if re.search(r"(?:删除|刪除|去掉|移除)\s*" + tag, text):
                        s["slices"] = [t for t in s["slices"] if t != tag]
            if v["items"]["query"] == "issue":
                if "query" in override:
                    s["query"] = override["query"]
                else:
                    errors.append(f"{sid}: query proposal requires manual wording")
            span = g["evidence_span"]["text"]
            if sid == "pc-0025":
                span = "本錠劑應整粒以液體吞服,不可嚼破或壓破本錠劑。"
                s["slices"] = [t for t in s["slices"] if t != "time_window"]
            elif sid == "pc-0073":
                end = "812.150(a)(4))."
                span = span[: span.index(end) + len(end)]
            elif sid in ("pc-0026", "pc-0027"):
                notes.append(
                    "span 扩展建议与已批准的 MA 试跑逐条处理重复：沿用不扩展的既有裁决，见人工确认记录及试跑表；不把该裁决扩展到其他新问题。"
                )
            elif v["items"]["evidence_span"] == "issue":
                errors.append(f"{sid}: span proposal requires manual wording")
            if "mixed_zh_en" in s["slices"]:
                s["language"] = "mixed"
            if page.count(span) != 1 or g["key_text"] not in span:
                errors.append(f"{sid}: proposed span/key mismatch")
            else:
                start = page.index(span)
                g["evidence_span"] = {"text": span, "char_start": start, "char_end": start + len(span)}
            payload = {k: val for k, val in s.items() if k != "_draft"}
            for issue in checker.iter_errors(payload):
                if not (issue.validator == "required" and issue.message == "'review' is a required property"):
                    errors.append(f"{sid}: {issue.message}")
            if sid == "pc-0038":
                notes.append("复核人按频次表达的字面口径建议给文档年度更新加 dose_unit；请人工明确接受或拒绝。")
            if sid in ("pc-0053", "pc-0071"):
                notes.append(
                    "复核人原建议超过 key_text 的 200 字符上限；改为保留对象与数据完整性约束的连续锚点，完整定义仍在 span。"
                )
            if sid in ("pc-0039", "pc-0065"):
                notes.append("使用简短自然的替代问题，不添加复核人建议的长场景。")
            if sid == "pc-0050":
                notes.append(
                    "按现有定义移除法规条款编号的 protocol_id；这也恢复了 PV 原始人工编辑中的标签选择。其他样本仍满足编号切片数量门槛。"
                )
            modified = {}
            for field in ("query", "slices", "language"):
                if s[field] != original[field]:
                    modified[field] = {"before": original[field], "after": s[field]}
            old_gold = original["required_gold_evidence"][0]
            for field in ("key_text", "evidence_span"):
                if g[field] != old_gold[field]:
                    modified[field] = {"before": old_gold[field], "after": g[field]}
            counts.update(modified.keys())
            if not modified and sid != "pc-0027":
                errors.append(f"{sid}: unresolved dispute has no proposed action")
            changes.append({"sample_id": sid, "changes": modified, "notes": notes, "status": "pending_human_decision"})
            candidates.append(s)
    queries = [normalize_text(s["query"]) for s in candidates]
    keys = {g["key_text"] for s in candidates for g in s["required_gold_evidence"]}
    if len(queries) != len(set(queries)) or set(queries) & keys:
        errors.append("candidate queries duplicate or equal a gold key_text")
    per_slice = Counter(t for s in candidates for t in s["slices"])
    if len(candidates) < 60 or any(per_slice[tag] < 8 for tag in TAGS):
        errors.append("candidate counts do not meet the existing minimums")
    # Candidate plans can be inspected without changing any input to an ongoing reviewer.
    report = {
        "status": "proposal_only",
        "draft_file_sha256": fingerprints,
        "changes": changes,
        "mechanical_errors": errors,
        "candidate_counts": {
            "samples": len(candidates),
            "slices": dict(per_slice),
            "gold_languages": dict(
                Counter(corpus[s["required_gold_evidence"][0]["source_hash"]]["language"] for s in candidates)
            ),
        },
    }
    (REVIEW / "proposed_changes.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# 正式复核后的具体修订提案（待人工裁决）",
        "",
        "本文件对应 proposed_changes.json，未覆盖样本，未写人工签字，未触发重审。",
        "当前已收到的争议逐项如下；复核是否全部完成见 [复核状态](formal_review_status.md)。",
        "",
        f"涉及 {len(changes)} 条；字段修改次数：{dict(counts)}。候选机械检查错误：{len(errors)}。",
        "",
        "建议：按 P1 补足或缩短锚点，按 P2 补标签；pc-0039/0065 使用简短自然问法；pc-0025/0073 收窄 span。",
        "pc-0026/0027 的 span 不扩展沿用既有人工决定，不要求重复确认；pc-0026 新的锚点扩展仍列作新提案。",
        "pc-0053/0071 的原复核建议超过 200 字符，提案已改成更短的连续原文。",
        "pc-0038 给年度文档更新加 dose_unit 的建议需人工明确：这里按当前“频次表达”的字面口径列出，不能自行收窄规范。",
        "",
    ]
    for item in changes:
        lines += [f"## {item['sample_id']}", ""]
        if not item["changes"]:
            lines += ["样本不改，沿用已有人工裁决。", ""]
        for field, values in item["changes"].items():
            before, after = values["before"], values["after"]
            if field == "evidence_span":
                before, after = before["text"], after["text"]
            if isinstance(before, list):
                before, after = ", ".join(before), ", ".join(after)
            lines += [f"**{field}**", "", f"原：{before}", "", f"拟改：{after}", ""]
        for note in item["notes"]:
            lines += [note, ""]
    if errors:
        lines += ["## 未解决的机械问题", "", *[f"- {e}" for e in errors], ""]
    (REVIEW / "proposed_changes.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {"proposed_rows": len(changes), "fields": dict(counts), "mechanical_errors": errors}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
