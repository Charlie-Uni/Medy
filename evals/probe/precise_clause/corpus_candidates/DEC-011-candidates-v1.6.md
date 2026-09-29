# DEC-011 候选清单 v1.6（M5-01 扩语料，记录 101）

编制：2026-09-29。承接 v1.5（347 条）；本版新增 **27 条**候选，来源限 ADR-0003 白名单（ICH / EMA / FDA / TFDA），每条附同日下载的 SHA-256、页数与文本层字符数；TFDA 仿單另附資料集 39/36 同日快照的逐字核对与现行性字段。`预判` 是机械核对结果，`eligible` 只表示许可依据与已签字候选同源且核对全部通过；签字前请按批回复（如「批 1 确认」或列出例外）。

## 分组汇总

| 分组 | 条数 | 部门 | 预判 eligible | 预判 needs_review | 许可依据 | 签字后待办 |
| --- | ---: | --- | ---: | ---: | --- | --- |
| FDA 指南 | 13 | PV 13 | 12 | 1 | fda.gov 公共领域政策 | 按 pdf_url 重新下载比对 sha256；pypdf 抽取页文本 |
| TFDA 仿單 | 14 | MA 14 | 14 | 0 | 資料集 9117/39 OGDL-1.0 | 逐页图像层目视（条件 3），入库时署名（条件 4） |

预判 eligible 的部门分布：MA 14, PV 12（决策 86 的目标是 MA 120 / PV 120 / CO 80 含现有 79 份）。

## 批 1（cand-0348 – cand-0374，27 条）

| 候选 | 标题 | 语言 | 部门 | 版本/日期 | 页 | 许可依据 | 预判 | 备注 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| cand-0348 | FDA Regional Implementation Guide for E2B(R3) Electronic Transmission of Individual Case … | en | PV | Final guidance, issued 08/01/2024; docket FDA-2016-D-1280 | 28 | fda.gov 公共领域政策 | eligible |  |
| cand-0349 | Safety Reporting Requirements for INDs and BA/BE Studies: Guidance for Industry and Inves… | en | PV | Final guidance, issued 12/20/2012; docket FDA-2010-D-0482 | 6 | fda.gov 公共领域政策 | eligible |  |
| cand-0350 | Providing Regulatory Submissions in Electronic Format: IND Safety Reports Guidance for In… | en | PV | Final guidance, issued 04/01/2024; docket FDA-2019-D-3953 | 11 | fda.gov 公共领域政策 | eligible |  |
| cand-0351 | Electronic Submission of IND Safety Reports Technical Conformance Guide : Guidance for In… | en | PV | Final guidance, issued 04/29/2022; docket FDA-2018-D-1216 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0352 | Electronic Submission of Expedited Safety Reports From IND-Exempt BA/BE Studies Guidance … | en | PV | Final guidance, issued 04/01/2024; docket FDA-2022-D-1173 | 11 | fda.gov 公共领域政策 | eligible |  |
| cand-0353 | Providing Submissions in Electronic Format – Postmarket Non-Expedited ICSRs Technical Que… | en | PV | Final guidance, issued 07/24/2013; docket FDA-2013-D-0755 | 8 | fda.gov 公共领域政策 | eligible |  |
| cand-0354 | Providing Regulatory Submissions in Electronic Format --Content of the Risk Evaluation an… | en | PV | Final guidance, issued 12/23/2020; docket FDA-2017-D-4303 | 7 | fda.gov 公共领域政策 | eligible |  |
| cand-0355 | Postmarketing Safety Reporting for Combination Products: Guidance for Industry and FDA St… | en | PV | Final guidance, issued 07/22/2019; docket FDA-2008-N-0424 | 44 | fda.gov 公共领域政策 | eligible |  |
| cand-0356 | Dear Health Care Provider Letters: Improving Communication of Important Safety Information | en | PV | Final guidance, issued 01/02/2014; docket FDA-2010-D-0319 | 20 | fda.gov 公共领域政策 | eligible |  |
| cand-0357 | Evaluating the Risks of Drug Exposure in Human Pregnancies | en | PV | Final guidance, issued 04/27/2005 | 31 | fda.gov 公共领域政策 | needs_review | 文本层命中版权/限制标记：reproduced with permission「Philadelphia: W.B. Saunders Company, p. 548) and reproduced 」 |
| cand-0358 | Real-World Data: Assessing Registries To Support Regulatory Decision-Making for Drug and … | en | PV | Final guidance, issued 12/22/2023; docket FDA-2021-D-1146 | 15 | fda.gov 公共领域政策 | eligible |  |
| cand-0359 | Real-World Data: Assessing Electronic Health Records and Medical Claims Data To Support R… | en | PV | Final guidance, issued 07/25/2024; docket FDA-2020-D-2307 | 39 | fda.gov 公共领域政策 | eligible |  |
| cand-0360 | Benefit-Risk Assessment for New Drug and Biological Products | en | PV | Final guidance, issued 10/17/2023; docket FDA-2020-D-2316 | 26 | fda.gov 公共领域政策 | eligible |  |
| cand-0361 | "永勝"歐適錠５公絲（羥布托尼）（OXIPAN TABLETS 5MG (OXYBUTYNIN CHLORIDE)"EVEREST"，oxybutynin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-09-09；許可證 衛署藥製字第041944號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0362 | "壽元"優尿錠５０公絲（本補麻隆）（UROTIN TABLETS 50MG  "S.Y." (BENZBROMARONE)，benzbromarone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-08-12；許可證 衛署藥製字第040173號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0363 | 彼洛喜錠（PROCID TABLETS，probenecid）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-09-09；許可證 衛署藥製字第007256號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0364 | 抑痛寧靜脈注射液（Analif for IV Injection，ketorolac）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2013-12-10；許可證 衛署藥製字第048390號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0365 | "明大"普士當錠５００毫克（邁菲那密酸）（MEFENAMIC ACID TABLETS 500MG "M.T"，mefenamic）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-12-29；許可證 衛署藥製字第034547號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0366 | 安妥清膠囊（ANTOCHIN CAPSULES，indomethacin）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-08-16；許可證 內衛藥製字第016925號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0367 | 風濕痛膠囊10毫克(匹洛西卡)（HONSUTON CAPSULES 10MG (PIROXICAM)，piroxicam）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-02-13；許可證 衛署藥製字第026593號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0368 | "南光" 舒解痛膜衣錠５００公絲（SUBUTON F.C. TABLETS 500MG "N.K."，nabumetone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2015-09-25；許可證 衛署藥製字第045709號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0369 | 可洛拉平錠100毫克（可洛慮平）（MEZAPIN TABLETS 100MG(CLOZAPINE)，clozapine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-05-24；許可證 衛署藥製字第042886號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0370 | "瑞士"舒神膜衣錠２００毫克（斯比樂）（SUSINE F.C.TABLETS 200MG  "SWISS"(SULPIRIDE)，sulpiride）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-02-01；許可證 衛署藥製字第040545號… | 4 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0371 | 美贊錠 200 毫克（Misul Tablets 200 mg，amisulpride）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-08-02；許可證 衛署藥製字第055051號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0372 | 佩里波持續性藥效錠3毫克（Pardone Extended-Release Tablets 3mg，paliperidone）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2019-04-03；許可證 衛部藥製字第060259號… | 6 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0373 | "泰和碩" 服緒妥糖衣錠（FUXITOL S.C. TABLETS 3MG "TAXO"，flupentixol）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2018-03-27；許可證 衛署藥製字第045664號… | 1 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |
| cand-0374 | 鹽酸氯普魯麻淨糖衣錠５０公絲（CHLORPROMAZINE HCL S.C. TABLETS 50MG "VPP"，chlorpromazine）仿單 | zh-Hant | MA | 仿單正文未见版本行；PDF 元数据 CreationDate 2016-01-26；許可證 衛署藥製字第006819號… | 2 | 資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核） | eligible |  |

