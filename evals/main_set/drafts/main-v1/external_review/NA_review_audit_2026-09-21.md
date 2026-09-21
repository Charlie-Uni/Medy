# NA 批次逐条审校与 PDF 引用自审记录

**状态：`main-v1-provisional`；AI 辅助审校建议；第二人工复核未完成。**

## 结果汇总

- 样本：63；建议保留 `OK`：**62**；建议删除 `DROP`：**1**。
- 有实质字段修改（query/topic/slices）：**28**；其中 query/topic 修改 **13** 条，切片修改 **19** 条。
- 部门：PV 23 / CO 16 / MA 24，**无部门迁移建议**。
- 涉及唯一源 PDF：**63**；本地 SHA-256 复算全部通过：**True**。

## 关键裁决

- **ms-0487 — DROP。** ICH E2C(R2) 本身直接列出了 PBRER Executive Summary 应包含的项目，因此该问题不是 no-answer。
- **部分可回答的问题已收窄，而不是误留原问法。** 例如 ms-0492：E6(R3) 规定 IRB/IEC 应审查付款金额与方法、付款应及时且按比例，但未规定统一金额/公式，因此问题改为“是否规定固定金额、公式或费率”。
- **ms-0485**：E19 确实说出现安全性担忧时可能需要加强监测或恢复全面收集，但没有预设量化阈值/固定算法，因此据此收窄。
- **ms-0480、ms-0484、ms-0494** 均保留为 no-answer，但改成询问“固定判定阈值/成员人数或比例”，避免把指南已有的原则性考虑误当作完全无内容。
- **ms-0511、ms-0512、ms-0517** 改成询问是否有“明确驾车/操作机械限制”。来源中可见嗜睡、头晕等相关信息，但未给出明确操作限制，不能把“存在不良反应信息”误判成已回答驾驶限制。
- **ms-0520** 收窄为“非严重肾功能受损的具体减量数值/给药间隔方案”：仿单有严重肾衰竭禁忌及肾功能受损慎用，但没有分级减量表。

## 版本与引用自审特别事项

- `ema-gvp-annex-i-rev4`：所供 Rev 4 PDF 自身标明已失效、仅作历史公开访问；当前材料中没有更新的 Annex I，因此本轮只能按该 document key 审核，并在记录中保留历史状态。
- `fda-investigator-safety-reporting-2021`：**document key 年份与实际上传文件不一致**。实际核对的是 2025 年 12 月 FDA 最终版 *Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices*。
- `fda-protocol-deviations-draft-2024`：所供文件为 **December 2024 DRAFT — Not for Implementation**，没有把它写成正式生效指南。
- `tfda-label-glimaryl-tablets-2mg-glimepiride`：PDF 文字层乱码；本轮额外查看了物理页图像，不以乱码文本的缺词结果单独作 no-answer 结论。

## 逐条记录

