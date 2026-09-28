# DEC-011 候选清单 v1.2（M5-01 扩语料，记录 89）

编制：2026-09-26。承接 v1.1（102 条）；本版新增 **230 条**候选，来源限 ADR-0003 白名单（ICH / EMA / FDA / TFDA），每条附同日下载的 SHA-256、页数与文本层字符数；TFDA 仿單另附資料集 39/36 同日快照的逐字核对与现行性字段。`预判` 是机械核对结果，`eligible` 只表示许可依据与已签字候选同源且核对全部通过；签字前请按批回复（如「批 1 确认」或列出例外）。

## 分组汇总

| 分组 | 条数 | 部门 | 预判 eligible | 预判 needs_review | 许可依据 | 签字后待办 |
| --- | ---: | --- | ---: | ---: | --- | --- |
| ICH 指南 | 14 | CO 9, PV 5 | 13 | 1 | ICH Legal Mentions | 按 pdf_url 重新下载比对 sha256；pypdf 抽取页文本 |
| EMA 指南 / 程序文件 | 48 | CO 17, MA 2, PV 29 | 48 | 0 | EMA Legal Notice + 封面 © 声明 | 按 pdf_url 重新下载比对 sha256；pypdf 抽取页文本 |
| FDA 指南 | 87 | CO 31, MA 25, PV 31 | 87 | 0 | fda.gov 公共领域政策 | 按 pdf_url 重新下载比对 sha256；pypdf 抽取页文本 |
| TFDA 指引 / 法規 / 公告 | 12 | CO 4, MA 2, PV 6 | 12 | 0 | TFDA 網站資料開放宣告 + 著作權聲明 | 按 pdf_url 重新下载比对 sha256；pypdf 抽取页文本 |
| TFDA 仿單 | 69 | MA 69 | 66 | 3 | 資料集 9117/39 OGDL-1.0 | 逐页图像层目视（条件 3），入库时署名（条件 4） |

预判 eligible 的部门分布：CO 61, MA 95, PV 70（决策 86 的目标是 MA 120 / PV 120 / CO 80 含现有 79 份）。

## 批 1（cand-0103 – cand-0152，50 条）

