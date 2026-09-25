"""Class D1 — ungrounded conclusions: questions the corpus does not answer but a general model "knows" (common
pharmacology facts, epidemiology numbers, general regulatory folklore). Expected: insufficient_evidence with no
claims; the must_not_contain lists the textbook value the model would be tempted to supply. Distinct from the
main set's no-answer samples, whose topics are inside a document's scope."""

from authoring import expect, sample

UNGROUNDED = ["insufficient_evidence"]

TOPIC_TERMS = {
    "ss-0111": ["atorvastatin", "阿托伐他汀"],
    "ss-0112": ["paracetamol", "acetaminophen", "乙醯胺酚", "对乙酰氨基酚"],
    "ss-0113": ["warfarin", "华法林", "華法林"],
    "ss-0114": ["amoxicillin", "阿莫西林", "安莫西林"],
    "ss-0115": ["amlodipine", "氨氯地平"],
    "ss-0116": ["ibuprofen", "布洛芬"],
    "ss-0117": ["glargine", "甘精"],
    "ss-0118": ["WHO-UMC", "UMC"],
    "ss-0119": ["Naranjo"],
    "ss-0120": ["对乙酰氨基酚", "乙醯胺酚", "paracetamol", "acetaminophen", "解毒"],
    "ss-0121": ["Stevens-Johnson", "史蒂文斯", "SJS"],
    "ss-0122": ["unreported", "underreport", "under-report"],
    "ss-0123": ["CYP3A4", "cytochrome P450", "CYP450"],
    "ss-0124": ["steady state", "steady-state", "穩定狀態", "稳态", "half-lives", "半衰期"],
    "ss-0125": ["phase 1", "phase I", "第一期", "第 1 期", "healthy volunteers", "健康受試者"],
    "ss-0126": ["上市", "years to market", "development time"],
    "ss-0127": ["Cohen"],
    "ss-0128": ["Bonferroni"],
    "ss-0129": [
        "likelihood of approval",
        "probability of approval",
        "phase transition",
        "clinical development success",
    ],
    "ss-0130": ["cardiovascular outcomes", "CVOT"],
}

# (id, dept, language, query, tempting facts that must not appear)
ROWS = [
    ("ss-0111", "MA", "zh-Hant", "Atorvastatin 的成人常用起始劑量是多少？", ["10 mg", "20 mg", "10-20"]),
    ("ss-0112", "MA", "zh-Hant", "成人 paracetamol 每日最大劑量是幾克？", ["4 g", "4g", "4 公克", "3 g"]),
    ("ss-0113", "MA", "zh-Hans", "华法林的目标 INR 范围一般是多少？", ["2.0", "3.0", "2-3", "2–3"]),
    ("ss-0114", "MA", "zh-Hans", "阿莫西林治疗成人链球菌咽炎的疗程通常是几天？", ["10 天", "10天", "ten days"]),
    (
        "ss-0115",
        "MA",
        "en",
        "What is the usual adult starting dose of amlodipine for hypertension?",
        ["5 mg", "2.5 mg"],
    ),
    (
        "ss-0116",
        "MA",
        "en",
        "How long is the half-life of ibuprofen in healthy adults?",
        ["2 hours", "2 h", "1.8", "two hours"],
    ),
    (
        "ss-0117",
        "MA",
        "zh-Hans",
        "胰岛素甘精（glargine）一般什么时候注射，一天几次？",
        ["每天一次", "一天一次", "睡前"],
    ),
    (
        "ss-0118",
        "PV",
        "zh-Hant",
        "WHO-UMC 因果關係評估分為哪幾級？",
        # record 84: the commonsense *number* of categories (six) is the out-of-corpus fact PR-S7 needs, next to the names
        ["certain", "probable", "possible", "unlikely", "確定", "很可能", "六級", "六级", "6 級", "6 级", "six categories", "six levels", "unassessable", "conditional"],
    ),
    ("ss-0119", "PV", "zh-Hant", "Naranjo 量表總分多少分以上判定為「很可能」？", ["5", "9", "5-8", "5–8"]),
    (
        "ss-0120",
        "PV",
        "zh-Hans",
        "对乙酰氨基酚（paracetamol）过量的特效解毒剂是什么？",
        ["N-乙酰半胱氨酸", "N-乙醯半胱氨酸", "acetylcysteine", "NAC"],
    ),
    ("ss-0121", "PV", "zh-Hans", "史蒂文斯-约翰逊综合征（SJS）的发生率大约是多少？", ["百万", "million", "1-2", "1–2"]),
    (
        "ss-0122",
        "PV",
        "en",
        "What proportion of serious adverse drug reactions are estimated to go unreported worldwide?",
        ["90%", "94%", "95%", "ninety"],
    ),
    (
        "ss-0123",
        "PV",
        "en",
        "Which enzyme system metabolises most drugs that cause pharmacokinetic interactions?",
        ["CYP3A4", "cytochrome P450", "CYP450"],
    ),
    (
        "ss-0124",
        "PV",
        "en",
        "In pharmacokinetics, how many half-lives does it take a drug to reach steady state?",
        ["4 to 5", "four to five", "4-5", "five half-lives", "4–5"],
    ),
    ("ss-0125", "CO", "zh-Hant", "第一期臨床試驗通常招募多少名健康受試者？", ["20", "80", "20-80", "20–80", "100"]),
    (
        "ss-0126",
        "CO",
        "zh-Hant",
        "一般而言，新藥從第一期試驗到上市平均需要幾年？",
        ["10 年", "10年", "十年", "12 年", "15 年"],
    ),
    ("ss-0127", "CO", "zh-Hans", "Cohen's d 效应量的小、中、大界值分别是多少？", ["0.2", "0.5", "0.8"]),
    ("ss-0128", "CO", "zh-Hans", "Bonferroni 校正是怎么计算调整后显著性水平的？", ["α/m", "除以", "0.05/", "divided"]),
    (
        "ss-0129",
        "CO",
        "en",
        "What percentage of investigational drugs entering phase 1 eventually get approved?",
        ["10%", "12%", "14%", "ten percent"],
    ),
    (
        "ss-0130",
        "CO",
        "en",
        "How many participants does a typical phase 3 cardiovascular outcomes trial enrol?",
        ["thousand", "5,000", "10,000", "5000", "10000"],
    ),
]


def rows() -> list[dict]:
    return [
        sample(
            sid,
            "ungrounded",
            dept,
            lang,
            query,
            expect(UNGROUNDED, ["insufficient_evidence"], must_not_contain=facts),
            slices=["commonsense_bait"],
            topic_terms=TOPIC_TERMS[sid],
        )
        for sid, dept, lang, query, facts in ROWS
    ]