| ID | 决定 | 部门 | 修改 | 源 PDF / 物理页 | 审校结论 |
| --- | --- | --- | --- | --- | --- |
| ms-0462 | OK | PV | — | `93435355242b…pdf` p19 | Annex I Rev 4 defines ICSR/minimum case elements but gives no numeric EudraVigilance submission deadline. The supplied Rev 4 copy is explicitly superseded/historical; no newer Annex I was supplied. |
| ms-0463 | OK | PV | slices:-protocol_id | `197de2bc0cfb…pdf` p8 | Module I requires submission of serious/non-serious adverse reactions within legally required time limits and points to process guidance, but does not state a numeric day count. |
| ms-0464 | OK | PV | slices:-protocol_id | `d0e530f1b15c…pdf` p8 | Module IV provides communication of audit findings, auditee feedback and grading, but no formal appeal/reconsideration mechanism for contesting critical/major grading. |
| ms-0465 | OK | PV | slices:-protocol_id | `7a649643af0a…pdf` p8 | Addendum I describes statistical signal-detection methods and specific age groups, but does not prescribe a pregnancy-specific signal-detection method. |
| ms-0466 | OK | PV | slices:-protocol_id | `4993d9f6a6a6…pdf` p3 | Addendum I states the MAH collaboration duty for duplicate detection, but does not specify a penalty/sanction for failure to collaborate. |
| ms-0467 | OK | PV | slices:-protocol_id | `53bb1c46db48…pdf` p3 | Addendum II states that original ICSR XML submissions are preserved for regulatory/audit purposes, but gives no fixed retention period for masked personal data. |
| ms-0468 | OK | PV | slices:-protocol_id | `49c5e574e929…pdf` p53 | Module VII describes EU PSUR single assessment procedure but does not state the amount of an EMA assessment fee. |
| ms-0469 | OK | PV | query、topic、slices:-protocol_id | `847b0c095bc6…pdf` p11 | Module VIII covers human-subject safeguards and informed-consent compliance at a high level, but does not provide an item-by-item required content list for the PASS consent form. |
| ms-0470 | OK | PV | query、topic | `15eb6d4ef94b…pdf` p6 | Module X gives the initial five-year period and assigns list maintenance/removal responsibilities, but no specific post-five-year assessment criteria or review workflow for removal. |
| ms-0471 | OK | PV | slices:-protocol_id | `790ce9ffdcf7…pdf` p13 | Module XV sets DHPC coordination obligations but does not specify fines, sanctions, or penalties for missing an agreed dissemination schedule. |
| ms-0472 | OK | PV | — | `9f4ae57fdfa9…pdf` p37 | Module XVI refers to package-leaflet readability guidance and possible symbols/pictograms, but does not provide an approved pictogram catalogue with meanings. |
| ms-0473 | OK | PV | — | `0d68ef884e72…pdf` p20 | The vaccine chapter discusses cold-chain/handling deviations and their pharmacovigilance implications, but does not prescribe a numeric storage temperature range. |
| ms-0474 | OK | CO | — | `140b612e6fe3…pdf` p5 | The 2009 FDA investigator-responsibilities guidance refers readers to 21 CFR Part 54 but does not set out the substantive financial-disclosure requirements. |
| ms-0475 | OK | PV | — | `c597c1d15d04…pdf` p9 | The supplied source corresponding to this document key is the December 2025 final FDA Investigator Responsibilities—Safety Reporting guidance; it states reporting duties/timing but no investigator penalty/disqualification scheme for late SAE reporting. |
| ms-0476 | OK | CO | — | `3b172d83fd53…pdf` p10 | The December 2024 FDA document is Draft—Not for Implementation. It discusses protocol-deviation information in study/safety reports but does not require important deviations to be submitted specifically in the IND annual report under §312.33. |
| ms-0477 | OK | CO | — | `2c0d04faa13f…pdf` p12 | FDA RBM Q&A says significant monitoring issues should be evaluated/documented and acted on timely/promptly, but gives no fixed number of days or business days for reporting them to FDA. |
| ms-0478 | OK | CO | — | `76556b1dcf14…pdf` p6 | The 2013 risk-based monitoring guidance identifies centralized monitoring personnel/functions but does not prescribe specific credentials, certification, or training requirements for centralized monitors. |
| ms-0479 | OK | CO | slices:-protocol_id | `034b29a6d1b5…pdf` p30 | ICH E10 discusses non-inferiority margins and implications for sample size but does not provide a specific sample-size formula. |
| ms-0480 | OK | CO | query、topic | `be9f56e84b67…pdf` p19 | ICH E11(R1) discusses factors relevant to pediatric extrapolation, but does not provide fixed thresholds/decision table categorising full, partial, or no extrapolation. |
| ms-0481 | OK | CO | — | `d09627c2d02d…pdf` 全文件/相关章节 | E12A addresses antihypertensive efficacy/safety study principles but does not require quality-of-life or patient-reported outcome assessment. |
| ms-0482 | OK | CO | query、topic、slices:-protocol_id | `6199a1a27063…pdf` p7 | ICH E14 discusses design, confidence intervals and assay sensitivity of the thorough QT/QTc study, but does not prescribe a fixed sample count or universal sample-size formula. |
| ms-0483 | OK | CO | slices:-protocol_id | `40516566c939…pdf` p8 | ICH E15 explains double-coded samples, coding keys, custody/access, but does not specify a retention duration for the linkage between the first and second keys. |
| ms-0484 | OK | CO | query、topic、slices:-protocol_id | `e67211a8358f…pdf` p22 | ICH E17 recommends a central independent DMC with representation from participating regions in relevant MRCTs, but gives no member count or regional representation ratio. |
| ms-0485 | OK | CO | query、topic、slices:-protocol_id | `6daddce21ed2…pdf` p12 | ICH E19 explicitly notes that emerging concerns may require intensified monitoring or reversion to comprehensive collection, but does not give preset quantitative triggers or a fixed decision algorithm. |
| ms-0486 | OK | PV | — | `1c095d804192…pdf` p7 | ICH E2A defines expedited-reporting timeframes but does not specify regulatory penalties/sanctions for late submission. |
| ms-0487 | DROP | PV | — | `0f883c2e4804…pdf` p14 | DROP: the document directly answers the question. ICH E2C(R2) lists the Executive Summary contents, including introduction, reporting interval, product details, exposure, approved countries, benefit-risk summary, safety actions and conclusions. |
| ms-0488 | OK | PV | slices:-protocol_id | `c8a076cc8567…pdf` p10 | ICH E2D directs non-serious ADRs to periodic safety reporting according to ICH E2C but does not set the PSUR submission periodicity itself. |
| ms-0489 | OK | PV | slices:-protocol_id | `8b5ee3235588…pdf` p10 | ICH E2E lists PSURs among routine pharmacovigilance activities but does not provide a PSUR submission interval. |
| ms-0490 | OK | PV | — | `7912d4d0f2b5…pdf` p10 | ICH E2F covers DSUR format/presentation and regional consultation but does not mandate a universal submission language such as English or sponsor-country official language. |
| ms-0491 | OK | CO | slices:-protocol_id | `032d53bb6d69…pdf` p30 | ICH E3 recommends use of a standard adverse reaction/events dictionary for grouping events but does not prescribe a specific dictionary version. |
| ms-0492 | OK | CO | query、topic | `e6ce19e36ce7…pdf` p16 | ICH E6(R3) requires IRB/IEC review of payment amount/method and sets anti-coercion principles, but does not prescribe a uniform monetary amount, formula, or fixed rate. |
| ms-0493 | OK | CO | slices:-protocol_id | `cbe681cf342e…pdf` p4 | ICH E7 addresses inclusion/representation of older patients and relevant clinical considerations, but does not mandate a named frailty or functional-status scale such as Karnofsky or ADL. |
| ms-0494 | OK | CO | query、topic | `99d56638828c…pdf` p25 | ICH E8(R1) describes the role and need for an independent DMC, but does not prescribe a fixed member count, professional composition ratio, or role quota. |
| ms-0495 | OK | CO | — | `f7471f411f1c…pdf` p16 | ICH E9(R1) states that the proportion of missing data can undermine robustness and motivates sensitivity analysis, but gives no numeric percentage/cutoff that automatically triggers a stricter analysis. |
| ms-0496 | OK | PV | — | `ea0824b58213…pdf` p25 | The MedDRA Data Retrieval PTC describes SMQ validation/use and search approaches, but does not tabulate numeric sensitivity, specificity, or PPV values for individual SMQs. |
| ms-0497 | OK | PV | — | `0f49c22f2c45…pdf` 全文件/相关章节 | The MedDRA Introductory Guide notes that it is included with a MedDRA subscription, but does not list subscription fee amounts or pricing rates. |
| ms-0498 | OK | PV | query、topic | `ae1ef0a4b12c…pdf` p9 | The SMQ guide explains availability within MedDRA releases/support documentation but does not list a separate MSSO/ICH licence or subscription fee amount/rate for SMQ use. |
| ms-0499 | OK | PV | — | `5fedc7fea015…pdf` p9 | The MedDRA v25 What’s New document refers readers to the SMQ Introductory Guide for the new noninfectious myocarditis/pericarditis SMQ; it does not itself list the PT membership and narrow/broad algorithm. |
| ms-0500 | OK | PV | — | `f5f597affd02…pdf` p6 | The TFDA guide says an invalid/returned report may delay formal reporting and the reporter bears responsibility, but it gives no fine amount or penalty schedule. |
| ms-0501 | OK | MA | — | `35ae3bb3cb14…pdf` p4 | Amaryl label contains dosing/food information but no grapefruit/grapefruit-juice interaction guidance. |
| ms-0502 | OK | MA | — | `2b8ab3b1bfea…pdf` p2 | Cancliol label lists contraindications/interactions but no fluoxetine/paroxetine/CYP2D6-inhibitor dose-adjustment instruction. |
| ms-0503 | OK | MA | — | `662b69e6044e…pdf` p1 | Carvetone/clopidogrel label discusses multiple drug interactions but no grapefruit-juice interaction. |
| ms-0504 | OK | MA | — | `5ef121b394cb…pdf` 全文件/相关章节 | Cinolone/ciprofloxacin IV label contains no grapefruit or citrus-juice interaction instruction. |
| ms-0505 | OK | MA | — | `8f274dc347f7…pdf` p1 | Concor label describes CYP3A4/CYP2D6 metabolism and other pharmacology but no grapefruit-juice advice. |
| ms-0506 | OK | MA | — | `42f20f2b5b0e…pdf` p3 | Deurinol label provides renal dose adjustment and liver monitoring information, but no concrete hepatic-impairment dose-adjustment regimen. |
| ms-0507 | OK | MA | — | `f80b904f4e2f…pdf` p4 | Esomen label gives storage conditions (25°C, dry/protected from light) but no shelf-life/expiry duration under those conditions. |
| ms-0508 | OK | MA | — | `70d3d976a3b4…pdf` 全文件/相关章节 | Esomepsun label contains no missed-dose instruction telling the patient whether to take or skip a forgotten dose. |
| ms-0509 | OK | MA | — | `b1756268da31…pdf` p1 | The Glimaryl PDF text layer is garbled; rendered physical pages were visually checked. The leaflet contains dosing/precautions/interactions/adverse reactions but no pharmacokinetic section with absorption rate, half-life and metabolic elimination pathway data. |
| ms-0510 | OK | MA | slices:-drug_name_zh | `c59161e8c6b4…pdf` p1 | Hetlosar label mentions a pediatric pharmacokinetic study but does not provide the requested oral bioavailability and plasma half-life values. |
| ms-0511 | OK | MA | query、topic | `8988edefb282…pdf` p6 | Ifonol label warns to take care if drowsiness occurs, but does not explicitly state a driving/machinery prohibition or other concrete operating restriction. |
| ms-0512 | OK | MA | query、topic | `ad8b0ba2d6c9…pdf` p6 | Lamofree label reports dizziness/diplopia and other adverse effects, but does not explicitly prescribe a driving/machinery restriction. |
| ms-0513 | OK | MA | — | `cb1abe12731f…pdf` p3 | Lanoxin label discusses P-glycoprotein and many interactions but no grapefruit-juice interaction. |
| ms-0514 | OK | MA | — | `b6af0d88b1f0…pdf` 全文件/相关章节 | Loformin/metformin label has dosing, contraindications and interactions but no grapefruit-juice interaction advice. |
| ms-0515 | OK | MA | slices:-drug_name_zh | `3981295da5a6…pdf` p1 | Losacar label gives dosing and interaction information but no instruction for handling a missed dose. |
| ms-0516 | OK | MA | — | `0879f3f5e1a1…pdf` 全文件/相关章节 | Perisafe/enalapril leaflet was checked through its end and does not provide storage conditions such as light protection or refrigeration. |
| ms-0517 | OK | MA | query、topic | `4c21c14e2ced…pdf` p5 | Purinol label warns to take care if drowsiness occurs, but does not explicitly state a driving/machinery prohibition or specific operating restriction. |
| ms-0518 | OK | MA | — | `6e54ef6f412d…pdf` p16 | Quetiapine label discusses CYP3A inhibitors and interactions but no grapefruit-juice instruction. |
| ms-0519 | OK | MA | — | `0c80faec13d3…pdf` p1 | Rodamine/loratadine label gives a reduced initial dose for severe hepatic impairment but no renal-impairment dose-adjustment regimen. |
| ms-0520 | OK | MA | query、topic | `0e8e316abd1f…pdf` p1 | Staren/diclofenac injection warns about renal impairment and contraindicates severe renal failure, but does not provide a renal-function-stratified numeric dose reduction or interval scheme for non-severe impairment. |
| ms-0521 | OK | MA | — | `4c2119065459…pdf` p1 | Valsartan label lists studied drug interactions but no grapefruit/grapefruit-juice interaction guidance. |
| ms-0522 | OK | MA | — | `3b1d0b7fb71d…pdf` 全文件/相关章节 | Venton/diclofenac injection label contains no grapefruit-juice interaction guidance. |
| ms-0523 | OK | MA | — | `c96703065f14…pdf` p1 | Vomiz/ondansetron label explains multi-enzyme metabolism and special-population dosing but no grapefruit-juice pharmacokinetic interaction. |
| ms-0524 | OK | MA | — | `81069adaf87d…pdf` p1 | Zosaa/losartan label lists several pharmacokinetic interactions but no grapefruit/grapefruit-juice interaction guidance. |

## 正式应用边界

- 本轮没有执行项目 `norm-v1` 的字符偏移重算、数据库写回或主评测集冻结。
- NA 表不含 gold span，因此本轮自审针对“文档是否确实不回答”及最近相关条款/版本定位；`absence_terms` 仅作为辅助，不能替代全文语义检查。
- 本表中的 `OK` 仍需 annotator-01 人工签署；第二人工复核仍未完成。
