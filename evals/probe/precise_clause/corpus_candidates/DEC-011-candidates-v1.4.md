# DEC-011 候选清单 v1.4：PV 白名单补件（待签）

编制：2026-09-28。承接 [v1.3 已签清单](DEC-011-candidates-v1.3.md)，旧 332 条记录原样保留；本版在 ADR-0003 既有 EMA/FDA 来源内增加 15 条 PV 候选。新条目的 `license_status=eligible` 仅为许可初判，`reviewer_decision` 全部为空，**未获签字、不得入库**。

## 已决疑点的原件核对

- cand-0114：ICH PDF 第 14 页含 ISO/HL7 第三方版权声明；`rejected`，不得入库。
- cand-0293：PDF 第 26 页图像层可见 `© Johnson & Johnson Taiwan Ltd. 2021`；维持 `needs_review`，不得入库。
- cand-0298：PDF 第 2 页图像层可见 `© Johnson & Johnson Taiwan Ltd. 2021`，文本抽取乱码；维持 `needs_review`，不得入库。
- cand-0316：PDF 第 2 页图像层是厂址后的圈号 `②`，文本层映射为 `©`；许可裁决维持 `eligible`，但文字质量未通过前不得入库。

## 新增 PV 候选（15 条）

官方 PDF 为许可核对入口。副本在 `evals/main_set/sources_staging/<sha256>.pdf`，该目录不入 Git。EMA 文档须署名、排除第三方内容；FDA 文档依据其网站公共领域声明初判。cand-0347 为 FDA 草案，仅可按草案身份使用。