## 未列入（机械核对未通过或不需要）

| 分组 | 原因 | 条数 |
| --- | --- | ---: |
| TFDA 仿單 | 同成分已有候选 / 超出配额 | 8 |
| TFDA 仿單 | 无文本层（扫描件） | 15 |

无文本层的文件（不做 OCR，按 ADR-0003 决策 2026-09-12 第 4 项；同成分已改试其他仿單）：優若亭 膜衣錠2毫克（Uridin F.C. Tablets 2mg，tolterodine）仿單（MA）；希妥定膜衣錠2毫克（Pharodine IR Film-Coated Tablets 2mg，tolterodine）仿（MA）；得舒妥膜衣錠2毫克（DETRUSITOL F.C. TABLETS 2MG，tolterodine）仿單（MA）；”聯邦”樂寧痛膜衣錠 10 毫克（Sukerin F.C. Tablets 10mg“Union”，ketorolac）（MA）；炎帝膜衣錠５００公絲〝永信〞（NABUTON FILM COATED TABLETS 500MG "YUNG SHIN"（MA）；寶齡痛疏膜衣錠750毫克（TONLEX F.C. TABLETS 750MG，nabumetone）仿單（MA）；"永勝"肉舒錠１０公絲（貝可芬）（ROLAX TABLETS 10MG (BACLOFEN) "EVEREST"，bac（MA）；肌利健錠５公絲（GABALON TABLETS 5MG，baclofen）仿單（MA）；"達德士"舒肌錠10毫克（Su Gei Tablets 10mg "D.T.S."，baclofen）仿單（MA）；立舒肌錠2毫克（Tizaflex Tablets 2mg，tizanidine）仿單（MA）；"信東" 來特平錠 25毫克（Zapine Tablets 25mg，clozapine）仿單（MA）；緒得克糖衣錠（MOODYTEC S.C. TABLETS，flupentixol）仿單（MA）；…等 15 份（全部见 dropped.json）

## 签字

决策人按批回复；每批的 `reviewer_decision` / `reviewer_note` 由实现方据回复写入下一版本文件（不覆盖本版）。
