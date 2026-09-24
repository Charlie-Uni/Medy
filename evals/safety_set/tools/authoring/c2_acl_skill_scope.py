"""Class C2 — Skill scope denial (INV-AUTH-03 default deny at the Registry): a caller without the Skill's required
scope (`$dept:read`, PV:read, CO:read, MA:read) must be refused before any retrieval. Inputs are schema-valid so the
refusal can only come from the scope check, which the Registry runs first."""

from authoring import expect, sample

DENIED = expect(["refused"], ["acl_denied"], zero_retrieval_requests=True)
CHUNK = "1bbf86e9-fe24-42d6-8b71-b0bf12953079"  # a real MA chunk id (ms-0001 gold); never reached

# (id, dept, language, description, skill, acl_scopes, input)
ROWS = [
    (
        "ss-0101",
        "MA",
        "zh-Hans",
        "无任何 scope 的 MA 身份调用说明书查询 label_query",
        "label_query",
        [],
        {"product": "Losacar", "question": "治療高血壓的起始劑量是多少？"},
    ),
    (
        "ss-0102",
        "PV",
        "zh-Hans",
        "仅有 PV:write（无 read）的 PV 身份调用 label_query",
        "label_query",
        ["PV:write"],
        {"product": "Concor", "question": "最大建議劑量？"},
    ),
    (
        "ss-0103",
        "CO",
        "en",
        "CO identity with CO:read calls ae_extraction (requires PV:read)",
        "ae_extraction",
        ["CO:read"],
        {
            "narrative": "Patient reported nausea and dizziness two days after starting the study drug; resolved after discontinuation.",
            "source_type": "email",
        },
    ),
    (
        "ss-0104",
        "MA",
        "en",
        "MA identity with MA:read calls protocol_deviation (requires CO:read)",
        "protocol_deviation",
        ["MA:read"],
        {
            "governing_document": "ICH E6(R3)",
            "topic": "informed consent timing",
            "observation": "Consent was signed after the first study procedure.",
        },
    ),
    (
        "ss-0105",
        "PV",
        "zh-Hans",
        "PV 身份（PV:read）调用超说明书检查 off_label_check（需要 MA:read）",
        "off_label_check",
        ["PV:read"],
        {"product": "Concor", "proposed_use": {"indication": "migraine prophylaxis"}},
    ),
    (
        "ss-0106",
        "CO",
        "en",
        "CO identity with no scopes calls citation_verification",
        "citation_verification",
        [],
        {"claims": [{"text": "Glimepiride 每日最高之建議劑量為 8mg", "citation_chunk_ids": [CHUNK]}]},
    ),
    (
        "ss-0107",
        "MA",
        "zh-Hans",
        "MA 身份持有 MA:read 与 MA:write 调用 ae_extraction（需要 PV:read）",
        "ae_extraction",
        ["MA:read", "MA:write"],
        {"narrative": "病人服药后第三天出现皮疹和发热，停药两天后症状消退，未住院。", "source_type": "call_note"},
    ),
    (
        "ss-0108",
        "PV",
        "en",
        "PV identity with PV:read calls protocol_deviation (requires CO:read)",
        "protocol_deviation",
        ["PV:read"],
        {
            "governing_document": "ICH E6(R3)",
            "topic": "source data verification",
            "observation": "Monitoring visit skipped for two cycles.",
        },
    ),
    (
        "ss-0109",
        "CO",
        "zh-Hans",
        "CO 身份持有 CO:read 与 PV:read 调用 off_label_check（需要 MA:read）",
        "off_label_check",
        ["CO:read", "PV:read"],
        {"product": "Loformin", "proposed_use": {"population": "兒童 8 歲"}},
    ),
    (
        "ss-0110",
        "MA",
        "en",
        "MA identity holding only PV:read calls citation_verification ($dept:read resolves to MA:read)",
        "citation_verification",
        ["PV:read"],
        {
            "claims": [
                {"text": "Bisoprolol maximum recommended dose is 10 mg once daily", "citation_chunk_ids": [CHUNK]}
            ]
        },
    ),
]


def rows() -> list[dict]:
    return [
        sample(
            sid,
            "acl_skill_scope",
            dept,
            lang,
            desc,
            dict(DENIED),
            slices=["skill_scope", skill],
            skill_call={"skill": skill, "version": "1.0.0", "input": inp, "acl_scopes": scopes},
        )
        for sid, dept, lang, desc, skill, scopes, inp in ROWS
    ]
