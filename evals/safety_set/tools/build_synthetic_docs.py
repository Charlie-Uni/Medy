"""Build the safety corpus (spec-s1 §5): for each base document in injection_plan.json, a DOCX whose paragraphs are
the production chunks in order (headings = chunk sections) plus one injected paragraph per planned sample, then
corpus_safety.json for `python -m medops.ingestion.load` against medops_v2_safety.

    python evals/safety_set/tools/build_synthetic_docs.py [--database medops_v2_safety]

The DOCX files land in evals/safety_set/synthetic/<source_hash>.docx (gitignored: copied licensed text); the corpus
file and the per-sample canary map are committed. Self-check: the ingestion DOCX extractor must see every injected
paragraph exactly once, in the planned section.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from medops.evals.safety_data import (  # noqa: E402
    CORPUS_SAFETY,
    INJECTION_PLAN,
    SAFETY_DB,
    SYNTHETIC_DIR,
    admin_dsn,
    canary_for,
)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "src"))
from medops.ingestion import docx as docx_mod  # noqa: E402

_CT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>'
    "</w:styles>"
)


_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _p(text: str, heading: bool = False) -> str:
    text = _XML_INVALID.sub("", text)  # control characters in a few production chunks are not valid XML 1.0
    ppr = '<w:pPr><w:pStyle w:val="Heading1"/><w:outlineLvl w:val="0"/></w:pPr>' if heading else ""
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def build_docx(paragraphs: list[tuple[str, bool]]) -> bytes:
    body = "".join(_p(t, h) for t, h in paragraphs)
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        + body
        + "<w:sectPr/></w:body></w:document>"
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CT)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("word/styles.xml", _STYLES)
        zf.writestr("word/document.xml", doc)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", default=SAFETY_DB)
    args = ap.parse_args()
    plan = json.loads(INJECTION_PLAN.read_text(encoding="utf-8"))
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    corpus_docs: list[dict] = []
    canaries: list[dict] = []
    with psycopg.connect(admin_dsn(args.database)) as conn:
        for spec in plan["documents"]:
            meta = conn.execute(
                "select title, doc_type, owner_dept::text, language, version, doc_id::text from documents where document_key = %s",
                (spec["base"],),
            ).fetchone()
            if meta is None:
                raise SystemExit(f"base document {spec['base']} not found in {args.database}")
            title, doc_type, owner_dept, language, version, doc_id = meta
            chunks = conn.execute(
                "select seq, section, content from chunks where doc_id = %s::uuid order by seq", (doc_id,)
            ).fetchall()
            by_seq = {int(c[0]): c for c in chunks}
            injections = {int(i["after_seq"]): i for i in spec["injections"]}
            missing = sorted(set(injections) - set(by_seq))
            if missing:
                raise SystemExit(f"{spec['base']}: anchor seq not found: {missing}")
            paragraphs: list[tuple[str, bool]] = [(f"[安全集合成文件] {title}", False)]
            last_section = None
            for seq, section, content in chunks:
                sec = (section or "").strip() or f"第 {seq + 1} 段"
                if sec != last_section:
                    paragraphs.append((sec, True))
                    last_section = sec
                paragraphs.append((content, False))
                inj = injections.get(int(seq))
                if inj:
                    canary = canary_for(inj["sample_id"])
                    payload = plan["payloads"][inj["payload"]]
                    text = payload["text"].replace("{canary}", canary)
                    paragraphs.append((text, False))
                    canaries.append(
                        {
                            "sample_id": inj["sample_id"],
                            "canary": canary,
                            "sf_key": spec["sf_key"],
                            "base": spec["base"],
                            "after_seq": int(seq),
                            "section": sec,
                            "payload": inj["payload"],
                            "payload_kind": payload["kind"],
                            "anchor_preview": content[:80],
                        }
                    )
            data = build_docx(paragraphs)
            # self-check with the ingestion extractor: every canary exactly once, headings recognised
            sections, warnings = docx_mod.extract_sections(data)
            joined = "\n".join(s.text for s in sections)
            for c in [x for x in canaries if x["sf_key"] == spec["sf_key"]]:
                if joined.count(c["canary"]) != 1:
                    raise SystemExit(f"{spec['sf_key']}: canary {c['canary']} seen {joined.count(c['canary'])} times")
            if warnings:
                raise SystemExit(f"{spec['sf_key']}: extractor warnings {warnings}")
            source_hash = hashlib.sha256(data).hexdigest()
            (SYNTHETIC_DIR / f"{source_hash}.docx").write_bytes(data)
            corpus_docs.append(
                {
                    "document_key": spec["sf_key"],
                    "title": f"[安全集合成] {title}",
                    "doc_type": doc_type,
                    "owner_dept": owner_dept,
                    "language": language,
                    "version_label": f"safety-v1 synthetic（基于 {version}）",
                    "source_hash": source_hash,
                    "byte_size": len(data),
                    "source_url": f"https://medops.local/safety-set/{spec['sf_key']}",  # documents.source_url CHECK ^https?://
                    "publisher": f"MedOps 安全评测集合成文件（条款复制自 {spec['base']}，另加注入段落）",
                    "retrieved_at": "2026-09-24",
                    "terms_url": "https://medops.local/safety-set/terms",
                    "license_or_terms": {
                        "name_or_summary": f"internal synthetic test artefact derived from {spec['base']}; not for distribution",
                        "attribution_text": f"derived from {spec['base']} for the MedOps safety set (spec-s1 §5)",
                    },
                    "notes": f"合成注入 {len(spec['injections'])} 段（injection_plan.json）；正文 {len(chunks)} 段照抄 medops_v2 chunk",
                    "base_document_key": spec["base"],
                    "sections_extracted": len(sections),
                }
            )
            print(
                f"{spec['sf_key']}: {len(chunks)} chunks -> {len(sections)} sections, {len(spec['injections'])} injections, {len(data)} bytes"
            )
    CORPUS_SAFETY.write_text(
        json.dumps(
            {"dataset_version": "safety-v1", "documents": corpus_docs, "canaries": canaries},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {CORPUS_SAFETY.relative_to(pathlib.Path.cwd())} with {len(corpus_docs)} documents and {len(canaries)} canaries"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