| 候选 | 标题 | 语言 | 部门 | 版本/日期 | 页 | 许可依据 | 预判 | 备注 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| cand-0103 | ICH E1: The Extent of Population Exposure to Assess Clinical Safety for Drugs Intended fo… | en | PV | Step 4, 1994-10-27（文内 dated 27 October 1994） | 5 | ICH Legal Mentions（无文内公告，同 E2A/E2F） | eligible |  |
| cand-0104 | ICH E4: Dose-Response Information to Support Drug Registration | en | CO | Step 4, 1994-03-10（文内 dated 10 March 1994） | 14 | ICH Legal Mentions（无文内公告，同 E2A/E2F） | eligible |  |
| cand-0105 | ICH E5(R1): Ethnic Factors in the Acceptability of Foreign Clinical Data | en | CO | Step 4, 1998-02-05（文内 dated 5 February 1998） | 17 | ICH Legal Mentions（无文内公告，同 E2A/E2F） | eligible |  |
| cand-0106 | ICH E16: Biomarkers Related to Drug or Biotechnology Product Development: Context, Struct… | en | CO | Step 4, 2010-08-20（文内 dated 20 August 2010） | 13 | ICH Legal Mentions（无文内公告，同 E2A/E2F） | eligible |  |
| cand-0107 | ICH E11A: Pediatric Extrapolation | en | CO | Step 4, 2024-08-21 | 33 | ICH Legal Mentions+文内公告 | eligible |  |
| cand-0108 | ICH E6(R3) Annex 2: Good Clinical Practice – Additional Considerations for Interventional… | en | CO | Step 4, 2026-06-03 | 15 | ICH Legal Mentions+文内公告 | eligible |  |
| cand-0109 | ICH M11: Clinical Electronic Structured Harmonised Protocol (CeSHarP) – Guideline | en | CO | Step 4, 2025-11-19 | 6 | ICH Legal Mentions+文内公告 | eligible |  |
| cand-0110 | ICH M4E(R2): The Common Technical Document for the Registration of Pharmaceuticals for Hu… | en | CO | Step 4, 2016-06-15（文内 dated 15 June 2016） | 64 | ICH Legal Mentions（无文内公告，同 E2A/E2F） | eligible |  |
| cand-0111 | ICH E3 Questions & Answers (R1): Structure and Content of Clinical Study Reports | en | CO | Q&As (R1), 2012-07-06（文内 dated 6 July 2012） | 11 | ICH Legal Mentions（无文内公告，同 E2A/E2F） | eligible |  |
| cand-0112 | ICH E14 Questions & Answers (R3): The Clinical Evaluation of QT/QTc Interval Prolongation… | en | CO | Q&As (R3), 2015-12-10 | 18 | ICH Legal Mentions+文内公告 | eligible |  |
| cand-0113 | ICH E2B(R3) Implementation Guide Questions & Answers, version 2.4 | en | PV | Q&As v2.4, 2022-12-02 | 30 | ICH Legal Mentions+文内公告 | eligible |  |
| cand-0114 | ICH E2B(R3) Implementation Guide for Electronic Transmission of Individual Case Safety Re… | en | PV | Step 3 (public consultation), 2025-07-18 | 170 | ICH Legal Mentions（无文内公告，同 E2A/E2F） | needs_review | 文本层命中限制标记：all rights reserved「ntly by ISO and Health Level Seven International. ALL RIGHTS」 |
| cand-0115 | ICH E2D(R1): Post-Approval Safety Data: Definitions and Standards for Management and Repo… | en | PV | Step 4, 2025-08-19 | 26 | ICH Legal Mentions+文内公告 | eligible |  |
| cand-0116 | ICH M14: General Principles on Plan, Design and Analysis of Pharmacoepidemiological Studi… | en | PV | Step 4, 2025-09-05 | 44 | ICH Legal Mentions+文内公告 | eligible |  |
| cand-0117 | Guideline on good pharmacovigilance practices (GVP) – Module VIII Addendum I – Requiremen… | en | PV | EMA/395730/2012 Rev 3 (15 June 2020) | 3 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0118 | Guideline on good pharmacovigilance practices (GVP) – Module XVI Addendum I – Risk minimi… | en | PV | EMA/608947/2021 (22 August 2025) | 10 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0119 | Guideline on good pharmacovigilance practices (GVP) – Module XVI Addendum II – Methods fo… | en | PV | EMA/419982/2019 (26 July 2024) | 19 | EMA Legal Notice | eligible |  |
| cand-0120 | Guideline on good pharmacovigilance practices (GVP) – Product- or Population-Specific Con… | en | PV | EMA/168402/2014 Corr (4 August 2016) | 19 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0121 | Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Cover page of… | en | PV | EMA/170043/2013 (19 April 2013) | 2 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0122 | Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Direct health… | en | PV | EMA/36988/2013 Rev 1 (9 October 2017) | 3 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0123 | Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Communication… | en | PV | EMA/334164/2015 (9 October 2017) | 2 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0124 | Guideline on good pharmacovigilance practices (GVP) – Annex V – Abbreviations (Rev 1) | en | PV | EMA/135814/2013 Rev 1 (9 October 2017) | 7 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0125 | Guideline on good pharmacovigilance practices (GVP) – Module VII – Periodic safety update… | en | PV | EMA/670256/2017 Rev. 4 (17 April 2026) | 13 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0126 | Good practice guide on recording, coding, reporting and assessment of medication errors | en | PV | EMA/762563/2014 (23 October 2015) | 42 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0127 | Good practice guide on risk minimisation and prevention of medication errors | en | PV | EMA/606103/2014 (18 November 2015) | 41 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0128 | Risk minimisation strategy for high-strength and fixed-combination insulin products – Add… | en | PV | EMA/686009/2014 (23 October 2015) | 16 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0129 | Questions and answers on the periodic safety update report single assessment (PSUSA) – gu… | en | PV | EMA/518909/2016 Rev 1 (17 April 2026) | 26 | EMA Legal Notice | eligible |  |
| cand-0130 | Pharmacovigilance Risk Assessment Committee (PRAC) – Rules of Procedure | en | PV | EMA/PRAC/567515/2012 Rev.31 (11 October 2021) | 14 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0131 | Guideline on key aspects for the use of pharmacogenomics in the pharmacovigilance of medi… | en | PV | EMA/CHMP/281371/2013 (24 September 2015) | 19 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0132 | Guidelines on good pharmacovigilance practices (GVP) – Introductory cover note (last upda… | en | PV | EMA/165286/2026 (9 September 2026) | 8 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0133 | Reporting requirements for marketing authorisation holders in the EU regarding suspected … | en | PV | EMA/182873/2015 (27 April 2015) | 2 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0134 | Screening for adverse reactions in EudraVigilance | en | PV | EMA/849944/2016 (19 December 2016) | 34 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0135 | Questions and answers on signal management | en | PV | EMA/261758/2013 Rev 5 (19 January 2026) | 9 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0136 | Questions and answers on Implementing Regulation (EU) 2025/1466 amending Regulation (EU) … | en | PV | EMA/243145/2025 Rev. 2 (28 January 2026) | 3 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0137 | Periodic safety update report (PSUR) repository – mandatory use: questions and answers | en | PV | EMA/395434/2016 (9 June 2016) | 2 | EMA Legal Notice | eligible |  |
| cand-0138 | Introductory cover note to the list of European Union reference dates and frequency of su… | en | PV | EMA/606369/2012 Rev.17 (16 July 2019) | 8 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0139 | Guideline on registry-based studies | en | PV | EMA/426390/2021 (22 October 2021) | 35 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0140 | Guideline on the exposure to medicinal products during pregnancy: need for post-authorisa… | en | PV | EMEA/CHMP/313666/2005 (14 November 2005) | 21 | EMA Legal Notice | eligible |  |
| cand-0141 | Guideline on the use of statistical signal detection methods in the EudraVigilance data a… | en | PV | EMEA/106464/2006 (26 June 2008) | 22 | EMA Legal Notice | eligible |  |
| cand-0142 | EU Individual Case Safety Report (ICSR) Implementation Guide | en | PV | EMA/51938/2013 Rev 2 (4 December 2014) | 112 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0143 | Guide on the interpretation of spontaneous case reports of suspected adverse reactions to… | en | PV | EMA/CHMP/PhVWP/646186/2010 (22 June 2011) | 4 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0144 | Reporting requirements of Individual Case Safety Reports (ICSRs) applicable to marketing … | en | PV | EMA/411742/2015 Rev. 9 (29 June 2015) | 4 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0145 | Reflection paper on use of real-world data in non-interventional studies to generate real… | en | PV | EMA/99865/2025 (17 March 2025) | 17 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0146 | Guideline on computerised systems and electronic data in clinical trials | en | CO | EMA/INS/GCP/112288/2023 (9 March 2023) | 52 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0147 | Guideline on the content, management and archiving of the clinical trial master file (pap… | en | CO | EMA/INS/GCP/856758/2018 (06 December 2018) | 17 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0148 | Guideline on strategies to identify and mitigate risks for first-in-human and early clini… | en | CO | 20 July 2017 | 22 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0149 | Guideline on data monitoring committees | en | CO | 27 July 2005 | 8 | EMA Legal Notice | eligible |  |
| cand-0150 | Questions and answers on Data Monitoring Committees issues | en | CO | EMA/CHMP/470185/2020 (17 September 2020) | 5 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0151 | Guideline on missing data in confirmatory clinical trials | en | CO | 2 July 2010 | 12 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0152 | Guideline on adjustment for baseline covariates in clinical trials | en | CO | EMA/CHMP/295050/2013 (26 February 2015) | 11 | EMA Legal Notice + 封面 © 声明 | eligible |  |

## 批 2（cand-0153 – cand-0202，50 条）

| 候选 | 标题 | 语言 | 部门 | 版本/日期 | 页 | 许可依据 | 预判 | 备注 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| cand-0153 | Guideline on the investigation of subgroups in confirmatory clinical trials | en | CO | EMA/CHMP/539146/2013 (31 January 2019) | 20 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0154 | Guideline on clinical trials in small populations | en | CO | CHMP/EWP/83561/2005 (27 July 2006) | 10 | EMA Legal Notice | eligible |  |
| cand-0155 | Guideline on the choice of the non-inferiority margin | en | CO | 27 July 2005 | 11 | EMA Legal Notice | eligible |  |
| cand-0156 | Points to consider on multiplicity issues in clinical trials | en | CO | 19 September 2002 | 11 | EMA Legal Notice | eligible |  |
| cand-0157 | Reflection paper on methodological issues in confirmatory clinical trials planned with an… | en | CO | 18 October 2007 | 10 | EMA Legal Notice | eligible |  |
| cand-0158 | Reflection paper on ethical and GCP aspects of clinical trials of medicinal products for … | en | CO | EMA/121340/2011 (16 April 2012) | 42 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0159 | Scientific guidance on post-authorisation efficacy studies | en | CO | EMA/PDCO/CAT/CMDh/PRAC/CHMP/261500/2015 (12 October 2016) | 14 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0160 | Guideline on clinical development of fixed combination medicinal products (Rev 2) | en | CO | EMA/CHMP/158268/2017 (23 March 2017) | 12 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0161 | Data Quality Framework for EU medicines regulation | en | CO | EMA/326985/2023 (30 October 2023) | 42 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0162 | Position paper on the non-acceptability of replacement of pivotal clinical trials in case… | en | CO | EMA/448853/2015 (26 November 2015) | 3 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0163 | Quality Review of Documents (QRD) convention to be followed for the European Medicines Ag… | en | MA | EMA/62470/2007 (12 April 2011) | 3 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0164 | Guideline on risk assessment of medicinal products on human reproduction and lactation: f… | en | MA | EMEA/CHMP/203927/2005 (24 July 2008) | 18 | EMA Legal Notice + 封面 © 声明 | eligible |  |
| cand-0165 | Labeling for Human Prescription Drug and Biological Products - Implementing the PLR Conte… | en | MA | Final guidance, issued 02/25/2013; docket FDA-2005-D-0153 | 34 | fda.gov 公共领域政策 | eligible |  |
| cand-0166 | Warnings and Precautions, Contraindications, and Boxed Warning Sections of Labeling for H… | en | MA | Final guidance, issued 10/12/2011; docket FDA-2011-D-0694 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0167 | Adverse Reactions Section of Labeling for Human Prescription Drug and Biological Products… | en | MA | Final guidance, issued 01/24/2006; docket FDA-2005-D-0153 | 16 | fda.gov 公共领域政策 | eligible |  |
| cand-0168 | Clinical Studies Section of Labeling for Human Prescription Drug and Biological Products … | en | MA | Final guidance, issued 01/24/2006; docket FDA-2000-D-0074 | 25 | fda.gov 公共领域政策 | eligible |  |
| cand-0169 | Clinical Pharmacology Labeling for Human Prescription Drug and Biological Products — Cont… | en | MA | Final guidance, issued 12/05/2016; docket FDA-2009-D-0095 | 19 | fda.gov 公共领域政策 | eligible |  |
| cand-0170 | Patient Counseling Information Section of Labeling for Human Prescription Drug and Biolog… | en | MA | Final guidance, issued 12/10/2014; docket FDA-2013-D-1067 | 12 | fda.gov 公共领域政策 | eligible |  |
| cand-0171 | Dosage and Administration Section of Labeling for Human Prescription Drug and Biological … | en | MA | Draft guidance, issued 01/12/2023; docket FDA-2007-D-0201 | 36 | fda.gov 公共领域政策 | eligible |  |
| cand-0172 | Indications and Usage Section of Labeling for Human Prescription Drug and Biological Prod… | en | MA | Draft guidance, issued 07/06/2018; docket FDA-2018-D-1895 | 20 | fda.gov 公共领域政策 | eligible |  |
| cand-0173 | Drug Interaction Information in Human Prescription Drug and Biological Product Labeling | en | MA | Draft guidance, issued 10/21/2024; docket FDA-2024-D-3903 | 30 | fda.gov 公共领域政策 | eligible |  |
| cand-0174 | Pregnancy, Lactation, and Reproductive Potential: Labeling for Human Prescription Drug an… | en | MA | Draft guidance, issued 07/29/2020; docket FDA-2014-D-1551 | 35 | fda.gov 公共领域政策 | eligible |  |
| cand-0175 | Pediatric Information Incorporated Into Human Prescription Drug and Biological Products L… | en | MA | Final guidance, issued 03/28/2019; docket FDA-2013-D-0169 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0176 | Geriatric Information in Human Prescription Drug and Biological Product Labeling Guidance… | en | MA | Draft guidance, issued 09/15/2020; docket FDA-2020-D-1621 | 21 | fda.gov 公共领域政策 | eligible |  |
| cand-0177 | Drug Abuse and Dependence Section of Labeling for Human Prescription Drug and Biological … | en | MA | Draft guidance, issued 07/01/2019; docket FDA-2019-D-1917 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0178 | Instructions for Use — Patient Labeling for Human Prescription Drug and Biological Produc… | en | MA | Final guidance, issued 07/15/2022; docket FDA-2019-D-1615 | 22 | fda.gov 公共领域政策 | eligible |  |
| cand-0179 | Human Prescription Drug and Biological Products--Labeling for Dosing Based on Weight or B… | en | MA | Final guidance, issued 10/02/2023; docket FDA-2022-D-0219 | 10 | fda.gov 公共领域政策 | eligible |  |
| cand-0180 | QTc Information in Human Prescription Drug and Biological Product Labeling: Guidance for … | en | MA | Final guidance, issued 12/03/2025; docket FDA-2023-D-2439 | 16 | fda.gov 公共领域政策 | eligible |  |
| cand-0181 | Labeling for Human Prescription Drug and Biological Products — Determining Established Ph… | en | MA | Final guidance, issued 10/19/2009; docket FDA-2007-D-0302 | 9 | fda.gov 公共领域政策 | eligible |  |
| cand-0182 | Labeling for Biosimilar Products Guidance for Industry | en | MA | Final guidance, issued 07/18/2018; docket FDA-2016-D-0643 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0183 | Presenting Quantitative Efficacy and Risk Information in Direct-to-Consumer (DTC) Promoti… | en | MA | Final guidance, issued 12/12/2023; docket FDA-2018-D-2613 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0184 | Direct-to-Consumer Prescription Drug Advertisements: Presentation of the Major Statement … | en | MA | Final guidance, issued 12/26/2023; docket FDA-2009-N-0582 | 9 | fda.gov 公共领域政策 | eligible |  |
| cand-0185 | Product Name Placement, Size, and Prominence in Advertising and Promotional Labeling-Final | en | MA | Final guidance, issued 12/12/2017; docket FDA-1999-D-4079 | 11 | fda.gov 公共领域政策 | eligible |  |
| cand-0186 | Presenting Risk Information in Prescription Drug and Medical Device Promotion | en | MA | Draft guidance, issued 05/27/2009; docket FDA-2008-D-0253 | 27 | fda.gov 公共领域政策 | eligible |  |
| cand-0187 | Responding to Unsolicited Requests for Off-Label Information About Prescription Drugs and… | en | MA | Draft guidance, issued 12/30/2011; docket FDA-2011-D-0868 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0188 | Medical Product Communications That Are Consistent With the FDA-Required Labeling — Quest… | en | MA | Final guidance, issued 06/13/2018; docket FDA-2016-D-2285 | 22 | fda.gov 公共领域政策 | eligible |  |
| cand-0189 | Communications From Firms to Health Care Providers Regarding Scientific Information on Un… | en | MA | Final guidance, issued 01/06/2025; docket FDA-2008-D-0053 | 32 | fda.gov 公共领域政策 | eligible |  |
| cand-0190 | Good Pharmacovigilance Practices and Pharmacoepidemiologic Assessment: Guidance for Indus… | en | PV | Final guidance, issued 03/24/2005; docket FDA-2004-D-0041 | 23 | fda.gov 公共领域政策 | eligible |  |
| cand-0191 | Premarketing Risk Assessment: Guidance for Industry | en | PV | Final guidance, issued 03/29/2005; docket FDA-2004-D-0121 | 28 | fda.gov 公共领域政策 | eligible |  |
| cand-0192 | Development and Use of Risk Minimization Action Plans: Guidance for Industry | en | PV | Final guidance, issued 03/29/2005; docket FDA-2004-D-0441 | 27 | fda.gov 公共领域政策 | eligible |  |
| cand-0193 | Providing Postmarket Periodic Safety Reports in the ICH E2C(R2) Format (Periodic Benefit-… | en | PV | Final guidance, issued 11/29/2016; docket FDA-2013-D-0349 | 10 | fda.gov 公共领域政策 | eligible |  |
| cand-0194 | Postmarketing Safety Reporting for Human Drug and Biological Products Including Vaccines:… | en | PV | Draft guidance, issued 03/12/2001; docket FDA-2001-D-0506 | 50 | fda.gov 公共领域政策 | eligible |  |
| cand-0195 | Postmarketing Adverse Experience Reporting for Human Drug and Licensed Biological Product… | en | PV | Final guidance, issued 08/27/1997; docket FDA-1997-D-0445 | 7 | fda.gov 公共领域政策 | eligible |  |
| cand-0196 | Format and Content of a REMS Document Guidance for Industry | en | PV | Final guidance, issued 01/04/2023; docket FDA-2009-D-0461 | 13 | fda.gov 公共领域政策 | eligible |  |
| cand-0197 | Risk Evaluation and Mitigation Strategies: Modifications and Revisions Guidance for Indus… | en | PV | Final guidance, issued 07/09/2019; docket FDA-2014-D-1747 | 26 | fda.gov 公共领域政策 | eligible |  |
| cand-0198 | FDA’s Application of Statutory Factors in Determining When a REMS Is Necessary | en | PV | Final guidance, issued 04/04/2019; docket FDA-2016-D-2730 | 13 | fda.gov 公共领域政策 | eligible |  |
| cand-0199 | REMS Logic Model: A Framework to Link Program Design With Assessment | en | PV | Draft guidance, issued 05/07/2024; docket FDA-2024-D-1032 | 29 | fda.gov 公共领域政策 | eligible |  |
| cand-0200 | Survey Methodologies to Assess REMS Goals That Relate to Knowledge | en | PV | Draft guidance, issued 02/01/2019; docket FDA-2018-D-4629 | 25 | fda.gov 公共领域政策 | eligible |  |
| cand-0201 | Development of a Shared System REMS Guidance for Industry | en | PV | Draft guidance, issued 06/01/2018; docket FDA-2018-D-1041 | 11 | fda.gov 公共领域政策 | eligible |  |
| cand-0202 | Medication Guides — Distribution Requirements and Inclusion in Risk Evaluation and Mitiga… | en | PV | Final guidance, issued 11/18/2011 | 12 | fda.gov 公共领域政策 | eligible |  |

## 批 3（cand-0203 – cand-0252，50 条）

| 候选 | 标题 | 语言 | 部门 | 版本/日期 | 页 | 许可依据 | 预判 | 备注 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| cand-0203 | Medication Guides — Adding a Toll-Free Number for Reporting Adverse Events | en | PV | Final guidance, issued 06/08/2009; docket FDA-2009-D-0217 | 7 | fda.gov 公共领域政策 | eligible |  |
| cand-0204 | Safety Labeling Changes -- Implementation of Section 505(o)(4) of the Federal Food, Drug,… | en | PV | Final guidance, issued 07/30/2013; docket FDA-2011-D-0164 | 21 | fda.gov 公共领域政策 | eligible |  |
| cand-0205 | Postmarketing Studies and Clinical Trials—Implementation of Section 505(o)(3) of the Fede… | en | PV | Final guidance, issued 04/12/2011; docket FDA-2009-D-0283 | 21 | fda.gov 公共领域政策 | eligible |  |
| cand-0206 | Determining the Extent of Safety Data Collection Needed in Late Stage Premarket and Posta… | en | PV | Final guidance, issued 02/19/2016; docket FDA-2012-D-0096 | 11 | fda.gov 公共领域政策 | eligible |  |
| cand-0207 | Safety Considerations for Product Design to Minimize Medication Errors Guidance for Indus… | en | PV | Final guidance, issued 04/12/2016; docket FDA-2012-D-1005 | 22 | fda.gov 公共领域政策 | eligible |  |
| cand-0208 | Safety Considerations for Container Labels and Carton Labeling Design to Minimize Medicat… | en | PV | Final guidance, issued 05/18/2022; docket FDA-2013-D-0401 | 41 | fda.gov 公共领域政策 | eligible |  |
| cand-0209 | Best Practices in Developing Proprietary Names for Human Prescription Drug Products; Guid… | en | PV | Final guidance, issued 12/08/2020; docket FDA-2014-D-0622 | 42 | fda.gov 公共领域政策 | eligible |  |
| cand-0210 | Contents of a Complete Submission for the Evaluation of Proprietary Names | en | PV | Final guidance, issued 04/11/2016; docket FDA-2008-D-0592 | 22 | fda.gov 公共领域政策 | eligible |  |
| cand-0211 | Drug-Induced Liver Injury: Premarketing Clinical Evaluation | en | PV | Final guidance, issued 07/29/2009; docket FDA-2008-D-0128 | 28 | fda.gov 公共领域政策 | eligible |  |
| cand-0212 | Guidance for Industry: Suicidal Ideation and Behavior: Prospective Assessment of Occurren… | en | PV | Draft guidance, issued 08/13/2012 | 16 | fda.gov 公共领域政策 | eligible |  |
| cand-0213 | Assessment of Abuse Potential of Drugs | en | PV | Final guidance, issued 01/18/2017; docket FDA-2010-D-0026 | 37 | fda.gov 公共领域政策 | eligible |  |
| cand-0214 | Meta-Analyses of Randomized Controlled Clinical Trials to Evaluate the Safety of Human Dr… | en | PV | Draft guidance, issued 11/07/2018; docket FDA-2018-D-3710 | 29 | fda.gov 公共领域政策 | eligible |  |
| cand-0215 | Specifications for Preparing and Submitting Electronic ICSRs and ICSR Attachments | en | PV | Final guidance, issued 02/14/2020; docket None found | 48 | fda.gov 公共领域政策 | eligible |  |
| cand-0216 | Postmarketing Adverse Event Reporting for Medical Products and Dietary Supplements During… | en | PV | Final guidance, issued 05/11/2020; docket FDA-2008-D-0610 | 14 | fda.gov 公共领域政策 | eligible |  |
| cand-0217 | Postmarketing Adverse Event Reporting for Nonprescription Human Drug Products Marketed Wi… | en | PV | Final guidance, issued 07/17/2009; docket FDA-2007-D-0434 | 16 | fda.gov 公共领域政策 | eligible |  |
| cand-0218 | Providing Submissions in Electronic Format — Postmarketing Safety Reports | en | PV | Final guidance, issued 04/27/2022; docket FDA-2001-D-0067 | 16 | fda.gov 公共领域政策 | eligible |  |
| cand-0219 | Annual Status Report Information and Other Submissions for Postmarketing Requirements and… | en | PV | Final guidance, issued 09/15/2023; docket FDA-2018-N-3771 | 13 | fda.gov 公共领域政策 | eligible |  |
| cand-0220 | Reports on the Status of Postmarketing Study Commitments — Implementation of Section 130 … | en | PV | Final guidance, issued 02/16/2006; docket FDA-1999-N-0098 | 25 | fda.gov 公共领域政策 | eligible |  |
| cand-0221 | Conducting Clinical Trials With Decentralized Elements | en | CO | Final guidance, issued 09/18/2024; docket FDA-2022-D-2870 | 21 | fda.gov 公共领域政策 | eligible |  |
| cand-0222 | Electronic Systems, Electronic Records, and Electronic Signatures in Clinical Investigati… | en | CO | Final guidance, issued 10/01/2024; docket FDA-2017-D-1105 | 28 | fda.gov 公共领域政策 | eligible |  |
| cand-0223 | Considerations for the Design and Conduct of Externally Controlled Trials for Drug and Bi… | en | CO | Draft guidance, issued 02/01/2023; docket FDA-2022-D-2983 | 20 | fda.gov 公共领域政策 | eligible |  |
| cand-0224 | Clinical Investigator Administrative Actions - Disqualification: Guidance for Institution… | en | CO | Final guidance, issued 12/01/2022; docket FDA-2010-D-0265 | 9 | fda.gov 公共领域政策 | eligible |  |
| cand-0225 | Ethical Considerations for Clinical Investigations of Medical Products Involving Children… | en | CO | Draft guidance, issued 09/26/2022; docket FDA-2022-D-0738 | 17 | fda.gov 公共领域政策 | eligible |  |
| cand-0226 | Digital Health Technologies for Remote Data Acquisition in Clinical Investigations | en | CO | Final guidance, issued 12/22/2023; docket FDA-2021-D-1128 | 35 | fda.gov 公共领域政策 | eligible |  |
| cand-0227 | Information Sheet Guidance for Sponsors, Clinical Investigators, and IRBs Frequently Aske… | en | CO | Draft guidance, issued 05/19/2021; docket FDA-2008-D-0406 | 12 | fda.gov 公共领域政策 | eligible |  |
| cand-0228 | Adaptive Design Clinical Trials for Drugs and Biologics Guidance for Industry | en | CO | Final guidance, issued 12/02/2019; docket FDA-2018-D-3124 | 37 | fda.gov 公共领域政策 | eligible |  |
| cand-0229 | Enrichment Strategies for Clinical Trials to Support Approval of Human Drugs and Biologic… | en | CO | Final guidance, issued 03/15/2019; docket FDA-2012-D-1145 | 45 | fda.gov 公共领域政策 | eligible |  |
| cand-0230 | Demonstrating Substantial Evidence of Effectiveness for Human Drug and Biological Product… | en | CO | Draft guidance, issued 06/24/2026; docket FDA-2019-D-4964 | 20 | fda.gov 公共领域政策 | eligible |  |
| cand-0231 | Multiple Endpoints in Clinical Trials: Guidance for Industry | en | CO | Final guidance, issued 10/21/2022; docket FDA-2016-D-4460 | 29 | fda.gov 公共领域政策 | eligible |  |
| cand-0232 | Non-Inferiority Clinical Trials | en | CO | Final guidance, issued 11/08/2016; docket FDA-2010-D-0075 | 56 | fda.gov 公共领域政策 | eligible |  |
| cand-0233 | Master Protocols: Efficient Clinical Trial Design Strategies to Expedite Development of O… | en | CO | Final guidance, issued 03/01/2022; docket FDA-2018-D-3292 | 28 | fda.gov 公共领域政策 | eligible |  |
| cand-0234 | Establishment and Operation of Clinical Trial Data Monitoring Committees: Guidance for Cl… | en | CO | Final guidance, issued 03/28/2006; docket FDA-2001-D-0219 | 38 | fda.gov 公共领域政策 | eligible |  |
| cand-0235 | Waiver of IRB Requirements for Drug and Biological Product Studies: Guidance For Sponsors… | en | CO | Final guidance, issued 10/03/2017 | 6 | fda.gov 公共领域政策 | eligible |  |
| cand-0236 | Use of Electronic Informed Consent in Clinical Investigations – Questions and Answers: Gu… | en | CO | Final guidance, issued 12/15/2016; docket FDA-2015-D-0390 | 16 | fda.gov 公共领域政策 | eligible |  |
| cand-0237 | Collection of Race and Ethnicity Data in Clinical Trials: Guidance for Industry and Food … | en | CO | Final guidance, issued 10/26/2016; docket FDA-2016-D-3561 | 20 | fda.gov 公共领域政策 | eligible |  |
| cand-0238 | Charging for Investigational Drugs Under an IND: Questions and Answers | en | CO | Final guidance, issued 02/14/2024; docket FDA-2013-D-0447 | 14 | fda.gov 公共领域政策 | eligible |  |
| cand-0239 | Expanded Access to Investigational Drugs for Treatment Use: Questions and Answers | en | CO | Final guidance, issued 04/15/2026; docket FDA-2013-D-0446 | 44 | fda.gov 公共领域政策 | eligible |  |
| cand-0240 | Electronic Source Data in Clinical Investigations: Guidance for Industry | en | CO | Final guidance, issued 09/18/2013; docket FDA-2010-D-0643 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0241 | Investigational New Drug Applications (INDs) - Determining Whether Human Research Studies… | en | CO | Final guidance, issued 09/10/2013; docket FDA-2010-D-0503 | 23 | fda.gov 公共领域政策 | eligible |  |
| cand-0242 | IRB Responsibilities for Reviewing the Qualifications of Investigators, Adequacy of Resea… | en | CO | Final guidance, issued 08/27/2013; docket FDA-2012-D-0847 | 11 | fda.gov 公共领域政策 | eligible |  |
| cand-0243 | Exception from Informed Consent Requirements for Emergency Research: Guidance for Institu… | en | CO | Final guidance, issued 04/01/2013; docket FDA-2006-D-0464 | 64 | fda.gov 公共领域政策 | eligible |  |
| cand-0244 | Financial Disclosure by Clinical Investigators: Guidance for Clinical Investigators, Indu… | en | CO | Final guidance, issued 02/01/2013; docket FDA-1999-D-0742 | 35 | fda.gov 公共领域政策 | eligible |  |
| cand-0245 | FDA Acceptance of Foreign Clinical Studies Not Conducted Under an IND: Frequently Asked Q… | en | CO | Final guidance, issued 03/01/2012 | 19 | fda.gov 公共领域政策 | eligible |  |
| cand-0246 | IRB Continuing Review After Clinical Investigation Approval: Guidance for IRBs, Clinical … | en | CO | Final guidance, issued 02/27/2012; docket FDA-2009-D-0605 | 28 | fda.gov 公共领域政策 | eligible |  |
| cand-0247 | Questions and Answers on Informed Consent Elements, 21 CFR § 50.25(c): Guidance for Spons… | en | CO | Final guidance, issued 02/01/2012 | 10 | fda.gov 公共领域政策 | eligible |  |
| cand-0248 | Data Retention When Subjects Withdraw from FDA-Regulated Clinical Trials: Guidance for Sp… | en | CO | Final guidance, issued 10/01/2008; docket FDA-2008-D-0576 | 8 | fda.gov 公共领域政策 | eligible |  |
| cand-0249 | Part 11, Electronic Records; Electronic Signatures - Scope and Application: Guidance for … | en | CO | Final guidance, issued 09/05/2003; docket FDA-2003-D-0143 | 12 | fda.gov 公共领域政策 | eligible |  |
| cand-0250 | Processes and Practices Applicable to Bioresearch Monitoring Inspections: Guidance for In… | en | CO | Final guidance, issued 12/19/2025; docket FDA-2023-D-5021 | 16 | fda.gov 公共领域政策 | eligible |  |
| cand-0251 | Considerations for the Use of Real-World Data and Real-World Evidence To Support Regulato… | en | CO | Final guidance, issued 08/30/2023; docket FDA-2021-D-1214 | 12 | fda.gov 公共领域政策 | eligible |  |
| cand-0252 | 藥品優良安全監視規範（Guidance for Good Pharmacovigilance Practice） | zh-Hant | PV | 2014 年 12 月版（文内以 PDF 首页为准） | 26 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |

## 批 4（cand-0253 – cand-0302，50 条）

| 候选 | 标题 | 语言 | 部门 | 版本/日期 | 页 | 许可依据 | 预判 | 备注 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| cand-0253 | 藥品安全監視管理辦法 | zh-Hant | PV | 現行條文（以 PDF 首页发布日期为准） | 9 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0254 | 新藥採用藥品定期安全性報告格式及檢送時程說明 | zh-Hant | PV | 以 PDF 首页公告文号 / 日期为准；PDF 首页日期 2005-12-02 | 8 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0255 | 藥品風險評估及管控計畫書應載明項目 | zh-Hant | PV | 以 PDF 内容为准（2023 年上網） | 1 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0256 | 不良反應通報收（退）件作業原則 | zh-Hant | PV | 以 PDF 内容为准；PDF 首页日期 1924-05-20 | 2 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0257 | 上市後疫苗不良事件通報表填寫指引 | zh-Hant | PV | 以 PDF 内容为准；PDF 首页日期 1936-03 | 22 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0258 | 藥品優良臨床試驗作業準則（民國 109 年 8 月 28 日修正） | zh-Hant | CO | 2020-08-28 修正；PDF 首页日期 2020-08-28 | 19 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0259 | 藥品臨床試驗申請須知（中華民國 114 年 12 月） | zh-Hant | CO | 2025 年 12 月版；PDF 首页日期 2025-12 | 262 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0260 | 銜接性試驗基準（接受國外臨床資料之族群因素考量） | zh-Hant | CO | 以 PDF 首页版本为准 | 21 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0261 | 人類細胞治療產品臨床試驗申請作業及審查基準（中華民國 103 年 9 月 17 日） | zh-Hant | CO | 2014-09-17 | 67 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0262 | 藥品仿單全面電子結構化及無紙化分階段實施時程及方法（衛授食字第 1141418097 號公告附件） | zh-Hant | MA | 2025-07-31 公告；PDF 首页日期 2022-05-09 | 15 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0263 | 西藥非處方藥仿單外盒格式及規範 Q&A | zh-Hant | MA | 以 PDF 内容为准；PDF 首页日期 2016-03-08 | 5 | TFDA 網站資料開放宣告 + 著作權聲明 | eligible |  |
| cand-0264 | 易吉妥錠10毫克（Ezzicad (Ezetimibe) 10mg Tablets，ezetimibe）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-02-13；許可證 衛部藥輸字第027311號… | 3 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0265 | 愛妥糖錠15公絲（Actos Tablets 15mg，pioglitazone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2025-05-26；許可證 衛部藥製字第061860號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0266 | "國嘉"克糖寧錠80毫克（葛立克拉）（GLICALIN TABLETS 80MG (GLICLAZIDE) "KOJAR"，gliclazide）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-12-24；許可證 衛署藥製字第034736號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0267 | 優理醣錠2毫克（Repade Tablets 2mg (Repaglinide)，repaglinide）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-11-23；許可證 衛部藥製字第058068號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0268 | 泰穩壓錠40毫克（Tesaa Tablets 40mg，telmisartan）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-11-12；許可證 衛署藥製字第056745號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0269 | 壓落敏錠 25 公絲（CARVEDIL TABLETS 25MG，carvedilol）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-10-14；許可證 衛署藥製字第047239號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0270 | "國嘉"阿利平膜衣錠５０毫克（阿廷諾）（ANLIPIN F.C. TABLETS 50MG (ATENOLOL) "KOJAR"，atenolol）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-10-30；許可證 衛署藥製字第039816號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0271 | 博能錠（健心寧）（PRANOLOL TABLETS (PROPRANOLOL) "N.C.P."，propranolol）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2017-05-16；許可證 衛署藥製字第022259號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0272 | 使能通錠50毫克（Slatone Tablets 50mg，spironolactone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2020-09-02；許可證 衛部藥製字第060536號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0273 | ”羅得”優尿壓膠囊２．５公絲（UTRILIX CAPSULE 2.5MG "ROOT"，indapamide）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-04-15；許可證 衛署藥製字第043728號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0274 | 富必欣持續性藥效錠4毫克（Danxosin CORS Tablets 4mg，doxazosin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2023-03-02；許可證 衛部藥製字第061419號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0275 | 欣服寧 錠 1 毫克（Synfarin Tablets 1 mg，warfarin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-02-22；許可證 衛署藥製字第050068號… | 4 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0276 | 心韻錠（Tempo Tablets，amiodarone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-04-13；許可證 衛部藥製字第058597號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0277 | 歐舒心注射劑 0.01%（Easy-Isosorbide Injection 0.01%，isosorbide）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2012-03-05；許可證 衛署藥製字第056734號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0278 | 恩舒注射劑0.4毫克/毫升（N.T.G. Premixed Injection 0.4mg/mL，nitroglycerin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-06-12；許可證 衛部藥製字第058314號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0279 | 潰滿定膜衣錠２０公絲（啡莫替定）（QUIMADINE F.C. TABLETS 20MG (FAMOTIDINE)，famotidine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-10-06；許可證 衛署藥製字第039794號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0280 | "豐田"莫痙錠10毫克(多普利杜)（Motin Tablets 10mg "Honten"(Domperidone)，domperidone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-04-29；許可證 衛署藥製字第039969號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0281 | "永勝" 永胃健糖衣錠１０毫克（美托拉麥）（DRINGEN S.C. TABLETS 10MG (METOCLOPRAMIDE) "EVEREST"，metoclopramide… | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-01-06；許可證 衛署藥製字第039855號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0282 | “信東”摩暢膜衣錠 5 毫克（Mosa F.C. Tablets 5mg，mosapride）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-10-28；許可證 衛署藥製字第055990號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0283 | "太田"鎮拉定膠囊（樂必寧）（GENLATIN CAPSULES "TAITEN" (LOPERAMIDE)，loperamide）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-12-28；許可證 衛署藥製字第021703號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0284 | 美腸順 腸溶錠 400毫克（Mesaclon Enteric Film Coated  Tablets 400 mg，mesalazine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-09-11；許可證 衛署藥製字第048800號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0285 | "井田" 利肝膽膠囊300毫克（Legan Capsules 300mg "Chinteng"，ursodeoxycholic）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2014-10-14；許可證 衛署藥製字第048555號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0286 | 樂寶寧 膜衣錠50毫克（Lustraline Film Coated Tablets 50mg，sertraline）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2022-05-20；許可證 衛署藥製字第048541號… | 3 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0287 | ”生達”伏鬱微粒膠囊１０公絲（FLUX MICROENCAPSULATED CAP.10MG "STANDARD"，fluoxetine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 无；許可證 衛署藥製字第043705號 现行（有效日期 … | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0288 | 康緒平錠37.5毫克（Calmdown Tablets 37.5mg，venlafaxine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2022-05-25；許可證 衛署藥製字第048054號… | 20 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0289 | 憂必舒膠囊30毫克（Ulitine Capsules 30mg，duloxetine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2022-07-18；許可證 衛部藥製字第059825號… | 26 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0290 | “新瑞”邁慮煩 膜衣錠 15 毫克（Minivane F.C. Tablets 15mg“synray”，mirtazapine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-11-07；許可證 衛署藥製字第050016號… | 7 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0291 | "應元"百適存持續性藥效錠300毫克（Bestrim XL 300mg Tablets "Y.Y."，bupropion）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2017-11-16；許可證 衛部藥製字第059790號… | 4 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0292 | "杏輝"杏緩妥錠５０公絲（鹽酸查諾頓）（CIRZODONE TABLET 50MG "SINPHAR"(TRAZODONE                   HYDROCHLO… | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-09-22；許可證 衛署藥製字第041499號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0293 | 理思必妥 膜衣錠１毫克（Risperdal Film Coated Tablet 1mg，risperidone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2021-01-18；許可證 衛署藥輸字第022767號… | 26 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | needs_review | 文本层命中版权/限制标记：©「樓及 11 樓 電 話：0800-211-688 版 本：CCDS 07Apr2020_v2101 © Johnson 」 |
| cand-0294 | 羅亞達口溶錠10毫克（Arizole Orally Disintegrating Tablets 10mg，aripiprazole）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-11-22；許可證 衛部藥製字第058180號… | 4 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0295 | 鋰康膠囊300毫克（Lithcan Capsules 300 mg，lithium）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-03-29；許可證 衛署藥製字第046154號… | 3 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0296 | "威勝" 樂眠錠1毫克（Larpam Tablets 1 mg “W.S.”，lorazepam）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2022-02-21；許可證 衛署藥製字第039567號… | 3 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0297 | "新喜" 心氣寧錠（SINDILIUM TABLETS "N.C.P."，diazepam）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-08-09；許可證 內衛藥製字第006186號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0298 | 妥泰膜衣錠２００毫克（TOPAMAX FILM-COATED TABLETS 200MG，topiramate）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-07-02；許可證 衛署藥輸字第022510號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | needs_review | 文本层命中版权/限制标记：©「e100e200 ૩д̬၇ ኒඎf TOPAMAX̮ᝈνɨj 200 mg ΙϞ¨TopΙϞ¨200©f ቇᏐस Ի」 |
| cand-0299 | 普疼立寧膠囊75毫克（Pregabalin Capsules 75mg "C.C.P.C."，pregabalin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2019-05-09；許可證 衛部藥製字第060273號… | 7 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0300 | “榮民”癲可停膠囊１００毫克（EPILEPTIN CAPSULES 100MG，phenytoin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-02-09；許可證 衛署藥製字第030963號… | 3 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0301 | 痛搏適膠囊400毫克（Seconbrex Capsule 400mg，celecoxib）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-02-21；許可證 衛部藥輸字第027353號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0302 | 馬蓋先膜衣錠４００公絲（黃布洛芬）（MACSAFE F.C.TABLETS 400MG (IBUPROFEN)，ibuprofen）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-02-09；許可證 衛署藥製字第040695號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |

## 批 5（cand-0303 – cand-0332，30 条）

| 候选 | 标题 | 语言 | 部门 | 版本/日期 | 页 | 许可依据 | 预判 | 备注 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| cand-0303 | "應元"拿痛仙錠250毫克(那普洛仙)（Natoxen Tablets 250mg"Y.Y."(Naproxen)，naproxen）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-07-16；許可證 衛署藥製字第038997號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0304 | 益妥瑞膜衣錠120毫克（Terexib Film-coated Tablets 120mg，etoricoxib）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2019-04-08；許可證 衛部藥輸字第027583號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0305 | 蒙地卡膜衣錠 10 毫克（Monteka F.C. Tablets 10 mg，montelukast）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2022-01-05；許可證 衛署藥製字第049242號… | 4 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0306 | "國嘉"息舒寧液5.34毫克/毫升（Theolin oral Solution 5.34mg/mL "Kojar"，theophylline）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2019-07-22；許可證 衛部藥製字第060320號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0307 | "大豐"抒敏膜衣錠60毫克（"T.F." Su-min F.C. Tablets 60mg，fexofenadine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-11-10；許可證 衛署藥製字第057280號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0308 | "強生"暢適得膜衣錠5毫克（Fencare FCT 5mg "Johnson"，solifenacin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2021-04-19；許可證 衛部藥製字第060825號… | 8 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0309 | 虎讚膜衣錠10毫克（Zan Film-Coated Tablets 10mg，tadalafil）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2021-09-22；許可證 衛部藥製字第060951號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0310 | 士力挺膜衣錠50毫克（Sliting F.C. Tablets 50mg，sildenafil）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-10-19；許可證 衛部藥製字第059287號… | 11 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0311 | "汎生"僕樂彼錠５０毫克（POLUPI TABLET 50MG "PANBIOTIC"，propylthiouracil）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-11-23；許可證 衛署藥製字第043335號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0312 | 使汝健硬膠囊（Shi ru jian capsules，prednisolone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-02-26；許可證 衛署藥製字第047699號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0313 | "國嘉" 得佳錠0.5毫克（迪皮質醇）（DECA TABLETS 0.5MG (DEXAMETHASONE) "KOJAR"，dexamethasone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-01-22；許可證 衛署藥製字第034018號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0314 | "杏輝"杏節挺錠（PlusDmax Tablets "Sinphar"，alendronate）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-03-16；許可證 衛署藥製字第057366號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0315 | "安星" 克風迅錠0.5毫克（Cofoncin Tablets 0.5mg "Astar"，colchicine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-07-20；許可證 衛署藥製字第047814號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0316 | "信東" 撒樂腸溶錠５００公絲（SALAZINE ENTERIC COATED TABLETS 500MG (SULFASALAZINE) "S.T."，sulfasalazin… | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-10-01；許可證 衛署藥製字第043929號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | needs_review | 文本层命中版权/限制标记：©「٫jڦ؇͛Ҧٰ΅Ϟࠢʮ̡ ෤ਜʧྪ༩ 22 ໮ Ⴁ ி ᅀ j ࿲͏Ⴁᖹٰ΅Ϟࠢʮ̡ ݬ447 ໮ © ᅥᆀ ໑๓፵ 5」 |
| cand-0317 | 憶如新膜衣錠10毫克（Memsyn F.C. Tablets 10mg，memantine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2017-02-20；許可證 衛部藥製字第059394號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0318 | "應元"耳循膜衣錠8毫克（ECYCLE F.C.TABLETS 8MG "Y.Y."，betahistine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-07-16；許可證 衛署藥製字第044715號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0319 | 優樂欣注射劑（希福辛）（UROXIME INJECTION (CEFUROXIME)，cefuroxime）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-12-15；許可證 衛署藥製字第031094號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0320 | "生達"舒維速保膠囊２５０毫克（賜福力欣）（SERVISPOR CAPSULES 250MG "STANDARD"(CEPHALEXIN)，cephalexin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-11-25；許可證 衛署藥製字第040102號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0321 | 默菌殺點眼液（Micromox Eye Drops (Moxifloxacin Ophthalmic Solution USP 0.5% w/v)，moxifloxacin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2022-10-12；許可證 衛部藥輸字第028362號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0322 | 獨拉膠囊（去氧羥四環素）（BISTOR CAPSULE (DOXYCYCLINE) "SHITEH"，doxycycline）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-02-12；許可證 衛署藥製字第031219號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0323 | 黴祐膠囊５０公絲（氟可那挫）（AZOL FLUCON CAPSULES 50MG(FLUCNAZOLE)，fluconazole）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-12-01；許可證 衛署藥製字第041335號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0324 | 敵疱治錠２００公絲（艾賽可威）（ACYLETE TABLETS 200 MG (ACYCLOVIR)，acyclovir）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-09-23；許可證 衛署藥製字第040090號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0325 | 硝弗侖陶因錠１００公絲（NITROFURANTOIN TABLETS 100MG "R.S.P.P"，nitrofurantoin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-02-09；許可證 衛署藥製字第003893號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0326 | 順治炎錠（SINZUIN TABLETS "YUNG CHI"，sulfamethoxazole）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-12-06；許可證 衛署藥製字第013366號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0327 | 瑞保清膜衣錠0.5毫克（Hepato-ease F.C. Tablets 0.5mg，entecavir）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2020-07-06；許可證 衛部藥製字第060515號… | 17 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0328 | 惠肝怡錠300毫克（Hucanon Tablets 300mg，tenofovir）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-12-18；許可證 衛部藥製字第060206號… | 36 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0329 | 輔適納膜衣錠2.5毫克（Letramase F.C. Tablets 2.5mg，letrozole）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-11-19；許可證 衛部藥製字第058819號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0330 | 消汝妥1毫克（Arbreast F.C. Tab. 1mg (Anastrozole)，anastrozole）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2021-08-12；許可證 衛署藥輸字第025535號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0331 | 癌可泰膜衣錠50毫克（Bicalutamide-Acepharm film coated tablets 50mg，bicalutamide）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-04-02；許可證 衛部藥輸字第026270號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0332 | 立悠克膠囊100毫克（Leukure Micro-T Capsules 100mg，imatinib）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-09-29；許可證 衛部藥製字第059272號… | 11 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |

## 未列入（机械核对未通过或不需要）

| 分组 | 原因 | 条数 |
| --- | --- | ---: |
| TFDA 仿單 | 同成分已有候选 / 超出配额 | 20 |
| TFDA 仿單 | 已在清单中 | 2 |
| TFDA 仿單 | 无文本层（扫描件） | 70 |
| TFDA 指引 / 法規 / 公告 | 无文本层（扫描件） | 3 |

无文本层的文件（不做 OCR，按 ADR-0003 决策 2026-09-12 第 4 项；同成分已改试其他仿單）：藥品定期安全性報告－總結報告格式（97 年 5 月 26 日衛署藥字第 0970318606 號公告）（PV）；藥品定期安全性報告之通報格式（94 年 12 月 2 日衛署藥字第 0940336107 號公告）（PV）；西藥非處方藥仿單外盒格式及規範（公告）（MA）；“聯邦”欣華膜衣錠 40 毫克（Simva F.C. Tablets 40mg“Union”，simvastatin）仿（MA）；助療醣膜衣錠100毫克（Taglu F.C. Tablets 100mg，acarbose）仿單（MA）；"衛達" 醣可抑 錠50毫克（Glucout Tablets 50 mg "Weidar"，acarbose）仿單（MA）；助療醣膜衣錠50毫克（Taglu F.C. Tablets 50mg，acarbose）仿單（MA）；博脈舒　錠８公絲（BLOPRESS TABLETS 8MG，candesartan）仿單（MA）；“永勝”費落持續性藥效錠 2.5 毫克（Felo E.R. Tablets 2.5mg“EVEREST”，felodip（MA）；“永勝”費落持續釋放錠 5 毫克（Felo E.R. F.C. Tablets 5mg“EVEREST”，felodip（MA）；"信東" 菲可平持續釋放膜衣錠５毫克（FELPIN EXTENDED RELEASE TABLETS 5MG 'S.T.（MA）；降壓卡諾錠25毫克（CARVO TABLETS 25MG，carvedilol）仿單（MA）；…等 73 份（全部见 dropped.json）

## 签字

决策人按批回复；每批的 `reviewer_decision` / `reviewer_note` 由实现方据回复写入下一版本文件（不覆盖本版）。

### 2026-09-28 复核后需决策人单独判断

本节为复核辅助，不是签字。新增 230 份本地 PDF 均存在且 SHA-256 与清单一致；逐份扫描文本层限制标记后，以下三条仍有明确许可疑点。其余 227 条尚需按批确认，但没有发现同类文本层阻断证据；TFDA 仿單的逐页图像层检查仍按 ADR-0003 在签字后、入库前执行。

| 项目 | 核对证据 | 建议及需回复的判断 |
| --- | --- | --- |
| cand-0114 | [ICH 官方 PDF](https://database.ich.org/sites/default/files/ICH_E2B%28R3%29_EWG_IWG_ICSR_Implementation_Guide_%28QA%20integration%29_Step3_2025_0718_Assembly_Approved_0.pdf) 第 14 页注明 ISO/HL7 27953-2 的版权属于 ISO 和 HL7，并标记 `ALL RIGHTS RESERVED`；ICH 许可排除第三方内容。该 PDF 文档历史又将 2025 年 7 月的 v5.03 列为 Step 4，与候选标题和版本栏的 Step 3 咨询版不一致。 | 建议 `rejected`，并修正版本元数据。请决定是否排除整份 PDF；如认为有可分离且获准的部分，请明确范围与授权依据。 |
| cand-0293 | [TFDA 官方 PDF](https://mcp.fda.gov.tw/insert/pdfcasefile/i_bb02e8be-0595-4658-9274-375dc48102ae?c=2) 第 26 页含 `© Johnson & Johnson Taiwan Ltd. 2021`。 | 建议保持 `needs_review`。请决定该文件内声明是否阻止依据资料集 9117/39 的 OGDL-1.0 入库，或提供足以覆盖的具体授权依据。 |
| cand-0298 | [TFDA 官方 PDF](https://mcp.fda.gov.tw/insert/pdfcasefile/i_bc44dd21-e25b-4df9-ab90-150b5edc0d64?c=2) 第 2 页含 `© Johnson & Johnson Taiwan Ltd. 2021`；正文文本抽取另有严重乱码。 | 建议保持 `needs_review`，并在许可之外单独判定抽取质量。请决定是否排除或另找同成分备选。 |

**cand-0316 已排除为单独许可疑点。** 本机 Quartz 逐页渲染目视：文本层在第 2 页厂商地址后误抽为 `©` 的字形，图像上实际为圈号 `②`；两页均未见版权或保密声明。候选 JSON 中仍是 `needs_review`，待决策人按批确认后才能更新；TFDA 仿單的其余准入步骤仍须完成。

**PV 份数缺口：** 预判可用语料中 PV 为 102 份，距 120 份目标少 18 份。建议先在现有白名单补官方 PV 文件；若仍不足，再由决策人决定是否纳入 MHRA/TGA 并更新 ADR-0003。请回复选择现有白名单优先，或授权扩充来源。

**决策人回复（2026-09-28）：**“按照建议的来即可”。签字与逐条 `reviewer_note` 已写入 [v1.3 JSON](DEC-011-candidates-v1.3.json)，结果见 [v1.3 签字表](DEC-011-candidates-v1.3.md)：新增 230 条中 227 条 `eligible`、2 条 `needs_review`、1 条 `rejected`；PV 先在现有白名单补足。v1.2 JSON 保留签字前状态，v1.2 签字表只追加本次决定索引。
