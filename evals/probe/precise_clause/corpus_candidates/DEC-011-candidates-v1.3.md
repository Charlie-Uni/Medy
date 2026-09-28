# DEC-011 候选清单 v1.3（v1.2 新增 230 条的许可签字结果）

编制：2026-09-28。承接 [v1.2 签字前清单](DEC-011-candidates-v1.2.md) 与 [v1.2 PDF 清单](../../../main_set/drafts/v1.2_pdf_list_2026-09-28.md)。决策人就复核建议回复“按照建议的来即可”；本版把决定写入 [v1.3.json](DEC-011-candidates-v1.3.json) 的 `reviewer_decision` / `reviewer_note`。v1.2 JSON 保留为签字前快照；v1.2 签字表只追加决定索引。

## 决策结果

| 决定 | 新增 230 条 | 处理 |
| --- | ---: | --- |
| `eligible` | 227 | 按各来源许可与逐条 `reviewer_note` 执行署名、第三方内容和入库前复验；TFDA 仿單继续逐页图像层核查。 |
| `needs_review` | 2 | cand-0293、cand-0298；Johnson & Johnson 文件内版权声明尚无足够覆盖依据，不得入库。 |
| `rejected` | 1 | cand-0114；ISO/HL7 第三方版权内容与 ICH 许可排除条款冲突，不入库。 |

cand-0316 的文本层 `©` 经本机 Quartz 对两页逐页目视核对，实为圈号 `②` 的字形映射误报，本版改为 `eligible`。许可与文本质量分别把关；其 pypdf 文本质量仍需入库前检查。cand-0114 的标题和版本栏依据官方 PDF 文档历史改为 v5.03、Step 4。

PV 缺口处理：先在现有 ADR-0003 白名单内补官方 PV 候选；仍不足时另行决定是否扩充 MHRA/TGA 来源并更新 ADR。此次决定不把新来源自动列入白名单。

## 各批签字明细

### 批 1（cand-0103–cand-0152；eligible 49、needs_review 0、rejected 1）

