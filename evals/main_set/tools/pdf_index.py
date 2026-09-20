"""List, per annotator sheet, the local PDF behind every document (spec-m1 drafts) and create friendly-name
symlinks so the annotator can open `evals/main_set/pdf_by_key/<document_key>.pdf` next to the sheet.

    python evals/main_set/tools/pdf_index.py

Writes drafts/main-v1/pdf_index.md (paths, titles, sample counts and the PDF pages each sheet cites; no page text)
and refreshes the gitignored symlink directory evals/main_set/pdf_by_key/.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

SOURCE_DIRS = (dc.MAIN / "sources_staging", dc.REPO / "evals/probe/precise_clause/v1/sources")
LINKS = dc.MAIN / "pdf_by_key"
BATCHES = ("MA", "PV", "CO", "EN", "NA")


def pdf_path(source_hash: str) -> pathlib.Path | None:
    for base in SOURCE_DIRS:
        p = base / f"{source_hash}.pdf"
        if p.is_file():
            return p
    return None


def main() -> int:
    corpus = dc.load_corpus()
    LINKS.mkdir(exist_ok=True)
    for old in LINKS.glob("*.pdf"):
        old.unlink()
    lines = [
        "# 主评测集 main-v1 标注表对应的 PDF",
        "",
        "> PDF 在本机、不进入 Git。友好文件名 `evals/main_set/pdf_by_key/<document_key>.pdf` 是指向原件的符号链接（由 `tools/pdf_index.py` 生成）；原件按 SHA-256 命名。表中「页」为标注表引用的 PDF 物理页序号（从 1 起）。",
        "",
    ]
    missing = []
    for batch in BATCHES:
        samples = json.loads((dc.DRAFTS / f"samples_draft_{batch}.json").read_text(encoding="utf-8"))
        per_doc: dict[str, dict] = defaultdict(lambda: {"n": 0, "pages": set()})
        for s in samples:
            if s["required_gold_evidence"]:
                g = s["required_gold_evidence"][0]
                key = next(k for k, d in corpus.items() if d["source_hash"] == g["source_hash"])
                per_doc[key]["n"] += 1
                per_doc[key]["pages"].add(g["page"])
            else:
                key = s["abstention"]["scope_document_key"]
                per_doc[key]["n"] += 1
                per_doc[key]["pages"].update(s["abstention"]["document_pages"])
        lines += [
            f"## {batch} 批次（{len(samples)} 条，{len(per_doc)} 份文档）",
            "",
            "| document_key | 标题 | 条数 | 页 | PDF（友好名） | 原件 |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
        for key in sorted(per_doc):
            d = corpus[key]
            src = pdf_path(d["source_hash"])
            link = LINKS / f"{key}.pdf"
            if src is None:
                missing.append(key)
                shown, orig = "（缺失）", "—"
            else:
                if not link.exists():
                    link.symlink_to(src.resolve())
                shown = f"`{link.relative_to(dc.REPO)}`"
                orig = f"`{src.relative_to(dc.REPO)}`"
            pages = per_doc[key]["pages"]
            page_cell = (
                ", ".join(map(str, sorted(pages)))
                if batch != "NA"
                else f"全文档 {d['pages']} 页（复核打包页 {', '.join(map(str, sorted(pages)))}）"
            )
            lines.append(f"| {key} | {d['title'][:70]} | {per_doc[key]['n']} | {page_cell} | {shown} | {orig} |")
        lines.append("")
    out = dc.DRAFTS / "pdf_index.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"{out.relative_to(dc.REPO)} written; symlinks in {LINKS.relative_to(dc.REPO)}: {len(list(LINKS.glob('*.pdf')))}; missing PDFs: {missing}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