| 候选 | 来源 | 页 | 文件 / 版本 | 官方 PDF | 本地 SHA-256 | 许可初判 | 签字 |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| cand-0333 | EMA | 51 | Guidance on the format of the risk management plan (RMP) in the EU – in integrated format (Rev. 2.0.1)（EMA/164014/2018 Rev 2.0.1） | [PDF](https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/guidance-format-risk-management-plan-rmp-eu-integrated-format-rev-201_en.pdf) | `fa09df2f5151397f7731b60fc8efafff3a00ce3d38c9c2396b136a383150f785` | `eligible` | **待签** |
| cand-0334 | EMA | 14 | Consideration on core requirements for RMPs of COVID-19 vaccines（EMA/PRAC/709308/2022; updated 2025-12-04） | [PDF](https://www.ema.europa.eu/en/documents/other/consideration-core-requirements-rmps-covid-19-vaccines_en.pdf) | `36419985fa3107cc0f59a36dcd77d77564beee1ce228b2238b2d6f36328d5471` | `eligible` | **待签** |
| cand-0335 | EMA | 10 | Guideline on specific adverse reaction follow-up questionnaires (Specific AR FUQ)（EMA/PRAC/490455/2023; effective 2025-02-01） | [PDF](https://www.ema.europa.eu/en/documents/scientific-guideline/guideline-specific-adverse-reaction-follow-questionnaires-specific-ar-fuq_en.pdf-0) | `247dcadd018fb6e0003169b8152363029ed6bcf50b67a18cbc17273bea8047a5` | `eligible` | **待签** |
| cand-0336 | EMA | 8 | Anonymisation of personal data and assessment of commercially confidential information during preparation of RMPs（EMA/63692/2025 Rev 3） | [PDF](https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/guidance-anonymisation-protected-personal-data-assessment-commercially-confidential-information-during-preparation-rmps-main-body-annexes-4-6_en.pdf) | `0484e6d398bd9e342781f66a1c94807f59f420349f09b49177465e42cb5d37b3` | `eligible` | **待签** |
| cand-0337 | EMA | 135 | EudraVigilance – EVWEB user manual（EMA/501718/2018 v1.11; updated 2026-02-24） | [PDF](https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/eudravigilance-evweb-user-manual_en.pdf) | `7d55f2f25c74a963ea39dfd2967a5ba7d1be410637b5359e238e80ad7f326070` | `eligible` | **待签** |
| cand-0338 | EMA | 36 | EudraVigilance user manual – Individual Case Safety Report form (v1.1)（EMA/249220/2016 v1.1） | [PDF](https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/eudravigilance-user-manual-individual-case-safety-report-form-version-11_en.pdf) | `ff3c71961ef108bb8550a6c15376a475f8629fb9dab26b2ab9ca667f3bb4994e` | `eligible` | **待签** |
| cand-0339 | EMA | 23 | EudraVigilance – user manual for online access via adrreports.eu portal (v2.2)（EMA/198270/2026 v2.2） | [PDF](https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/eudravigilance-european-database-suspected-adverse-reactions-related-medicines-user-manual-online-access-adrreportseu-portal_en.pdf) | `287504a08e166dc0b35805bac7d68cfb5d1f846040b82fa793319a97797c73fe` | `eligible` | **待签** |
| cand-0340 | EMA | 78 | EudraVigilance user manual for marketing authorisation holders (v2.1)（EMA/167839/2016 v2.1） | [PDF](https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/eudravigilance-user-manual-marketing-authorisation-holders_en.pdf) | `f4d0c789d09b970ffcb3df8f424fc048833ef9415b82bad7ef64e6d25edaf98d` | `eligible` | **待签** |
| cand-0341 | EMA | 8 | Compliance notifications explanation and Q&A（EMA/362031/2025） | [PDF](https://www.ema.europa.eu/en/documents/other/compliance-notifications-explanation-qa_en.pdf) | `5d21c78aec6bdb740e34094dbae95ddcc89e40401bc45c3ca6c3049f68d57e75` | `eligible` | **待签** |
| cand-0342 | EMA | 23 | Detailed guide regarding the EudraVigilance data management activities by EMA（EMA/533039/2019 Rev 1） | [PDF](https://www.ema.europa.eu/en/documents/other/detailed-guide-regarding-eudravigilance-data-management-activities-european-medicines-agency_en.pdf) | `6831728d59e2b86992f0caf4b3c62d026a5e3be9190dbb7975c4e9c3f1d7d1af` | `eligible` | **待签** |
| cand-0343 | FDA | 33 | Postapproval Pregnancy Safety Studies（Final, May 2026） | [PDF](https://www.fda.gov/media/124746/download) | `ae10b3c86f5f0fac157c8a58159488fbbab24a60d0a82b6a74cb49c0edf9699e` | `eligible` | **待签** |
| cand-0344 | FDA | 40 | Best Practices for FDA Staff in the Postmarketing Safety Surveillance of Human Drug and Biological Products（FDA staff best practices, 2024） | [PDF](https://www.fda.gov/media/130216/download) | `b7d23e7c34ea525323cc2a7779be9f20cc3b02ed1f5053394b2114da86028b0d` | `eligible` | **待签** |
| cand-0345 | FDA | 43 | REMS Document Technical Conformance Guide（Final, January 2023） | [PDF](https://www.fda.gov/media/164344/download) | `2710e27fa1b4c2fcad05cbd727092f8de7f42a29f14eef848d805352d74c6ff0` | `eligible` | **待签** |
| cand-0346 | FDA | 11 | Providing Submissions in Electronic Format — Postmarketing Safety Reports for Vaccines（Final, August 2015） | [PDF](https://www.fda.gov/media/93233/download) | `d41b33c6098b505e6feed2c27eb8e2697d4c9946dee34dbb3f1527d70c2670d5` | `eligible` | **待签** |
| cand-0347 | FDA | 26 | REMS Assessment: Planning and Reporting（Draft, February 2019） | [PDF](https://www.fda.gov/media/119790/download) | `7df6c6d734e0db9e549ad008e9874f34fb108753a9592815aeb4685697e7314c` | `eligible` | **待签** |

## 份数与后续门槛

- 按 v1.2 签字表原口径，PV 原缺 18 份；此次补 15 份，名义上尚缺 3 份。v1.3 已决状态与主集实际可摄取数不同，正式重冻结前须以去重、现行性、质量和许可门槛重新计算。
- 本 15 份已经过官方 URL、PDF 格式、SHA-256、页数、文本层和清单内重复 URL/标题/哈希核对。该机械核对不替代 ADR-0003 决策人签字。
- 签字建议：`cand-0333～0346 确认`；`cand-0347 确认（仅作草案并保留显著标识）`。若不采草案，仍可先签 14 份，缺口按实际入库数再补。
- 签字后：重新下载比对哈希；检查 EMA 第三方内容与 FDA PDF 单件限制；逐页确认可用文本，再提交 M5-01 摄取与主集重冻结。

**2026-09-28 裁决：确认，无排除项；cand-0347 接受仅作 FDA 草案入库。** 15 条逐项许可决定与使用边界已写入 [v1.5 签字结果](DEC-011-candidates-v1.5.md)及 [v1.5 JSON](DEC-011-candidates-v1.5.json)。本版 JSON 保留签字前快照。
