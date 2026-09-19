"""Probe-set drafting aid: turn compact clause specs into anchored draft samples plus a review sheet.

For every spec the page text is normalised with norm-v1, `key_text` must occur exactly once on that page,
the evidence span is the sentence containing it (or an explicit span text) and offsets are computed, so the
owner only judges wording, slices and department. Output: <out>/samples_draft_<batch>.json and .md.
Nothing here writes samples.jsonl; that happens after the owner's confirmation with the review block.
"""

import json
import pathlib
import re
import sys
from collections import Counter

from medops.retrieval.lexical.normalization import normalize_text

REPO = pathlib.Path(__file__).resolve().parents[6]
V1 = REPO / "evals/probe/precise_clause/v1"
OUT = REPO / "evals/probe/precise_clause/drafts/v1"
SENT_END = re.compile(r"(?<=[。！？；])|(?<=[.!?;])(?=\s)")

corpus = {d["document_key"]: d for d in json.loads((V1 / "corpus.json").read_text(encoding="utf-8"))["documents"]}
_page_cache: dict = {}


def page_text(doc_key: str, page: int) -> str:
    key = (doc_key, page)
    if key not in _page_cache:
        d = corpus[doc_key]
        raw = (V1 / "pages" / d["source_hash"] / f"{page}.txt").read_text(encoding="utf-8")
        _page_cache[key] = normalize_text(raw)
    return _page_cache[key]


def sentence_around(text: str, pos: int, end: int) -> tuple[int, int]:
    """Smallest sentence (CJK or ASCII terminators) containing [pos, end)."""
    cuts = [m.start() for m in SENT_END.finditer(text) if 0 < m.start() < len(text)]
    start = max((c for c in cuts if c <= pos), default=0)
    stop = min((c for c in cuts if c >= end), default=len(text))
    while start < stop and text[start].isspace():
        start += 1
    while stop > start and text[stop - 1].isspace():
        stop -= 1
    return start, stop


def build(batch: str, specs: list[dict], start_id: int) -> list[dict]:
    samples, problems = [], []
    per_doc = Counter()
    for i, s in enumerate(specs):
        sid = f"pc-{start_id + i:04d}"
        d = corpus[s["doc"]]
        text = page_text(s["doc"], s["page"])
        key = normalize_text(s["key_text"])
        n = text.count(key)
        if n != 1:
            problems.append(f"{sid} {s['doc']} p{s['page']}: key_text occurs {n} times: {key!r}")
            continue
        pos = text.index(key)
        if s.get("span"):
            span_text = normalize_text(s["span"])
            if text.count(span_text) != 1 or key not in span_text:
                problems.append(f"{sid}: explicit span not unique or does not contain key_text")
                continue
            cs = text.index(span_text)
            ce = cs + len(span_text)
        else:
            cs, ce = sentence_around(text, pos, pos + len(key))
            span_text = text[cs:ce]
        assert text[cs:ce] == span_text and key in span_text
        query = s["query"].strip()
        if not 4 <= len(query) <= 300:
            problems.append(f"{sid}: query length {len(query)}")
        if normalize_text(query) == key:
            problems.append(f"{sid}: query equals key_text")
        slices = list(dict.fromkeys(s["slices"]))
        language = "mixed" if "mixed_zh_en" in slices else s.get("language", "zh")
        if language == "en" and "drug_name_zh" in slices:
            problems.append(f"{sid}: en sample with drug_name_zh")
        per_doc[s["doc"]] += 1
        if per_doc[s["doc"]] > 6:
            problems.append(f"{sid}: document {s['doc']} exceeds 6 samples")
        samples.append(
            {
                "sample_id": sid,
                "query": query,
                "dept": d["owner_dept"],
                "language": language,
                "slices": slices,
                "required_gold_evidence": [
                    {
                        "gold_id": f"{sid}-g1",
                        "source_hash": d["source_hash"],
                        "version_label": d["version_label"],
                        "page": s["page"],
                        "printed_page_label": None,
                        "section": s["section"],
                        "key_text": key,
                        "evidence_span": {"text": span_text, "char_start": cs, "char_end": ce},
                    }
                ],
                "notes": s.get("notes", ""),
                "_draft": {"document_key": s["doc"], "title": d["title"]},
            }
        )
    # PR-08: normalised queries distinct and not equal to any key_text in the batch
    q = Counter(normalize_text(x["query"]) for x in samples)
    for k, v in q.items():
        if v > 1:
            problems.append(f"duplicate query: {k!r}")
    keys = {x["required_gold_evidence"][0]["key_text"] for x in samples}
    for x in samples:
        if normalize_text(x["query"]) in keys:
            problems.append(f"{x['sample_id']}: query equals some key_text")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  ", p)
        sys.exit(1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"samples_draft_{batch}.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"# 探针集 v1 样本草稿：{batch} 批次（{len(samples)} 条，待决策人逐条确认）",
        "",
        "> 每条请判断五件事：问题是否自然且只有这一句能回答；key_text 是否最短且页内唯一（工具已核对唯一性）；span 是否完整条款；切片标签；部门归属。",
        "> 确认方式：在「结论」列填 OK，或直接改写 query / key_text / span / slices；改动的条目我重新计算偏移。",
        "",
        "| ID | 文档 | 页 | 切片 | query | key_text | evidence_span | 章节 | 结论 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for x in samples:
        g = x["required_gold_evidence"][0]
        span = g["evidence_span"]["text"].replace("|", "\\|")
        span_cell = span[:160] + ("…" if len(span) > 160 else "")
        key_cell = g["key_text"].replace("|", "\\|")
        slices_cell = ", ".join(x["slices"])
        lines.append(
            f"| {x['sample_id']} | {x['_draft']['document_key']} | {g['page']} | {slices_cell} | {x['query']} | {key_cell} | {span_cell} | {g['section']} | |"
        )
    by_slice = Counter(sl for x in samples for sl in x["slices"])
    by_dept = Counter(x["dept"] for x in samples)
    lines += [
        "",
        f"切片计数：{dict(by_slice)}；部门：{dict(by_dept)}；语言：{dict(Counter(x['language'] for x in samples))}",
    ]
    (OUT / f"samples_draft_{batch}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{batch}: {len(samples)} samples; slices {dict(by_slice)}; per doc {dict(per_doc)}")
    return samples


if __name__ == "__main__":
    spec_file = pathlib.Path(sys.argv[1])
    payload = json.loads(spec_file.read_text(encoding="utf-8"))
    build(payload["batch"], payload["specs"], payload["start_id"])