| 候选 | 标题 | 来源 | 部门 | 决定 |
| --- | --- | --- | --- | --- |
| cand-0103 | ICH E1: The Extent of Population Exposure to Assess Clinical Safety for Drugs Inten… | ICH | PV | `eligible` |
| cand-0104 | ICH E4: Dose-Response Information to Support Drug Registration | ICH | CO | `eligible` |
| cand-0105 | ICH E5(R1): Ethnic Factors in the Acceptability of Foreign Clinical Data | ICH | CO | `eligible` |
| cand-0106 | ICH E16: Biomarkers Related to Drug or Biotechnology Product Development: Context, … | ICH | CO | `eligible` |
| cand-0107 | ICH E11A: Pediatric Extrapolation | ICH | CO | `eligible` |
| cand-0108 | ICH E6(R3) Annex 2: Good Clinical Practice – Additional Considerations for Interven… | ICH | CO | `eligible` |
| cand-0109 | ICH M11: Clinical Electronic Structured Harmonised Protocol (CeSHarP) – Guideline | ICH | CO | `eligible` |
| cand-0110 | ICH M4E(R2): The Common Technical Document for the Registration of Pharmaceuticals … | ICH | CO | `eligible` |
| cand-0111 | ICH E3 Questions & Answers (R1): Structure and Content of Clinical Study Reports | ICH | CO | `eligible` |
| cand-0112 | ICH E14 Questions & Answers (R3): The Clinical Evaluation of QT/QTc Interval Prolon… | ICH | CO | `eligible` |
| cand-0113 | ICH E2B(R3) Implementation Guide Questions & Answers, version 2.4 | ICH | PV | `eligible` |
| cand-0114 | ICH E2B(R3) Implementation Guide for Electronic Transmission of Individual Case Saf… | ICH | PV | `rejected` |
| cand-0115 | ICH E2D(R1): Post-Approval Safety Data: Definitions and Standards for Management an… | ICH | PV | `eligible` |
| cand-0116 | ICH M14: General Principles on Plan, Design and Analysis of Pharmacoepidemiological… | ICH | PV | `eligible` |
| cand-0117 | Guideline on good pharmacovigilance practices (GVP) – Module VIII Addendum I – Requ… | EMA | PV | `eligible` |
| cand-0118 | Guideline on good pharmacovigilance practices (GVP) – Module XVI Addendum I – Risk … | EMA | PV | `eligible` |
| cand-0119 | Guideline on good pharmacovigilance practices (GVP) – Module XVI Addendum II – Meth… | EMA | PV | `eligible` |
| cand-0120 | Guideline on good pharmacovigilance practices (GVP) – Product- or Population-Specif… | EMA | PV | `eligible` |
| cand-0121 | Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Cover p… | EMA | PV | `eligible` |
| cand-0122 | Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Direct … | EMA | PV | `eligible` |
| cand-0123 | Guideline on good pharmacovigilance practices (GVP) – Annex II – Templates: Communi… | EMA | PV | `eligible` |
| cand-0124 | Guideline on good pharmacovigilance practices (GVP) – Annex V – Abbreviations (Rev 1) | EMA | PV | `eligible` |
| cand-0125 | Guideline on good pharmacovigilance practices (GVP) – Module VII – Periodic safety … | EMA | PV | `eligible` |
| cand-0126 | Good practice guide on recording, coding, reporting and assessment of medication er… | EMA | PV | `eligible` |
| cand-0127 | Good practice guide on risk minimisation and prevention of medication errors | EMA | PV | `eligible` |
| cand-0128 | Risk minimisation strategy for high-strength and fixed-combination insulin products… | EMA | PV | `eligible` |
| cand-0129 | Questions and answers on the periodic safety update report single assessment (PSUSA… | EMA | PV | `eligible` |
| cand-0130 | Pharmacovigilance Risk Assessment Committee (PRAC) – Rules of Procedure | EMA | PV | `eligible` |
| cand-0131 | Guideline on key aspects for the use of pharmacogenomics in the pharmacovigilance o… | EMA | PV | `eligible` |
| cand-0132 | Guidelines on good pharmacovigilance practices (GVP) – Introductory cover note (las… | EMA | PV | `eligible` |
| cand-0133 | Reporting requirements for marketing authorisation holders in the EU regarding susp… | EMA | PV | `eligible` |
| cand-0134 | Screening for adverse reactions in EudraVigilance | EMA | PV | `eligible` |
| cand-0135 | Questions and answers on signal management | EMA | PV | `eligible` |
| cand-0136 | Questions and answers on Implementing Regulation (EU) 2025/1466 amending Regulation… | EMA | PV | `eligible` |
| cand-0137 | Periodic safety update report (PSUR) repository – mandatory use: questions and answers | EMA | PV | `eligible` |
| cand-0138 | Introductory cover note to the list of European Union reference dates and frequency… | EMA | PV | `eligible` |
| cand-0139 | Guideline on registry-based studies | EMA | PV | `eligible` |
| cand-0140 | Guideline on the exposure to medicinal products during pregnancy: need for post-aut… | EMA | PV | `eligible` |
| cand-0141 | Guideline on the use of statistical signal detection methods in the EudraVigilance … | EMA | PV | `eligible` |
| cand-0142 | EU Individual Case Safety Report (ICSR) Implementation Guide | EMA | PV | `eligible` |
| cand-0143 | Guide on the interpretation of spontaneous case reports of suspected adverse reacti… | EMA | PV | `eligible` |
| cand-0144 | Reporting requirements of Individual Case Safety Reports (ICSRs) applicable to mark… | EMA | PV | `eligible` |
| cand-0145 | Reflection paper on use of real-world data in non-interventional studies to generat… | EMA | PV | `eligible` |
| cand-0146 | Guideline on computerised systems and electronic data in clinical trials | EMA | CO | `eligible` |
| cand-0147 | Guideline on the content, management and archiving of the clinical trial master fil… | EMA | CO | `eligible` |
| cand-0148 | Guideline on strategies to identify and mitigate risks for first-in-human and early… | EMA | CO | `eligible` |
| cand-0149 | Guideline on data monitoring committees | EMA | CO | `eligible` |
| cand-0150 | Questions and answers on Data Monitoring Committees issues | EMA | CO | `eligible` |
| cand-0151 | Guideline on missing data in confirmatory clinical trials | EMA | CO | `eligible` |
| cand-0152 | Guideline on adjustment for baseline covariates in clinical trials | EMA | CO | `eligible` |

### 批 2（cand-0153–cand-0202；eligible 50、needs_review 0、rejected 0）

| 候选 | 标题 | 来源 | 部门 | 决定 |
| --- | --- | --- | --- | --- |
| cand-0153 | Guideline on the investigation of subgroups in confirmatory clinical trials | EMA | CO | `eligible` |
| cand-0154 | Guideline on clinical trials in small populations | EMA | CO | `eligible` |
| cand-0155 | Guideline on the choice of the non-inferiority margin | EMA | CO | `eligible` |
| cand-0156 | Points to consider on multiplicity issues in clinical trials | EMA | CO | `eligible` |
| cand-0157 | Reflection paper on methodological issues in confirmatory clinical trials planned w… | EMA | CO | `eligible` |
| cand-0158 | Reflection paper on ethical and GCP aspects of clinical trials of medicinal product… | EMA | CO | `eligible` |
| cand-0159 | Scientific guidance on post-authorisation efficacy studies | EMA | CO | `eligible` |
| cand-0160 | Guideline on clinical development of fixed combination medicinal products (Rev 2) | EMA | CO | `eligible` |
| cand-0161 | Data Quality Framework for EU medicines regulation | EMA | CO | `eligible` |
| cand-0162 | Position paper on the non-acceptability of replacement of pivotal clinical trials i… | EMA | CO | `eligible` |
| cand-0163 | Quality Review of Documents (QRD) convention to be followed for the European Medici… | EMA | MA | `eligible` |
| cand-0164 | Guideline on risk assessment of medicinal products on human reproduction and lactat… | EMA | MA | `eligible` |
| cand-0165 | Labeling for Human Prescription Drug and Biological Products - Implementing the PLR… | FDA | MA | `eligible` |
| cand-0166 | Warnings and Precautions, Contraindications, and Boxed Warning Sections of Labeling… | FDA | MA | `eligible` |
| cand-0167 | Adverse Reactions Section of Labeling for Human Prescription Drug and Biological Pr… | FDA | MA | `eligible` |
| cand-0168 | Clinical Studies Section of Labeling for Human Prescription Drug and Biological Pro… | FDA | MA | `eligible` |
| cand-0169 | Clinical Pharmacology Labeling for Human Prescription Drug and Biological Products … | FDA | MA | `eligible` |
| cand-0170 | Patient Counseling Information Section of Labeling for Human Prescription Drug and … | FDA | MA | `eligible` |
| cand-0171 | Dosage and Administration Section of Labeling for Human Prescription Drug and Biolo… | FDA | MA | `eligible` |
| cand-0172 | Indications and Usage Section of Labeling for Human Prescription Drug and Biologica… | FDA | MA | `eligible` |
| cand-0173 | Drug Interaction Information in Human Prescription Drug and Biological Product Labe… | FDA | MA | `eligible` |
| cand-0174 | Pregnancy, Lactation, and Reproductive Potential: Labeling for Human Prescription D… | FDA | MA | `eligible` |
| cand-0175 | Pediatric Information Incorporated Into Human Prescription Drug and Biological Prod… | FDA | MA | `eligible` |
| cand-0176 | Geriatric Information in Human Prescription Drug and Biological Product Labeling Gu… | FDA | MA | `eligible` |
| cand-0177 | Drug Abuse and Dependence Section of Labeling for Human Prescription Drug and Biolo… | FDA | MA | `eligible` |
| cand-0178 | Instructions for Use — Patient Labeling for Human Prescription Drug and Biological … | FDA | MA | `eligible` |
| cand-0179 | Human Prescription Drug and Biological Products--Labeling for Dosing Based on Weigh… | FDA | MA | `eligible` |
| cand-0180 | QTc Information in Human Prescription Drug and Biological Product Labeling: Guidanc… | FDA | MA | `eligible` |
| cand-0181 | Labeling for Human Prescription Drug and Biological Products — Determining Establis… | FDA | MA | `eligible` |
| cand-0182 | Labeling for Biosimilar Products Guidance for Industry | FDA | MA | `eligible` |
| cand-0183 | Presenting Quantitative Efficacy and Risk Information in Direct-to-Consumer (DTC) P… | FDA | MA | `eligible` |
| cand-0184 | Direct-to-Consumer Prescription Drug Advertisements: Presentation of the Major Stat… | FDA | MA | `eligible` |
| cand-0185 | Product Name Placement, Size, and Prominence in Advertising and Promotional Labelin… | FDA | MA | `eligible` |
| cand-0186 | Presenting Risk Information in Prescription Drug and Medical Device Promotion | FDA | MA | `eligible` |
| cand-0187 | Responding to Unsolicited Requests for Off-Label Information About Prescription Dru… | FDA | MA | `eligible` |
| cand-0188 | Medical Product Communications That Are Consistent With the FDA-Required Labeling —… | FDA | MA | `eligible` |
| cand-0189 | Communications From Firms to Health Care Providers Regarding Scientific Information… | FDA | MA | `eligible` |
| cand-0190 | Good Pharmacovigilance Practices and Pharmacoepidemiologic Assessment: Guidance for… | FDA | PV | `eligible` |
| cand-0191 | Premarketing Risk Assessment: Guidance for Industry | FDA | PV | `eligible` |
| cand-0192 | Development and Use of Risk Minimization Action Plans: Guidance for Industry | FDA | PV | `eligible` |
| cand-0193 | Providing Postmarket Periodic Safety Reports in the ICH E2C(R2) Format (Periodic Be… | FDA | PV | `eligible` |
| cand-0194 | Postmarketing Safety Reporting for Human Drug and Biological Products Including Vac… | FDA | PV | `eligible` |
| cand-0195 | Postmarketing Adverse Experience Reporting for Human Drug and Licensed Biological P… | FDA | PV | `eligible` |
| cand-0196 | Format and Content of a REMS Document Guidance for Industry | FDA | PV | `eligible` |
| cand-0197 | Risk Evaluation and Mitigation Strategies: Modifications and Revisions Guidance for… | FDA | PV | `eligible` |
| cand-0198 | FDA’s Application of Statutory Factors in Determining When a REMS Is Necessary | FDA | PV | `eligible` |
| cand-0199 | REMS Logic Model: A Framework to Link Program Design With Assessment | FDA | PV | `eligible` |
| cand-0200 | Survey Methodologies to Assess REMS Goals That Relate to Knowledge | FDA | PV | `eligible` |
| cand-0201 | Development of a Shared System REMS Guidance for Industry | FDA | PV | `eligible` |
| cand-0202 | Medication Guides — Distribution Requirements and Inclusion in Risk Evaluation and … | FDA | PV | `eligible` |

### 批 3（cand-0203–cand-0252；eligible 50、needs_review 0、rejected 0）

| 候选 | 标题 | 来源 | 部门 | 决定 |
| --- | --- | --- | --- | --- |
| cand-0203 | Medication Guides — Adding a Toll-Free Number for Reporting Adverse Events | FDA | PV | `eligible` |
| cand-0204 | Safety Labeling Changes -- Implementation of Section 505(o)(4) of the Federal Food,… | FDA | PV | `eligible` |
| cand-0205 | Postmarketing Studies and Clinical Trials—Implementation of Section 505(o)(3) of th… | FDA | PV | `eligible` |
| cand-0206 | Determining the Extent of Safety Data Collection Needed in Late Stage Premarket and… | FDA | PV | `eligible` |
| cand-0207 | Safety Considerations for Product Design to Minimize Medication Errors Guidance for… | FDA | PV | `eligible` |
| cand-0208 | Safety Considerations for Container Labels and Carton Labeling Design to Minimize M… | FDA | PV | `eligible` |
| cand-0209 | Best Practices in Developing Proprietary Names for Human Prescription Drug Products… | FDA | PV | `eligible` |
| cand-0210 | Contents of a Complete Submission for the Evaluation of Proprietary Names | FDA | PV | `eligible` |
| cand-0211 | Drug-Induced Liver Injury: Premarketing Clinical Evaluation | FDA | PV | `eligible` |
| cand-0212 | Guidance for Industry: Suicidal Ideation and Behavior: Prospective Assessment of Oc… | FDA | PV | `eligible` |
| cand-0213 | Assessment of Abuse Potential of Drugs | FDA | PV | `eligible` |
| cand-0214 | Meta-Analyses of Randomized Controlled Clinical Trials to Evaluate the Safety of Hu… | FDA | PV | `eligible` |
| cand-0215 | Specifications for Preparing and Submitting Electronic ICSRs and ICSR Attachments | FDA | PV | `eligible` |
| cand-0216 | Postmarketing Adverse Event Reporting for Medical Products and Dietary Supplements … | FDA | PV | `eligible` |
| cand-0217 | Postmarketing Adverse Event Reporting for Nonprescription Human Drug Products Marke… | FDA | PV | `eligible` |
| cand-0218 | Providing Submissions in Electronic Format — Postmarketing Safety Reports | FDA | PV | `eligible` |
| cand-0219 | Annual Status Report Information and Other Submissions for Postmarketing Requiremen… | FDA | PV | `eligible` |
| cand-0220 | Reports on the Status of Postmarketing Study Commitments — Implementation of Sectio… | FDA | PV | `eligible` |
| cand-0221 | Conducting Clinical Trials With Decentralized Elements | FDA | CO | `eligible` |
| cand-0222 | Electronic Systems, Electronic Records, and Electronic Signatures in Clinical Inves… | FDA | CO | `eligible` |
| cand-0223 | Considerations for the Design and Conduct of Externally Controlled Trials for Drug … | FDA | CO | `eligible` |
| cand-0224 | Clinical Investigator Administrative Actions - Disqualification: Guidance for Insti… | FDA | CO | `eligible` |
| cand-0225 | Ethical Considerations for Clinical Investigations of Medical Products Involving Ch… | FDA | CO | `eligible` |
| cand-0226 | Digital Health Technologies for Remote Data Acquisition in Clinical Investigations | FDA | CO | `eligible` |
| cand-0227 | Information Sheet Guidance for Sponsors, Clinical Investigators, and IRBs Frequentl… | FDA | CO | `eligible` |
| cand-0228 | Adaptive Design Clinical Trials for Drugs and Biologics Guidance for Industry | FDA | CO | `eligible` |
| cand-0229 | Enrichment Strategies for Clinical Trials to Support Approval of Human Drugs and Bi… | FDA | CO | `eligible` |
| cand-0230 | Demonstrating Substantial Evidence of Effectiveness for Human Drug and Biological P… | FDA | CO | `eligible` |
| cand-0231 | Multiple Endpoints in Clinical Trials: Guidance for Industry | FDA | CO | `eligible` |
| cand-0232 | Non-Inferiority Clinical Trials | FDA | CO | `eligible` |
| cand-0233 | Master Protocols: Efficient Clinical Trial Design Strategies to Expedite Developmen… | FDA | CO | `eligible` |
| cand-0234 | Establishment and Operation of Clinical Trial Data Monitoring Committees: Guidance … | FDA | CO | `eligible` |
| cand-0235 | Waiver of IRB Requirements for Drug and Biological Product Studies: Guidance For Sp… | FDA | CO | `eligible` |
| cand-0236 | Use of Electronic Informed Consent in Clinical Investigations – Questions and Answe… | FDA | CO | `eligible` |
| cand-0237 | Collection of Race and Ethnicity Data in Clinical Trials: Guidance for Industry and… | FDA | CO | `eligible` |
| cand-0238 | Charging for Investigational Drugs Under an IND: Questions and Answers | FDA | CO | `eligible` |
| cand-0239 | Expanded Access to Investigational Drugs for Treatment Use: Questions and Answers | FDA | CO | `eligible` |
| cand-0240 | Electronic Source Data in Clinical Investigations: Guidance for Industry | FDA | CO | `eligible` |
| cand-0241 | Investigational New Drug Applications (INDs) - Determining Whether Human Research S… | FDA | CO | `eligible` |
| cand-0242 | IRB Responsibilities for Reviewing the Qualifications of Investigators, Adequacy of… | FDA | CO | `eligible` |
| cand-0243 | Exception from Informed Consent Requirements for Emergency Research: Guidance for I… | FDA | CO | `eligible` |
| cand-0244 | Financial Disclosure by Clinical Investigators: Guidance for Clinical Investigators… | FDA | CO | `eligible` |
| cand-0245 | FDA Acceptance of Foreign Clinical Studies Not Conducted Under an IND: Frequently A… | FDA | CO | `eligible` |
| cand-0246 | IRB Continuing Review After Clinical Investigation Approval: Guidance for IRBs, Cli… | FDA | CO | `eligible` |
| cand-0247 | Questions and Answers on Informed Consent Elements, 21 CFR § 50.25(c): Guidance for… | FDA | CO | `eligible` |
| cand-0248 | Data Retention When Subjects Withdraw from FDA-Regulated Clinical Trials: Guidance … | FDA | CO | `eligible` |
| cand-0249 | Part 11, Electronic Records; Electronic Signatures - Scope and Application: Guidanc… | FDA | CO | `eligible` |
| cand-0250 | Processes and Practices Applicable to Bioresearch Monitoring Inspections: Guidance … | FDA | CO | `eligible` |
| cand-0251 | Considerations for the Use of Real-World Data and Real-World Evidence To Support Re… | FDA | CO | `eligible` |
| cand-0252 | 藥品優良安全監視規範（Guidance for Good Pharmacovigilance Practice） | TFDA | PV | `eligible` |

### 批 4（cand-0253–cand-0302；eligible 48、needs_review 2、rejected 0）

| 候选 | 标题 | 来源 | 部门 | 决定 |
| --- | --- | --- | --- | --- |
| cand-0253 | 藥品安全監視管理辦法 | TFDA | PV | `eligible` |
| cand-0254 | 新藥採用藥品定期安全性報告格式及檢送時程說明 | TFDA | PV | `eligible` |
| cand-0255 | 藥品風險評估及管控計畫書應載明項目 | TFDA | PV | `eligible` |
| cand-0256 | 不良反應通報收（退）件作業原則 | TFDA | PV | `eligible` |
| cand-0257 | 上市後疫苗不良事件通報表填寫指引 | TFDA | PV | `eligible` |
| cand-0258 | 藥品優良臨床試驗作業準則（民國 109 年 8 月 28 日修正） | TFDA | CO | `eligible` |
| cand-0259 | 藥品臨床試驗申請須知（中華民國 114 年 12 月） | TFDA | CO | `eligible` |
| cand-0260 | 銜接性試驗基準（接受國外臨床資料之族群因素考量） | TFDA | CO | `eligible` |
| cand-0261 | 人類細胞治療產品臨床試驗申請作業及審查基準（中華民國 103 年 9 月 17 日） | TFDA | CO | `eligible` |
| cand-0262 | 藥品仿單全面電子結構化及無紙化分階段實施時程及方法（衛授食字第 1141418097 號公告附件） | TFDA | MA | `eligible` |
| cand-0263 | 西藥非處方藥仿單外盒格式及規範 Q&A | TFDA | MA | `eligible` |
| cand-0264 | 易吉妥錠10毫克（Ezzicad (Ezetimibe) 10mg Tablets，ezetimibe）仿單 | TFDA | MA | `eligible` |
| cand-0265 | 愛妥糖錠15公絲（Actos Tablets 15mg，pioglitazone）仿單 | TFDA | MA | `eligible` |
| cand-0266 | "國嘉"克糖寧錠80毫克（葛立克拉）（GLICALIN TABLETS 80MG (GLICLAZIDE) "KOJAR"，gliclazide）仿單 | TFDA | MA | `eligible` |
| cand-0267 | 優理醣錠2毫克（Repade Tablets 2mg (Repaglinide)，repaglinide）仿單 | TFDA | MA | `eligible` |
| cand-0268 | 泰穩壓錠40毫克（Tesaa Tablets 40mg，telmisartan）仿單 | TFDA | MA | `eligible` |
| cand-0269 | 壓落敏錠 25 公絲（CARVEDIL TABLETS 25MG，carvedilol）仿單 | TFDA | MA | `eligible` |
| cand-0270 | "國嘉"阿利平膜衣錠５０毫克（阿廷諾）（ANLIPIN F.C. TABLETS 50MG (ATENOLOL) "KOJAR"，atenolol）仿單 | TFDA | MA | `eligible` |
| cand-0271 | 博能錠（健心寧）（PRANOLOL TABLETS (PROPRANOLOL) "N.C.P."，propranolol）仿單 | TFDA | MA | `eligible` |
| cand-0272 | 使能通錠50毫克（Slatone Tablets 50mg，spironolactone）仿單 | TFDA | MA | `eligible` |
| cand-0273 | ”羅得”優尿壓膠囊２．５公絲（UTRILIX CAPSULE 2.5MG "ROOT"，indapamide）仿單 | TFDA | MA | `eligible` |
| cand-0274 | 富必欣持續性藥效錠4毫克（Danxosin CORS Tablets 4mg，doxazosin）仿單 | TFDA | MA | `eligible` |
| cand-0275 | 欣服寧 錠 1 毫克（Synfarin Tablets 1 mg，warfarin）仿單 | TFDA | MA | `eligible` |
| cand-0276 | 心韻錠（Tempo Tablets，amiodarone）仿單 | TFDA | MA | `eligible` |
| cand-0277 | 歐舒心注射劑 0.01%（Easy-Isosorbide Injection 0.01%，isosorbide）仿單 | TFDA | MA | `eligible` |
| cand-0278 | 恩舒注射劑0.4毫克/毫升（N.T.G. Premixed Injection 0.4mg/mL，nitroglycerin）仿單 | TFDA | MA | `eligible` |
| cand-0279 | 潰滿定膜衣錠２０公絲（啡莫替定）（QUIMADINE F.C. TABLETS 20MG (FAMOTIDINE)，famotidine）仿單 | TFDA | MA | `eligible` |
| cand-0280 | "豐田"莫痙錠10毫克(多普利杜)（Motin Tablets 10mg "Honten"(Domperidone)，domperidone）仿單 | TFDA | MA | `eligible` |
| cand-0281 | "永勝" 永胃健糖衣錠１０毫克（美托拉麥）（DRINGEN S.C. TABLETS 10MG (METOCLOPRAMIDE) "EVEREST"，metoclop… | TFDA | MA | `eligible` |
| cand-0282 | “信東”摩暢膜衣錠 5 毫克（Mosa F.C. Tablets 5mg，mosapride）仿單 | TFDA | MA | `eligible` |
| cand-0283 | "太田"鎮拉定膠囊（樂必寧）（GENLATIN CAPSULES "TAITEN" (LOPERAMIDE)，loperamide）仿單 | TFDA | MA | `eligible` |
| cand-0284 | 美腸順 腸溶錠 400毫克（Mesaclon Enteric Film Coated  Tablets 400 mg，mesalazine）仿單 | TFDA | MA | `eligible` |
| cand-0285 | "井田" 利肝膽膠囊300毫克（Legan Capsules 300mg "Chinteng"，ursodeoxycholic）仿單 | TFDA | MA | `eligible` |
| cand-0286 | 樂寶寧 膜衣錠50毫克（Lustraline Film Coated Tablets 50mg，sertraline）仿單 | TFDA | MA | `eligible` |
| cand-0287 | ”生達”伏鬱微粒膠囊１０公絲（FLUX MICROENCAPSULATED CAP.10MG "STANDARD"，fluoxetine）仿單 | TFDA | MA | `eligible` |
| cand-0288 | 康緒平錠37.5毫克（Calmdown Tablets 37.5mg，venlafaxine）仿單 | TFDA | MA | `eligible` |
| cand-0289 | 憂必舒膠囊30毫克（Ulitine Capsules 30mg，duloxetine）仿單 | TFDA | MA | `eligible` |
| cand-0290 | “新瑞”邁慮煩 膜衣錠 15 毫克（Minivane F.C. Tablets 15mg“synray”，mirtazapine）仿單 | TFDA | MA | `eligible` |
| cand-0291 | "應元"百適存持續性藥效錠300毫克（Bestrim XL 300mg Tablets "Y.Y."，bupropion）仿單 | TFDA | MA | `eligible` |
| cand-0292 | "杏輝"杏緩妥錠５０公絲（鹽酸查諾頓）（CIRZODONE TABLET 50MG "SINPHAR"(TRAZODONE                   HYD… | TFDA | MA | `eligible` |
| cand-0293 | 理思必妥 膜衣錠１毫克（Risperdal Film Coated Tablet 1mg，risperidone）仿單 | TFDA | MA | `needs_review` |
| cand-0294 | 羅亞達口溶錠10毫克（Arizole Orally Disintegrating Tablets 10mg，aripiprazole）仿單 | TFDA | MA | `eligible` |
| cand-0295 | 鋰康膠囊300毫克（Lithcan Capsules 300 mg，lithium）仿單 | TFDA | MA | `eligible` |
| cand-0296 | "威勝" 樂眠錠1毫克（Larpam Tablets 1 mg “W.S.”，lorazepam）仿單 | TFDA | MA | `eligible` |
| cand-0297 | "新喜" 心氣寧錠（SINDILIUM TABLETS "N.C.P."，diazepam）仿單 | TFDA | MA | `eligible` |
| cand-0298 | 妥泰膜衣錠２００毫克（TOPAMAX FILM-COATED TABLETS 200MG，topiramate）仿單 | TFDA | MA | `needs_review` |
| cand-0299 | 普疼立寧膠囊75毫克（Pregabalin Capsules 75mg "C.C.P.C."，pregabalin）仿單 | TFDA | MA | `eligible` |
| cand-0300 | “榮民”癲可停膠囊１００毫克（EPILEPTIN CAPSULES 100MG，phenytoin）仿單 | TFDA | MA | `eligible` |
| cand-0301 | 痛搏適膠囊400毫克（Seconbrex Capsule 400mg，celecoxib）仿單 | TFDA | MA | `eligible` |
| cand-0302 | 馬蓋先膜衣錠４００公絲（黃布洛芬）（MACSAFE F.C.TABLETS 400MG (IBUPROFEN)，ibuprofen）仿單 | TFDA | MA | `eligible` |

### 批 5（cand-0303–cand-0332；eligible 30、needs_review 0、rejected 0）

| 候选 | 标题 | 来源 | 部门 | 决定 |
| --- | --- | --- | --- | --- |
| cand-0303 | "應元"拿痛仙錠250毫克(那普洛仙)（Natoxen Tablets 250mg"Y.Y."(Naproxen)，naproxen）仿單 | TFDA | MA | `eligible` |
| cand-0304 | 益妥瑞膜衣錠120毫克（Terexib Film-coated Tablets 120mg，etoricoxib）仿單 | TFDA | MA | `eligible` |
| cand-0305 | 蒙地卡膜衣錠 10 毫克（Monteka F.C. Tablets 10 mg，montelukast）仿單 | TFDA | MA | `eligible` |
| cand-0306 | "國嘉"息舒寧液5.34毫克/毫升（Theolin oral Solution 5.34mg/mL "Kojar"，theophylline）仿單 | TFDA | MA | `eligible` |
| cand-0307 | "大豐"抒敏膜衣錠60毫克（"T.F." Su-min F.C. Tablets 60mg，fexofenadine）仿單 | TFDA | MA | `eligible` |
| cand-0308 | "強生"暢適得膜衣錠5毫克（Fencare FCT 5mg "Johnson"，solifenacin）仿單 | TFDA | MA | `eligible` |
| cand-0309 | 虎讚膜衣錠10毫克（Zan Film-Coated Tablets 10mg，tadalafil）仿單 | TFDA | MA | `eligible` |
| cand-0310 | 士力挺膜衣錠50毫克（Sliting F.C. Tablets 50mg，sildenafil）仿單 | TFDA | MA | `eligible` |
| cand-0311 | "汎生"僕樂彼錠５０毫克（POLUPI TABLET 50MG "PANBIOTIC"，propylthiouracil）仿單 | TFDA | MA | `eligible` |
| cand-0312 | 使汝健硬膠囊（Shi ru jian capsules，prednisolone）仿單 | TFDA | MA | `eligible` |
| cand-0313 | "國嘉" 得佳錠0.5毫克（迪皮質醇）（DECA TABLETS 0.5MG (DEXAMETHASONE) "KOJAR"，dexamethasone）仿單 | TFDA | MA | `eligible` |
| cand-0314 | "杏輝"杏節挺錠（PlusDmax Tablets "Sinphar"，alendronate）仿單 | TFDA | MA | `eligible` |
| cand-0315 | "安星" 克風迅錠0.5毫克（Cofoncin Tablets 0.5mg "Astar"，colchicine）仿單 | TFDA | MA | `eligible` |
| cand-0316 | "信東" 撒樂腸溶錠５００公絲（SALAZINE ENTERIC COATED TABLETS 500MG (SULFASALAZINE) "S.T."，sulfas… | TFDA | MA | `eligible` |
| cand-0317 | 憶如新膜衣錠10毫克（Memsyn F.C. Tablets 10mg，memantine）仿單 | TFDA | MA | `eligible` |
| cand-0318 | "應元"耳循膜衣錠8毫克（ECYCLE F.C.TABLETS 8MG "Y.Y."，betahistine）仿單 | TFDA | MA | `eligible` |
| cand-0319 | 優樂欣注射劑（希福辛）（UROXIME INJECTION (CEFUROXIME)，cefuroxime）仿單 | TFDA | MA | `eligible` |
| cand-0320 | "生達"舒維速保膠囊２５０毫克（賜福力欣）（SERVISPOR CAPSULES 250MG "STANDARD"(CEPHALEXIN)，cephalexin）仿單 | TFDA | MA | `eligible` |
| cand-0321 | 默菌殺點眼液（Micromox Eye Drops (Moxifloxacin Ophthalmic Solution USP 0.5% w/v)，moxifloxa… | TFDA | MA | `eligible` |
| cand-0322 | 獨拉膠囊（去氧羥四環素）（BISTOR CAPSULE (DOXYCYCLINE) "SHITEH"，doxycycline）仿單 | TFDA | MA | `eligible` |
| cand-0323 | 黴祐膠囊５０公絲（氟可那挫）（AZOL FLUCON CAPSULES 50MG(FLUCNAZOLE)，fluconazole）仿單 | TFDA | MA | `eligible` |
| cand-0324 | 敵疱治錠２００公絲（艾賽可威）（ACYLETE TABLETS 200 MG (ACYCLOVIR)，acyclovir）仿單 | TFDA | MA | `eligible` |
| cand-0325 | 硝弗侖陶因錠１００公絲（NITROFURANTOIN TABLETS 100MG "R.S.P.P"，nitrofurantoin）仿單 | TFDA | MA | `eligible` |
| cand-0326 | 順治炎錠（SINZUIN TABLETS "YUNG CHI"，sulfamethoxazole）仿單 | TFDA | MA | `eligible` |
| cand-0327 | 瑞保清膜衣錠0.5毫克（Hepato-ease F.C. Tablets 0.5mg，entecavir）仿單 | TFDA | MA | `eligible` |
| cand-0328 | 惠肝怡錠300毫克（Hucanon Tablets 300mg，tenofovir）仿單 | TFDA | MA | `eligible` |
| cand-0329 | 輔適納膜衣錠2.5毫克（Letramase F.C. Tablets 2.5mg，letrozole）仿單 | TFDA | MA | `eligible` |
| cand-0330 | 消汝妥1毫克（Arbreast F.C. Tab. 1mg (Anastrozole)，anastrozole）仿單 | TFDA | MA | `eligible` |
| cand-0331 | 癌可泰膜衣錠50毫克（Bicalutamide-Acepharm film coated tablets 50mg，bicalutamide）仿單 | TFDA | MA | `eligible` |
| cand-0332 | 立悠克膠囊100毫克（Leukure Micro-T Capsules 100mg，imatinib）仿單 | TFDA | MA | `eligible` |

## 入库前仍需完成

- 按官方 `pdf_url` 重新下载，核对 SHA-256、页数、可抽取文本和版本状态；使用现行且质量合格的原件。
- 对本轮获批的 TFDA 仿單逐页核查图像层版权、保密及额外限制标记；cand-0316 已核两页，但它的文本抽取质量仍须单独把关。
- 落实 ICH/EMA/TFDA 的署名与标志、第三方内容边界；`needs_review` 和 `rejected` 条目不得进入语料。
- 扩充 PV 语料时先保持现有来源白名单，达不到配额再提交新来源决策。
