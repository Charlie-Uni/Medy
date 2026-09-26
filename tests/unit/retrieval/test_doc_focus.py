"""Named-document focus (record 94): title keys are derived deterministically from real corpus titles, questions
match them by brand name, ICH code or GVP module, and an ambiguous mention focuses nothing."""

from __future__ import annotations

from medops.retrieval.doc_focus import (
    DOC_FOCUS_VERSION,
    MAX_FOCUS_DOCS,
    DocRef,
    document_keys,
    focus_documents,
    query_keys,
)

DOCS = [
    DocRef("d1", "拔痛酸錠（PURINOL TABLETS，allopurinol）仿單", "label"),
    DocRef("d2", "痛風停錠300毫克（Deurinol Tablets 300mg, allopurinol）仿單", "label"),
    DocRef("d3", "胃所樂腸溶膜衣錠40毫克（Esomen Enteric-Coated Tablets 40mg, esomeprazole）仿單", "label"),
    DocRef("d4", "“信東”信諾隆靜脈輸注液 10 毫克/毫升（Cinolone IV Infusion 10 mg/mL，ciprofloxacin）仿單", "label"),
    DocRef("d5", "康肯５毫克（CONCOR 5，bisoprolol）仿單", "label"),
    DocRef("d6", "ICH Harmonised Guideline: Guideline for Good Clinical Practice E6(R3)", "guideline"),
    DocRef("d7", "E6(R3) Good Clinical Practice — Guidance for Industry (FDA, September 2025)", "guideline"),
    DocRef(
        "d8",
        "ICH E11(R1): Addendum: Clinical Investigation of Medicinal Products in the Pediatric Population",
        "guideline",
    ),
    DocRef(
        "d9",
        "Guideline on good pharmacovigilance practices (GVP) – GVP Module IX – Signal management (Rev 1)",
        "guideline",
    ),
    DocRef(
        "d10",
        "Guideline on good pharmacovigilance practices (GVP) – GVP Module IX Addendum I – Methodological aspects",
        "guideline",
    ),
    DocRef("d11", "Guideline on good pharmacovigilance practices (GVP) – Annex I – Definitions (Rev 5)", "guideline"),
    DocRef("d12", "藥品不良反應通報表填寫指引（第四版）", "guideline"),
    DocRef("d13", "Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring", "guideline"),
]


def test_title_keys_for_labels_ich_gvp_and_chinese_guidance():
    assert document_keys(DOCS[0].title, "label") == {"name:拔痛酸"}
    assert document_keys(DOCS[2].title, "label") == {"name:胃所樂"}
    assert document_keys(DOCS[3].title, "label") == {"name:信諾隆"}  # manufacturer quotes skipped
    assert document_keys(DOCS[4].title, "label") == {"name:康肯"}  # stops at the full-width digit
    assert document_keys(DOCS[5].title, "guideline") == {"ich:e6r3"}
    assert document_keys(DOCS[6].title, "guideline") == {"ich:e6r3"}  # the FDA reprint carries the same code
    assert document_keys(DOCS[7].title, "guideline") == {"ich:e11r1"}
    assert document_keys(DOCS[8].title, "guideline") == {"gvp:module IX"}
    assert document_keys(DOCS[9].title, "guideline") == {"gvp:module IX addendum I"}
    assert document_keys(DOCS[10].title, "guideline") == {"gvp:annex I"}
    assert document_keys(DOCS[11].title, "guideline") == {"title:藥品不良反應通報表填寫指引"}
    assert document_keys(DOCS[12].title, "guideline") == set()  # English FDA titles are not matched in v1


def test_questions_focus_the_named_document_only():
    assert [
        d.doc_id for d in focus_documents("停止使用拔痛酸錠（Allopurinol）治療後，血清尿酸濃度多久回復？", DOCS)
    ] == ["d1"]
    assert [d.doc_id for d in focus_documents("胃所樂泡在水裡崩散後要在多久之內喝完", DOCS)] == ["d3"]
    assert [d.doc_id for d in focus_documents("根据ICH E6(R3),研究者可以对受试者施压吗?", DOCS)] == [
        "d7",
        "d6",
    ]  # both copies
    assert [d.doc_id for d in focus_documents("按 GVP Module IX，收到信号确认结果后能否标记为完整？", DOCS)] == ["d9"]
    assert [
        d.doc_id for d in focus_documents("GVP Module IX Addendum I 对统计信号检测的 MedDRA 层级有何建议", DOCS)
    ] == ["d10"]
    assert [d.doc_id for d in focus_documents("按 GVP Annex I 的职业暴露定义", DOCS)] == ["d11"]
    assert [d.doc_id for d in focus_documents("藥品不良反應通報表填寫指引第四版要求哪些欄位", DOCS)] == ["d12"]
    assert focus_documents("esomeprazole 可以和 nelfinavir 一起服用嗎", DOCS) == []  # ingredient, not a product name
    assert query_keys("E2B(R3) 的数据元素") == {"ich:e2br3"} and query_keys("第 E1 栏") == set()


def test_ambiguous_mentions_focus_nothing():
    many = [
        DocRef(
            f"g{i}",
            f"Guideline on good pharmacovigilance practices (GVP) – Annex I – Definitions (Rev {i})",
            "guideline",
        )
        for i in range(MAX_FOCUS_DOCS + 1)
    ]
    assert focus_documents("GVP Annex I 定义", many) == []
    assert DOC_FOCUS_VERSION == "docfocus-v1"
