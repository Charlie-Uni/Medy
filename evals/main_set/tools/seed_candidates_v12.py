"""Seeds for DEC-011 candidate list v1.2 (M5-01, record 89): the documents proposed for the M5 corpus expansion,
one JSON object per line, before any download or licence check. `compile_candidates.py` turns the seeds into schema-
valid candidates (download, hash, page/text counts, licence evidence, TFDA dataset cross-check).

Sources are the ADR-0003 whitelist only (ICH / EMA / FDA / TFDA; WHO material is CC BY-NC-SA and would land in
`research_only`, so none is seeded). Selection rules are in the module-level lists; the TFDA label selection reads the
same-day open-data snapshots (dataset 39 = labels, dataset 36 = licences) that the compiler cross-checks against.

Usage:
  python evals/main_set/tools/seed_candidates_v12.py --fda-json <search-for-guidance.json> \
      --tfda-39 <39_x.csv> --tfda-36 <36_x.csv> --out <seeds.jsonl> [--labels 110 --labels-per-inn 3]
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import urllib.parse
from pathlib import Path

ICH_LANDING_E = "https://www.ich.org/page/efficacy-guidelines"
ICH_LANDING_M = "https://www.ich.org/page/multidisciplinary-guidelines"
ICH_FILES = "https://database.ich.org/sites/default/files/"
ICH_PUBLISHER = "International Council for Harmonisation (ICH)"

# (title, file, dept, version_or_date, landing, note)
ICH = [
    (
        "ICH E1: The Extent of Population Exposure to Assess Clinical Safety for Drugs Intended for Long-Term Treatment of Non-Life-Threatening Conditions",
        "E1_Guideline.pdf",
        "PV",
        "Step 4, 1994-10-27",
        ICH_LANDING_E,
        "用于 PV 部门安全性数据库规模（暴露人数 / 时长）条款检索",
    ),
    (
        "ICH E4: Dose-Response Information to Support Drug Registration",
        "E4_Guideline.pdf",
        "CO",
        "Step 4, 1994-03-10",
        ICH_LANDING_E,
        "CO 部门剂量反应研究设计条款",
    ),
    (
        "ICH E5(R1): Ethnic Factors in the Acceptability of Foreign Clinical Data",
        "E5_R1__Guideline.pdf",
        "CO",
        "Step 4, 1998-02-05",
        ICH_LANDING_E,
        "CO 部门桥接研究 / 族群因素条款",
    ),
    (
        "ICH E16: Biomarkers Related to Drug or Biotechnology Product Development: Context, Structure and Format of Qualification Submissions",
        "E16_Guideline.pdf",
        "CO",
        "Step 4, 2010-08-20",
        ICH_LANDING_E,
        "CO 部门生物标志物资格申请结构",
    ),
    (
        "ICH E11A: Pediatric Extrapolation",
        "ICH_E11A_Guideline_Step4_2024_0821.pdf",
        "CO",
        "Step 4, 2024-08-21",
        ICH_LANDING_E,
        "CO 部门儿科外推框架",
    ),
    (
        "ICH E6(R3) Annex 2: Good Clinical Practice – Additional Considerations for Interventional Clinical Trials",
        "ICH_E6(R3)_Annex%202_Guideline_Step%204_2026_0603_0.pdf",
        "CO",
        "Step 4, 2026-06-03",
        ICH_LANDING_E,
        "CO 部门去中心化 / 实用性试验与真实世界数据的 GCP 考量",
    ),
    (
        "ICH M11: Clinical Electronic Structured Harmonised Protocol (CeSHarP) – Guideline",
        "ICH_Step4_M11_Final_Guideline_2025_1119.pdf",
        "CO",
        "Step 4, 2025-11-19",
        ICH_LANDING_M,
        "CO 部门方案结构与内容",
    ),
    (
        "ICH M4E(R2): The Common Technical Document for the Registration of Pharmaceuticals for Human Use – Efficacy",
        "M4E_R2__Guideline.pdf",
        "CO",
        "Step 4, 2016-06-15",
        ICH_LANDING_M,
        "CO 部门临床模块（2.5 / 2.7 / 5）结构",
    ),
    (
        "ICH E3 Questions & Answers (R1): Structure and Content of Clinical Study Reports",
        "E3_Q%26As_R1_Q%26As.pdf",
        "CO",
        "Q&As (R1), 2012-07-06",
        ICH_LANDING_E,
        "CO 部门 CSR 结构问答",
    ),
    (
        "ICH E14 Questions & Answers (R3): The Clinical Evaluation of QT/QTc Interval Prolongation and Proarrhythmic Potential for Non-Antiarrhythmic Drugs",
        "E14_Q%26As_R3_Q%26As.pdf",
        "CO",
        "Q&As (R3), 2015-12-10",
        ICH_LANDING_E,
        "CO 部门 QT 评价问答",
    ),
    (
        "ICH E2B(R3) Implementation Guide Questions & Answers, version 2.4",
        "ICH_E2B-R3_QA_v2_4_Step4_2022_1202.pdf",
        "PV",
        "Q&As v2.4, 2022-12-02",
        ICH_LANDING_E,
        "用于 PV 部门 ICSR 电子传输数据元素问答",
    ),
    (
        "ICH E2B(R3) Implementation Guide for Electronic Transmission of Individual Case Safety Reports (with Q&A integration) – Step 3 consultation version",
        "ICH_E2B(R3)_EWG_IWG_ICSR_Implementation_Guide_(QA%20integration)_Step3_2025_0718_Assembly_Approved_0.pdf",
        "PV",
        "Step 3 (public consultation), 2025-07-18",
        ICH_LANDING_E,
        "用于 PV 部门 ICSR 数据元素与消息规范（咨询版，非现行终版）",
    ),
    (
        "ICH E2D(R1): Post-Approval Safety Data: Definitions and Standards for Management and Reporting of Individual Case Safety Reports",
        "ICH_E2D(R1)_Step4_FinalGuideline_2025_0819.pdf",
        "PV",
        "Step 4, 2025-08-19",
        ICH_LANDING_E,
        "用于 PV 部门上市后 ICSR 定义、时限与来源（PSP / 社交媒体）条款",
    ),
    (
        "ICH M14: General Principles on Plan, Design and Analysis of Pharmacoepidemiological Studies That Utilize Real-World Data for Safety Assessment of Medicines",
        "ICH_M14_Step4_Final_Guideline_2025_0905.pdf",
        "PV",
        "Step 4, 2025-09-05",
        ICH_LANDING_M,
        "用于 PV 部门真实世界数据安全性研究设计条款",
    ),
]

EMA_PUBLISHER = "European Medicines Agency / Heads of Medicines Agencies"
EMA = "https://www.ema.europa.eu"
GVP_PAGE = f"{EMA}/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/good-pharmacovigilance-practices-gvp"
SIGNAL_PAGE = (
    f"{EMA}/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/signal-management"
)
PSUR_PAGE = f"{EMA}/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/periodic-safety-update-reports-psurs"
MEDERR_PAGE = (
    f"{EMA}/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/medication-errors"
)
GCP_PAGE = (
    f"{EMA}/en/human-regulatory-overview/research-development/compliance-research-development/good-clinical-practice"
)
EV_PAGE = (
    f"{EMA}/en/human-regulatory-overview/research-development/pharmacovigilance-research-development/eudravigilance"
)
RWE_PAGE = f"{EMA}/en/human-regulatory-overview/research-development/scientific-guidelines/clinical-efficacy-safety-guidelines/real-world-evidence-guidelines"
SG = f"{EMA}/en/documents/scientific-guideline/"
RPG = f"{EMA}/en/documents/regulatory-procedural-guideline/"
OTH = f"{EMA}/en/documents/other/"
TF = f"{EMA}/en/documents/template-form/"


def _gl(slug: str) -> str:
    return f"{EMA}/en/{slug}-scientific-guideline"


# (title, pdf_url, landing, dept, note)
EMA_DOCS = [
    # PV — GVP modules / addenda / annexes not yet in the corpus
    (
        "Guideline on good pharmacovigilance practices (GVP) – Module VIII Addendum I – Requirements and recommendations for the submission of information on non-interventional post-authorisation safety studies (Rev 3)",
        SG
        + "guideline-good-pharmacovigilance-practices-gvp-module-viii-addendum-i-requirements-and-recommendations-submission-information-non-interventional-post-authorisation-safety-studies-rev-3_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门 PASS 信息递交要求条款",
    ),
    (
        "Guideline on good pharmacovigilance practices (GVP) – Module XVI Addendum I – Risk minimisation measures for medicinal products with embryo-fetal risks",
        SG
        + "guideline-good-pharmacovigilance-practices-gvp-module-xvi-addendum-i-risk-minimisation-measures-medicinal-products-embryo-fetal-risks_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门胚胎-胎儿风险的风险最小化措施条款",
    ),
    (
        "Guideline on good pharmacovigilance practices (GVP) – Module XVI Addendum II – Methods for evaluating the effectiveness of risk minimisation measures",
        RPG
        + "guideline-good-pharmacovigilance-practices-gvp-module-xvi-addendum-ii-methods-evaluating-effectiveness-risk-minimisation-measures_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门风险最小化措施有效性评估方法",
    ),
    (
        "Guideline on good pharmacovigilance practices (GVP) – Product- or Population-Specific Considerations II: Biological medicinal products",
        SG
        + "guideline-good-pharmacovigilance-practices-gvp-product-or-population-specific-considerations-ii-biological-medicinal-products_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门生物制品可追溯性与免疫原性监测条款",
    ),
    (
        "Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Cover page of periodic safety update report (PSUR)",
        SG
        + "guideline-good-pharmacovigilance-practices-annex-ii-templates-cover-page-periodic-safety-update-report-psur_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门 PSUR 封面模板字段",
    ),
    (
        "Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Direct healthcare professional communication (DHPC) (Rev 1)",
        TF
        + "guideline-good-pharmacovigilance-practices-annex-ii-templates-direct-healthcare-professional-communication-dhpc-rev-1_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门 DHPC 模板要素",
    ),
    (
        "Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Communication plan for direct healthcare professional communication (CP-DHPC)",
        TF
        + "guideline-good-pharmacovigilance-practices-gvp-annex-ii-templates-communication-plan-direct-healthcare-professional-communication-cp-dhpc_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门 DHPC 沟通计划模板",
    ),
    (
        "Guideline on good pharmacovigilance practices (GVP) – Annex V – Abbreviations (Rev 1)",
        SG + "guideline-good-pharmacovigilance-practices-annex-v-abbreviations-rev-1_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门 GVP 缩略语解析",
    ),
    (
        "Guideline on good pharmacovigilance practices (GVP) – Module VII – Periodic safety update report: Explanatory note",
        SG
        + "guideline-good-pharmacovigilance-practices-gvp-module-vii-periodic-safety-update-report-explanatory-note_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门 PSUR 撰写说明",
    ),
    (
        "Good practice guide on recording, coding, reporting and assessment of medication errors",
        RPG + "good-practice-guide-recording-coding-reporting-and-assessment-medication-errors_en.pdf",
        MEDERR_PAGE,
        "PV",
        "用于 PV 部门用药错误记录、编码与报告条款",
    ),
    (
        "Good practice guide on risk minimisation and prevention of medication errors",
        RPG + "good-practice-guide-risk-minimisation-and-prevention-medication-errors_en.pdf",
        MEDERR_PAGE,
        "PV",
        "用于 PV 部门用药错误风险最小化条款",
    ),
    (
        "Risk minimisation strategy for high-strength and fixed-combination insulin products – Addendum to the good practice guide on risk minimisation and prevention of medication errors",
        RPG
        + "risk-minimisation-strategy-high-strength-and-fixed-combination-insulin-products-addendum-good-practice-guide-risk-minimisation-and-prevention-medication-errors_en.pdf",
        MEDERR_PAGE,
        "PV",
        "用于 PV 部门高浓度胰岛素用药错误风险最小化",
    ),
    (
        "Questions and answers on the periodic safety update report single assessment (PSUSA) – guidance document for assessors",
        RPG
        + "questions-answers-periodic-safety-update-report-single-assessment-psusa-guidance-document-assessors_en.pdf",
        PSUR_PAGE,
        "PV",
        "用于 PV 部门 PSUSA 程序问答",
    ),
    (
        "Pharmacovigilance Risk Assessment Committee (PRAC) – Rules of Procedure",
        OTH + "prac-rules-procedure_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门 PRAC 程序规则",
    ),
    (
        "Guideline on key aspects for the use of pharmacogenomics in the pharmacovigilance of medicinal products",
        SG + "guideline-key-aspects-use-pharmacogenomics-pharmacovigilance-medicinal-products_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门药物基因组学与药物警戒条款",
    ),
    (
        "Guidelines on good pharmacovigilance practices (GVP) – Introductory cover note (last updated with revision 2 of Module III)",
        SG
        + "guidelines-good-pharmacovigilance-practices-gvp-introductory-cover-note-last-updated-revision-2-module-iii-pharmacovigilance-inspections_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门 GVP 模块总览与生效日期",
    ),
    (
        "Reporting requirements for marketing authorisation holders in the EU regarding suspected adverse reactions occurring with medicinal products they donate outside the EU to public health programmes",
        OTH
        + "reporting-requirements-marketing-authorisation-holders-european-union-eu-regarding-suspected-adverse-reactions-occurring-medicinal-products-they-donate-outside-eu-public-health-programmes-against_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门捐赠药品的不良反应报告要求",
    ),
    (
        "Screening for adverse reactions in EudraVigilance",
        OTH + "screening-adverse-reactions-eudravigilance_en.pdf",
        SIGNAL_PAGE,
        "PV",
        "用于 PV 部门 EudraVigilance 信号筛查方法",
    ),
    (
        "Questions and answers on signal management",
        OTH + "questions-answers-signal-management_en.pdf",
        SIGNAL_PAGE,
        "PV",
        "用于 PV 部门信号管理问答",
    ),
    (
        "Questions and answers on Implementing Regulation (EU) 2025/1466 amending Regulation (EU) No 520/2012 – conclusion of the signal detection in EudraVigilance pilot for marketing authorisation holders",
        OTH
        + "questions-answers-implementing-regulation-eu-2025-1466-amendment-regulation-eu-no-520-2012-conclusion-signal-detection-eudravigilance-pilot-marketing-authorisation-holders_en.pdf",
        SIGNAL_PAGE,
        "PV",
        "用于 PV 部门 MAH 在 EudraVigilance 中的信号检测义务",
    ),
    (
        "Periodic safety update report (PSUR) repository – mandatory use: questions and answers",
        RPG + "periodic-safety-update-report-psur-repository-mandatory-use-questions-and-answers_en.pdf",
        PSUR_PAGE,
        "PV",
        "用于 PV 部门 PSUR 递交库使用问答",
    ),
    (
        "Introductory cover note to the list of European Union reference dates and frequency of submission of periodic safety update reports (EURD list)",
        OTH
        + "introductory-cover-note-list-european-union-reference-dates-frequency-submission-periodic-safety-update-reports_en.pdf",
        PSUR_PAGE,
        "PV",
        "用于 PV 部门 EURD 清单与 PSUR 递交频率规则",
    ),
    (
        "Guideline on registry-based studies",
        SG + "guideline-registry-based-studies_en.pdf",
        _gl("guideline-registry-based-studies"),
        "PV",
        "用于 PV 部门基于登记的安全性研究设计条款",
    ),
    (
        "Guideline on the exposure to medicinal products during pregnancy: need for post-authorisation data",
        RPG + "guideline-exposure-medicinal-products-during-pregnancy-need-post-authorisation-data_en.pdf",
        GVP_PAGE,
        "PV",
        "用于 PV 部门妊娠暴露上市后数据收集条款",
    ),
    (
        "Guideline on the use of statistical signal detection methods in the EudraVigilance data analysis system",
        RPG + "guideline-use-statistical-signal-detection-methods-eudravigilance-data-analysis-system_en.pdf",
        SIGNAL_PAGE,
        "PV",
        "用于 PV 部门统计学信号检测方法（SDR）条款",
    ),
    (
        "EU Individual Case Safety Report (ICSR) Implementation Guide",
        RPG + "european-union-individual-case-safety-report-icsr-implementation-guide_en.pdf",
        EV_PAGE,
        "PV",
        "用于 PV 部门 EU ICSR 电子报告实施要求",
    ),
    (
        "Guide on the interpretation of spontaneous case reports of suspected adverse reactions to medicines",
        f"{EMA}/en/documents/report/guide-interpretation-spontaneous-case-reports-suspected-adverse-reactions-medicines_en.pdf",
        EV_PAGE,
        "PV",
        "用于 PV 部门自发报告解读要点",
    ),
    (
        "Reporting requirements of Individual Case Safety Reports (ICSRs) applicable to marketing authorisation holders during the interim period",
        RPG + "reporting-requirements-individual-case-safety-reports-applicable-marketing-authorisation-holders_en.pdf",
        EV_PAGE,
        "PV",
        "用于 PV 部门 MAH 的 ICSR 报告要求",
    ),
    (
        "Reflection paper on use of real-world data in non-interventional studies to generate real-world evidence for regulatory purposes",
        OTH
        + "reflection-paper-use-real-world-data-non-interventional-studies-generate-real-world-evidence-regulatory-purposes_en.pdf",
        RWE_PAGE,
        "PV",
        "用于 PV 部门非干预性研究真实世界证据条款",
    ),
    # CO — methodology / GCP
    (
        "Guideline on computerised systems and electronic data in clinical trials",
        RPG + "guideline-computerised-systems-and-electronic-data-clinical-trials_en.pdf",
        GCP_PAGE,
        "CO",
        "CO 部门临床试验计算机化系统与电子数据要求",
    ),
    (
        "Guideline on the content, management and archiving of the clinical trial master file (paper and/or electronic)",
        SG + "guideline-content-management-and-archiving-clinical-trial-master-file-paper-andor-electronic_en.pdf",
        GCP_PAGE,
        "CO",
        "CO 部门 TMF 内容、管理与归档",
    ),
    (
        "Guideline on strategies to identify and mitigate risks for first-in-human and early clinical trials with investigational medicinal products (Rev 1)",
        SG
        + "guideline-strategies-identify-and-mitigate-risks-first-human-and-early-clinical-trials-investigational-medicinal-products-revision-1_en.pdf",
        _gl("strategies-identify-mitigate-risks-first-human-early-clinical-trials-investigational-medicinal-products"),
        "CO",
        "CO 部门首次人体试验风险控制",
    ),
    (
        "Guideline on data monitoring committees",
        SG + "guideline-data-monitoring-committees_en.pdf",
        _gl("data-monitoring-committees"),
        "CO",
        "CO 部门 DMC 设立与运作",
    ),
    (
        "Questions and answers on Data Monitoring Committees issues",
        SG + "questions-and-answers-data-monitoring-committees-issues_en.pdf",
        _gl("data-monitoring-committees-issues"),
        "CO",
        "CO 部门 DMC 问答",
    ),
    (
        "Guideline on missing data in confirmatory clinical trials",
        SG + "guideline-missing-data-confirmatory-clinical-trials_en.pdf",
        _gl("missing-data-confirmatory-clinical-trials"),
        "CO",
        "CO 部门缺失数据处理",
    ),
    (
        "Guideline on adjustment for baseline covariates in clinical trials",
        SG + "guideline-adjustment-baseline-covariates-clinical-trials_en.pdf",
        _gl("adjustment-baseline-covariates-clinical-trials"),
        "CO",
        "CO 部门基线协变量调整",
    ),
    (
        "Guideline on the investigation of subgroups in confirmatory clinical trials",
        SG + "guideline-investigation-subgroups-confirmatory-clinical-trials_en.pdf",
        _gl("investigation-subgroups-confirmatory-clinical-trials"),
        "CO",
        "CO 部门亚组分析",
    ),
    (
        "Guideline on clinical trials in small populations",
        SG + "guideline-clinical-trials-small-populations_en.pdf",
        _gl("clinical-trials-small-populations"),
        "CO",
        "CO 部门小样本人群试验",
    ),
    (
        "Guideline on the choice of the non-inferiority margin",
        SG + "guideline-choice-non-inferiority-margin_en.pdf",
        _gl("non-inferiority-equivalence-comparisons-clinical-trials"),
        "CO",
        "CO 部门非劣效界值选择",
    ),
    (
        "Points to consider on multiplicity issues in clinical trials",
        SG + "points-consider-multiplicity-issues-clinical-trials_en.pdf",
        _gl("multiplicity-issues-clinical-trials"),
        "CO",
        "CO 部门多重性问题",
    ),
    (
        "Reflection paper on methodological issues in confirmatory clinical trials planned with an adaptive design",
        SG + "reflection-paper-methodological-issues-confirmatory-clinical-trials-planned-adaptive-design_en.pdf",
        _gl("methodological-issues-confirmatory-clinical-trials-planned-adaptive-design"),
        "CO",
        "CO 部门适应性设计方法学",
    ),
    (
        "Reflection paper on ethical and GCP aspects of clinical trials of medicinal products for human use conducted outside of the EU/EEA and submitted in marketing authorisation applications to the EU regulatory authorities",
        RPG
        + "reflection-paper-ethical-and-good-clinical-practice-aspects-clinical-trials-medicinal-products-human-use-conducted-outside-european-union-eu-european-economic-area-and-submitted-marketing-autho_en.pdf",
        GCP_PAGE,
        "CO",
        "CO 部门 EU 外试验的伦理与 GCP 要求",
    ),
    (
        "Scientific guidance on post-authorisation efficacy studies",
        SG + "scientific-guidance-post-authorisation-efficacy-studies-first-version_en.pdf",
        _gl("scientific-guidance-post-authorisation-efficacy-studies"),
        "CO",
        "CO 部门上市后疗效研究",
    ),
    (
        "Guideline on clinical development of fixed combination medicinal products (Rev 2)",
        SG + "guideline-clinical-development-fixed-combination-medicinal-products-revision-2_en.pdf",
        _gl("clinical-development-fixed-combination-medicinal-products"),
        "CO",
        "CO 部门固定复方临床开发",
    ),
    (
        "Data Quality Framework for EU medicines regulation",
        RPG + "data-quality-framework-eu-medicines-regulation_en.pdf",
        RWE_PAGE,
        "CO",
        "CO 部门数据质量维度与评估框架",
    ),
    (
        "Position paper on the non-acceptability of replacement of pivotal clinical trials in cases of GCP non-compliance in the context of marketing authorisation applications",
        OTH
        + "position-paper-non-acceptability-replacement-pivotal-clinical-trials-cases-gcp-non-compliance-context-marketing-authorisation-applications_en.pdf",
        GCP_PAGE,
        "CO",
        "CO 部门 GCP 不合规的后果",
    ),
    # MA — product information
    (
        "Quality Review of Documents (QRD) convention to be followed for the European Medicines Agency product information",
        RPG + "quality-review-documents-qrd-convention-be-followed-european-medicines-agency-qrd-templates_en.pdf",
        PSUR_PAGE,
        "MA",
        "MA 部门产品信息（SmPC / PL）格式约定",
    ),
    (
        "Guideline on risk assessment of medicinal products on human reproduction and lactation: from data to labelling",
        SG + "guideline-risk-assessment-medicinal-products-human-reproduction-and-lactation-data-labelling_en.pdf",
        _gl("risk-assessment-medicinal-products-human-reproduction-lactation-data-labelling"),
        "MA",
        "MA 部门 SmPC 4.6 妊娠哺乳标签措辞规则",
    ),
]

FDA_PUBLISHER = "U.S. Food and Drug Administration (CDER/CBER)"
# media id -> (dept, note)
FDA_MEDIA = {
    # MA — labeling content / promotional communication
    71836: ("MA", "MA 部门 PLR 格式标签的章节与格式要求"),
    71866: ("MA", "MA 部门警告与注意事项 / 禁忌 / 黑框警告章节"),
    72139: ("MA", "MA 部门不良反应章节内容与格式"),
    72140: ("MA", "MA 部门临床研究章节内容与格式"),
    74346: ("MA", "MA 部门临床药理章节内容与格式"),
    86734: ("MA", "MA 部门患者咨询信息章节"),
    72142: ("MA", "MA 部门用法用量章节（草案）"),
    114443: ("MA", "MA 部门适应症与用法章节（草案）"),
    182893: ("MA", "MA 部门药物相互作用信息（草案）"),
    90160: ("MA", "MA 部门妊娠、哺乳与生殖潜能章节（草案）"),
    84949: ("MA", "MA 部门儿科信息标签"),
    142162: ("MA", "MA 部门老年信息标签（草案）"),
    128443: ("MA", "MA 部门药物滥用与依赖章节（草案）"),
    128446: ("MA", "MA 部门患者使用说明（IFU）"),
    172571: ("MA", "MA 部门按体重 / 体表面积给药的标签表述"),
    170814: ("MA", "MA 部门 QTc 信息标签表述"),
    77834: ("MA", "MA 部门已确立药理类别"),
    96894: ("MA", "MA 部门生物类似药标签"),
    169803: ("MA", "MA 部门 DTC 推广材料中的定量疗效与风险信息"),
    175074: ("MA", "MA 部门 DTC 广告主要陈述的呈现"),
    87202: ("MA", "MA 部门推广材料中产品名称的呈现"),
    76269: ("MA", "MA 部门推广中的风险信息呈现（草案）"),
    82660: ("MA", "MA 部门回应未经请求的标签外信息请求（草案）"),
    133619: ("MA", "MA 部门与标签一致的医学产品沟通问答"),
    184871: ("MA", "MA 部门向医疗专业人员传播未批准用途的科学信息（SIUU）"),
    # PV — pharmacovigilance / risk management / postmarketing reporting
    71546: ("PV", "用于 PV 部门药物警戒实践与药物流行病学评估（信号识别 / 评估）"),
    71650: ("PV", "用于 PV 部门上市前风险评估"),
    71268: ("PV", "用于 PV 部门风险最小化行动计划（RiskMAP）"),
    85520: ("PV", "用于 PV 部门以 PBRER 格式递交定期安全性报告"),
    73593: ("PV", "用于 PV 部门上市后安全性报告（草案）"),
    71635: ("PV", "用于 PV 部门上市后不良经历报告范围澄清"),
    77846: ("PV", "用于 PV 部门 REMS 文件格式与内容"),
    128651: ("PV", "用于 PV 部门 REMS 修改与修订"),
    100307: ("PV", "用于 PV 部门判断是否需要 REMS 的法定因素"),
    178291: ("PV", "用于 PV 部门 REMS 逻辑模型（草案）"),
    119789: ("PV", "用于 PV 部门 REMS 知识目标的调查方法（草案）"),
    113869: ("PV", "用于 PV 部门共享系统 REMS（草案）"),
    79776: ("PV", "用于 PV 部门用药指南分发要求与 REMS"),
    76667: ("PV", "用于 PV 部门用药指南中不良事件报告电话"),
    116594: ("PV", "用于 PV 部门 505(o)(4) 安全性标签变更"),
    131980: ("PV", "用于 PV 部门 505(o)(3) 上市后研究与临床试验要求"),
    82664: ("PV", "用于 PV 部门晚期 / 上市后研究安全性数据收集范围"),
    84903: ("PV", "用于 PV 部门产品设计以减少用药错误"),
    158522: ("PV", "用于 PV 部门容器标签与外盒设计以减少用药错误"),
    88496: ("PV", "用于 PV 部门处方药商品名开发最佳实践（用药错误预防）"),
    72144: ("PV", "用于 PV 部门商品名评估递交内容"),
    116737: ("PV", "用于 PV 部门药物性肝损伤的上市前评价"),
    79482: ("PV", "用于 PV 部门自杀意念与行为前瞻性评估（草案）"),
    116739: ("PV", "用于 PV 部门滥用潜力评估"),
    117976: ("PV", "用于 PV 部门安全性 Meta 分析（草案）"),
    132096: ("PV", "用于 PV 部门电子 ICSR 与附件递交规范"),
    72498: ("PV", "用于 PV 部门大流行期间上市后不良事件报告"),
    77193: ("PV", "用于 PV 部门无批准申请的非处方药上市后不良事件报告"),
    71176: ("PV", "用于 PV 部门上市后安全性报告电子递交"),
    172038: ("PV", "用于 PV 部门上市后要求 / 承诺年度状态报告"),
    72535: ("PV", "用于 PV 部门上市后研究承诺状态报告"),
    # CO — clinical operations / GCP / trial design
    167696: ("CO", "CO 部门去中心化要素临床试验"),
    166215: ("CO", "CO 部门临床研究中的电子系统、电子记录与电子签名问答"),
    164960: ("CO", "CO 部门外部对照试验设计（草案）"),
    164561: ("CO", "CO 部门研究者取消资格程序"),
    161740: ("CO", "CO 部门涉及儿童的临床研究伦理考量（草案）"),
    155022: ("CO", "CO 部门数字健康技术远程数据采集"),
    148810: ("CO", "CO 部门 Form FDA 1572 常见问题（草案）"),
    78495: ("CO", "CO 部门适应性设计"),
    121320: ("CO", "CO 部门富集策略"),
    133660: ("CO", "CO 部门有效性实质证据（草案）"),
    162416: ("CO", "CO 部门多重终点"),
    78504: ("CO", "CO 部门非劣效试验"),
    120721: ("CO", "CO 部门肿瘤主方案设计"),
    75398: ("CO", "CO 部门数据监查委员会设立与运作"),
    75152: ("CO", "CO 部门 IRB 要求豁免"),
    116850: ("CO", "CO 部门电子知情同意问答"),
    75453: ("CO", "CO 部门种族与民族数据收集"),
    176308: ("CO", "CO 部门 IND 下试验用药收费问答"),
    162793: ("CO", "CO 部门扩大使用问答"),
    85183: ("CO", "CO 部门电子源数据"),
    79386: ("CO", "CO 部门判断研究是否需要 IND"),
    85294: ("CO", "CO 部门 IRB 审查研究者资质与研究场所"),
    80554: ("CO", "CO 部门急救研究的知情同意豁免"),
    85293: ("CO", "CO 部门研究者财务披露"),
    83209: ("CO", "CO 部门接受非 IND 境外临床研究问答"),
    83121: ("CO", "CO 部门 IRB 持续审查"),
    82634: ("CO", "CO 部门知情同意要素 21 CFR 50.25(c) 问答"),
    75138: ("CO", "CO 部门受试者退出后的数据保留"),
    75414: ("CO", "CO 部门 Part 11 电子记录范围与适用"),
    179027: ("CO", "CO 部门 BIMO 检查流程与做法"),
    171667: ("CO", "CO 部门真实世界数据 / 证据支持监管决策的考量"),
}

TFDA_PUBLISHER = "衛生福利部食品藥物管理署 (Taiwan Food and Drug Administration)"
TW = "https://www.fda.gov.tw"
# (title, pdf_url, landing, dept, version_or_date, note)
TFDA_DOCS = [
    (
        "藥品優良安全監視規範（Guidance for Good Pharmacovigilance Practice）",
        f"{TW}/upload/133/2014122815052015960.pdf",
        f"{TW}/TC/siteList.aspx?sid=4221",
        "PV",
        "2014 年 12 月版（文内以 PDF 首页为准）",
        "用于 PV 部门藥品安全監視體系、通報與風險管理條款檢索",
    ),
    (
        "藥品安全監視管理辦法",
        f"{TW}/tc/includes/GetFile.ashx?id=f637854534540331290",
        f"{TW}/TC/siteList.aspx?sid=4221",
        "PV",
        "現行條文（以 PDF 首页发布日期为准）",
        "用于 PV 部门新藥安全監視期間、定期安全性報告義務條款檢索",
    ),
    (
        "新藥採用藥品定期安全性報告格式及檢送時程說明",
        f"{TW}/tc/includes/GetFile.ashx?id=f636694195066433977&type=2&cid=22251",
        f"{TW}/TC/siteList.aspx?sid=4252",
        "PV",
        "以 PDF 首页公告文号 / 日期为准",
        "用于 PV 部门 PSUR 格式與檢送時程條款檢索",
    ),
    (
        "藥品定期安全性報告－總結報告格式（97 年 5 月 26 日衛署藥字第 0970318606 號公告）",
        f"{TW}/tc/includes/GetFile.ashx?id=f636694195068322990&type=2&cid=10145",
        f"{TW}/TC/siteList.aspx?sid=4252",
        "PV",
        "2008-05-26 公告",
        "用于 PV 部门監視期滿總結報告格式檢索",
    ),
    (
        "藥品定期安全性報告之通報格式（94 年 12 月 2 日衛署藥字第 0940336107 號公告）",
        f"{TW}/tc/includes/GetFile.ashx?id=f636694195068472869&type=2&cid=10144",
        f"{TW}/TC/siteList.aspx?sid=4252",
        "PV",
        "2005-12-02 公告",
        "用于 PV 部门定期安全性報告通報格式檢索",
    ),
    (
        "藥品風險評估及管控計畫書應載明項目",
        f"{TW}/tc/includes/GetFile.ashx?id=f638152601029825739&type=4",
        f"{TW}/TC/siteContent.aspx?sid=4234",
        "PV",
        "以 PDF 内容为准（2023 年上網）",
        "用于 PV 部门 RMP 計畫書應載明項目檢索",
    ),
    (
        "不良反應通報收（退）件作業原則",
        f"{TW}/tc/includes/GetFile.ashx?mid=133&id=10142&t=s",
        f"{TW}/TC/siteContent.aspx?sid=4240",
        "PV",
        "以 PDF 内容为准",
        "用于 PV 部门不良反應通報收件 / 退件規則檢索",
    ),
    (
        "上市後疫苗不良事件通報表填寫指引",
        f"{TW}/tc/includes/GetFile.ashx?mid=133&id=10139&t=s",
        f"{TW}/TC/siteContent.aspx?sid=4240",
        "PV",
        "以 PDF 内容为准",
        "用于 PV 部门疫苗不良事件通報欄位與時限檢索",
    ),
    # 藥品安全資訊風險溝通表 (TFDA safety communications) are published as .docx and were dropped: spec-v1 is PDF-only.
    (
        "藥品優良臨床試驗作業準則（民國 109 年 8 月 28 日修正）",
        f"{TW}/tc/includes/GetFile.ashx?id=f637463084180627995&type=2&cid=35750",
        f"{TW}/TC/siteContent.aspx?sid=4259",
        "CO",
        "2020-08-28 修正",
        "CO 部門 GCP 準則（受試者保護、IRB、試驗委託者與研究者責任）",
    ),
    (
        "藥品臨床試驗申請須知（中華民國 114 年 12 月）",
        f"{TW}/tc/includes/GetFile.ashx?id=f639017353524863682",
        f"{TW}/TC/siteContent.aspx?sid=4259",
        "CO",
        "2025 年 12 月版",
        "CO 部門臨床試驗申請文件與程序",
    ),
    # 藥品臨床試驗計畫－技術性文件指引 is served as .docx (dropped for the same reason).
    (
        "銜接性試驗基準（接受國外臨床資料之族群因素考量）",
        f"{TW}/tc/includes/GetFile.ashx?id=f636694507047553230",
        f"{TW}/TC/siteContent.aspx?sid=4259",
        "CO",
        "以 PDF 首页版本为准",
        "CO 部門銜接性試驗評估與族群因素",
    ),
    (
        "人類細胞治療產品臨床試驗申請作業及審查基準（中華民國 103 年 9 月 17 日）",
        f"{TW}/upload/133/2015010709495342651.pdf",
        f"{TW}/TC/siteContent.aspx?sid=4259",
        "CO",
        "2014-09-17",
        "CO 部門細胞治療產品臨床試驗申請與審查",
    ),
    (
        "藥品仿單全面電子結構化及無紙化分階段實施時程及方法（衛授食字第 1141418097 號公告附件）",
        f"{TW}/tc/includes/GetFile.ashx?id=f638895681180803149",
        f"{TW}/tc/newsContent.aspx?cid=3&id=31155",
        "MA",
        "2025-07-31 公告",
        "MA 部門處方藥仿單格式表與電子結構化時程",
    ),
    (
        "西藥非處方藥仿單外盒格式及規範（公告）",
        f"{TW}/tc/includes/GetFile.ashx?id=f636694193725128085&type=1",
        f"{TW}/Tc/site.aspx?sid=9601",
        "MA",
        "以 PDF 公告文号 / 日期为准",
        "MA 部門非處方藥仿單與外盒應刊載事項",
    ),
    (
        "西藥非處方藥仿單外盒格式及規範 Q&A",
        f"{TW}/tc/includes/GetFile.ashx?id=f636694233382078946&type=1",
        f"{TW}/Tc/siteListContent.aspx?sid=7835&id=22260",
        "MA",
        "以 PDF 内容为准",
        "MA 部門非處方藥仿單外盒格式問答",
    ),
]

# Active ingredients already represented by labels in the corpus (v1.1 signed set); skipped here.
INN_HAVE = "metformin allopurinol losartan metoprolol esomeprazole valsartan quetiapine lamotrigine ciprofloxacin diclofenac amoxicillin tamsulosin loratadine glimepiride levocetirizine clopidogrel ondansetron enalapril bisoprolol digoxin amlodipine atorvastatin".split()
# Target list in therapeutic-class order; one label per INN.
INN_TARGETS = """simvastatin rosuvastatin pravastatin ezetimibe fenofibrate
sitagliptin linagliptin empagliflozin dapagliflozin pioglitazone gliclazide acarbose repaglinide
telmisartan irbesartan candesartan nifedipine felodipine carvedilol atenolol propranolol furosemide spironolactone indapamide doxazosin
rivaroxaban apixaban dabigatran ticagrelor cilostazol warfarin amiodarone isosorbide nitroglycerin ivabradine
pantoprazole lansoprazole rabeprazole omeprazole famotidine domperidone metoclopramide mosapride loperamide mesalazine ursodeoxycholic
sertraline escitalopram fluoxetine paroxetine venlafaxine duloxetine mirtazapine bupropion trazodone
olanzapine risperidone aripiprazole haloperidol lithium alprazolam lorazepam zolpidem clonazepam diazepam
levetiracetam valproate carbamazepine topiramate gabapentin pregabalin phenytoin
celecoxib ibuprofen naproxen meloxicam etoricoxib tramadol
montelukast salbutamol theophylline fexofenadine
finasteride dutasteride solifenacin tadalafil sildenafil
levothyroxine methimazole propylthiouracil prednisolone dexamethasone methylprednisolone alendronate raloxifene
colchicine febuxostat hydroxychloroquine methotrexate sulfasalazine leflunomide
donepezil memantine betahistine flunarizine sumatriptan
azithromycin clarithromycin cefuroxime cephalexin cefixime levofloxacin moxifloxacin doxycycline metronidazole fluconazole acyclovir valacyclovir oseltamivir nitrofurantoin sulfamethoxazole
entecavir tenofovir letrozole anastrozole tamoxifen bicalutamide capecitabine imatinib
folic calcitriol cinacalcet sevelamer
glipizide glibenclamide vildagliptin saxagliptin nateglinide
nebivolol labetalol diltiazem verapamil hydralazine torsemide eplerenone terazosin prazosin
rosuvastatin pitavastatin fluvastatin gemfibrozil
prasugrel dipyridamole ranolazine trimetazidine ramipril lisinopril captopril perindopril quinapril benazepril fosinopril
oxybutynin tolterodine mirabegron alfuzosin silodosin
benzbromarone probenecid ketorolac mefenamic indomethacin piroxicam nabumetone baclofen tizanidine
clozapine sulpiride amisulpride paliperidone flupentixol chlorpromazine imipramine amitriptyline clomipramine doxepin
citalopram fluvoxamine buspirone hydroxyzine oxazepam estazolam zopiclone
oxcarbazepine lacosamide zonisamide clobazam primidone
levodopa pramipexole ropinirole selegiline rasagiline amantadine trihexyphenidyl biperiden rivastigmine galantamine piracetam
cinnarizine dimenhydrinate meclizine prochlorperazine granisetron lactulose bisacodyl sennoside hyoscine mebeverine itopride
cimetidine ranitidine nizatidine sucralfate misoprostol rebamipide teprenone silymarin
budesonide prednisone hydrocortisone betamethasone triamcinolone fludrocortisone carbimazole liothyronine
ibandronate risedronate cabergoline bromocriptine clomiphene estradiol progesterone medroxyprogesterone norethisterone dydrogesterone
exemestane flutamide abiraterone erlotinib gefitinib temozolomide cyclophosphamide mercaptopurine azathioprine mycophenolate
tacrolimus cyclosporine sirolimus everolimus hydroxyurea tranexamic pyridoxine thiamine alfacalcidol
penicillin ampicillin cloxacillin flucloxacillin dicloxacillin cefaclor cefadroxil cefazolin cefotaxime ceftriaxone ceftazidime cefepime cefoperazone
meropenem imipenem ertapenem gentamicin amikacin vancomycin teicoplanin linezolid clindamycin erythromycin roxithromycin minocycline tetracycline
norfloxacin ofloxacin rifampicin isoniazid ethambutol pyrazinamide colistin fosfomycin itraconazole voriconazole terbinafine nystatin
clotrimazole ketoconazole albendazole mebendazole praziquantel chloroquine ribavirin lamivudine ganciclovir famciclovir
fluticasone beclomethasone salmeterol formoterol terbutaline ipratropium tiotropium aminophylline ambroxol acetylcysteine bromhexine carbocisteine
dextromethorphan codeine guaifenesin chlorpheniramine diphenhydramine promethazine cyproheptadine ketotifen desloratadine ebastine bilastine
acetazolamide timolol latanoprost brimonidine dorzolamide pilocarpine mupirocin fusidic clobetasol mometasone tretinoin adapalene calcipotriol permethrin
lidocaine bupivacaine propofol ketamine fentanyl morphine pethidine naloxone neostigmine atracurium rocuronium heparin enoxaparin
epinephrine norepinephrine dopamine dobutamine adenosine esmolol nicardipine nitroprusside""".split()
FORM_PREF = (
    "錠劑",
    "膜衣錠",
    "膠囊劑",
    "糖衣錠",
    "持續性藥效錠",
    "持續性藥效膠囊",
    "腸溶膜衣錠",
    "口溶錠",
    "軟膠囊劑",
    "內服液劑",
    "糖漿劑",
    "注射劑",
    "乾粉注射劑",
    "凍晶注射劑",
    "散劑",
    "點眼液劑",
    "乳膏劑",
)
TODAY = "2026/09/26"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", " ", s.lower())


def tfda_label_seeds(
    csv39: Path, csv36: Path, limit: int, per_inn: int = 3, *, skip: frozenset[str] = frozenset(), today: str = TODAY
) -> list[dict]:
    """Up to `per_inn` labels per active ingredient for the first `limit` ingredients with any eligible product; the
    compiler tries them in rank order and lists one per INN (image-only scans fall out, so ranks 2/3 are fallbacks)."""
    with csv39.open(encoding="utf-8-sig", newline="") as f:
        labels = {r["許可證字號"]: r for r in csv.DictReader(f)}
    with csv36.open(encoding="utf-8-sig", newline="") as f:
        lic = {r["許可證字號"]: r for r in csv.DictReader(f)}
    pool: dict[str, list[dict]] = {}
    for key, row in labels.items():
        L = lic.get(key)
        if not L:
            continue
        link = row["仿單圖檔連結"]
        if ";" in link or not link.startswith("https://mcp.fda.gov.tw/insert/pdfcasefile/"):
            continue  # ADR-0003 决策 1 条件 (1) 只对上传 PDF 链接可成立
        if L["註銷狀態"] or not L["有效日期"] or L["有效日期"] <= today:
            continue
        if "處方" not in L["藥品類別"] and "限由醫師" not in L["藥品類別"]:
            continue
        comps = [c for c in re.split(r";+|\n", L["主成分略述"]) if c.strip()]
        m = _norm(L["主成分略述"])
        inns = [t for t in INN_TARGETS if t in m]
        if len(inns) != 1 or inns[0] in INN_HAVE or inns[0] in skip:
            continue
        if len(comps) > 1 and not (inns[0] == "sulfamethoxazole" and len(comps) == 2):
            continue  # single-ingredient labels only (SMX/TMP is a standard fixed combination)
        pool.setdefault(inns[0], []).append({"lic": key, **row, **L})
    out = []
    for inn in INN_TARGETS:
        rows = pool.get(inn)
        if not rows:
            continue
        rows.sort(
            key=lambda r: (
                r["製造廠國別"] != "TW",
                FORM_PREF.index(r["劑型"]) if r["劑型"] in FORM_PREF else 99,
                r["異動日期"] or "",
            )
        )
        top = [r for r in rows if r["製造廠國別"] == "TW" and r["劑型"] in FORM_PREF[:9]] or rows
        top.sort(key=lambda r: r["異動日期"] or "", reverse=True)
        rest = [r for r in rows if r not in top]
        for rank, r in enumerate((top + rest)[:per_inn], start=1):
            cn = html.unescape(r["中文品名"]).strip()
            en = html.unescape(r["英文品名"]).strip()
            out.append(
                {
                    "group": "tfda_label",
                    "title": f"{cn}（{en}，{inn}）仿單"[:300],
                    "publisher": f"衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；申請商 {r['申請商名稱']}"[
                        :200
                    ],
                    "language": "zh-Hant",
                    "doc_type": "label",
                    "owner_dept": "MA",
                    "landing_url": "https://mcp.fda.gov.tw/im_detail_1/" + urllib.parse.quote(r["lic"]),
                    "pdf_url": r["仿單圖檔連結"],
                    "registry_id": None,
                    "notes": f"MA 部门繁体仿單需求，{inn} 单一成分（{r['劑型']}，製造廠國別 {r['製造廠國別']}）",
                    "lic": r["lic"],
                    "lic_row": {
                        k: r[k]
                        for k in (
                            "許可證字號",
                            "註銷狀態",
                            "有效日期",
                            "發證日期",
                            "申請商名稱",
                            "製造商名稱",
                            "製造廠國別",
                            "劑型",
                            "藥品類別",
                            "主成分略述",
                        )
                    },
                    "inn": inn,
                    "rank": rank,
                }
            )
        if len({s["inn"] for s in out}) >= limit:
            break
    return out


def fda_seeds(fda_json: Path, media_map: dict[int, tuple[str, str]] | None = None) -> list[dict]:
    """`media_map` (media id -> (dept, note)) replaces the v1.2 FDA_MEDIA selection for a later batch (v1.6+)."""
    rows = json.loads(fda_json.read_text(encoding="utf-8"))

    def strip(s: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()

    def href(s: str) -> str:
        m = re.search(r'href="([^"]+)"', s or "")
        return html.unescape(m.group(1)) if m else ""

    by_media: dict[int, dict] = {}
    for r in rows:
        m = re.search(r"/media/(\d+)/download", href(r.get("field_associated_media_2")))
        if m:
            by_media.setdefault(int(m.group(1)), r)
    out = []
    for media, (dept, note) in (FDA_MEDIA if media_map is None else media_map).items():
        r = by_media.get(media)
        if r is None:
            raise SystemExit(f"FDA media {media} not found in dataset")
        status = strip(r.get("field_final_guidance_1"))
        date = strip(r.get("field_issue_datetime"))
        docket = strip(r.get("field_docket_number")) or None
        landing = href(r["title"])
        out.append(
            {
                "group": "fda",
                "title": strip(r["title"])[:300],
                "publisher": FDA_PUBLISHER,
                "language": "en",
                "doc_type": "guideline",
                "owner_dept": dept,
                "landing_url": ("https://www.fda.gov" + landing) if landing.startswith("/") else landing,
                "pdf_url": f"https://www.fda.gov/media/{media}/download",
                "version_or_date": f"{status} guidance, issued {date}" + (f"; docket {docket}" if docket else ""),
                "registry_id": docket[:60] if docket else None,
                "notes": note,
            }
        )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fda-json", type=Path, required=True)
    p.add_argument("--tfda-39", type=Path, required=True)
    p.add_argument("--tfda-36", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--labels", type=int, default=110, help="number of active ingredients to seed")
    p.add_argument("--labels-per-inn", type=int, default=3)
    p.add_argument("--groups", default="ich,ema,fda,tfda_site,tfda_label", help="comma list of seed groups to emit")
    p.add_argument(
        "--skip-inns", type=Path, default=None, help="JSON list of INNs already tried / listed (later batches)"
    )
    p.add_argument(
        "--today", default=TODAY, help="YYYY/MM/DD used for the licence currency filter (same day as the snapshots)"
    )
    p.add_argument("--fda-media", type=Path, default=None, help="JSON {media_id: [dept, note]} replacing FDA_MEDIA")
    a = p.parse_args()
    groups = {g.strip() for g in a.groups.split(",") if g.strip()}
    skip = frozenset(json.loads(a.skip_inns.read_text(encoding="utf-8"))) if a.skip_inns else frozenset()
    media_map = (
        {int(k): (v[0], v[1]) for k, v in json.loads(a.fda_media.read_text(encoding="utf-8")).items()}
        if a.fda_media
        else None
    )
    seeds: list[dict] = []
    for title, fn, dept, ver, landing, note in ICH if "ich" in groups else []:
        seeds.append(
            {
                "group": "ich",
                "title": title,
                "publisher": ICH_PUBLISHER,
                "language": "en",
                "doc_type": "guideline",
                "owner_dept": dept,
                "landing_url": landing,
                "pdf_url": ICH_FILES + fn,
                "version_or_date": ver,
                "registry_id": None,
                "notes": note,
            }
        )
    for title, pdf, landing, dept, note in EMA_DOCS if "ema" in groups else []:
        seeds.append(
            {
                "group": "ema",
                "title": title,
                "publisher": EMA_PUBLISHER,
                "language": "en",
                "doc_type": "guideline",
                "owner_dept": dept,
                "landing_url": landing,
                "pdf_url": pdf,
                "registry_id": None,
                "notes": note,
            }
        )
    if "fda" in groups:
        seeds.extend(fda_seeds(a.fda_json, media_map))
    for title, pdf, landing, dept, ver, note in TFDA_DOCS if "tfda_site" in groups else []:
        seeds.append(
            {
                "group": "tfda_site",
                "title": title,
                "publisher": TFDA_PUBLISHER,
                "language": "zh-Hant",
                "doc_type": "guideline",
                "owner_dept": dept,
                "landing_url": landing,
                "pdf_url": pdf,
                "version_or_date": ver,
                "registry_id": None,
                "notes": note,
            }
        )
    if "tfda_label" in groups:
        seeds.extend(tfda_label_seeds(a.tfda_39, a.tfda_36, a.labels, a.labels_per_inn, skip=skip, today=a.today))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for s in seeds:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    from collections import Counter

    print(len(seeds), "seeds", dict(Counter((s["group"], s["owner_dept"]) for s in seeds)))


if __name__ == "__main__":
    main()
