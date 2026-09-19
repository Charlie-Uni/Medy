# 探针集 v1 样本草稿：CO 批次（16 条，待决策人逐条确认）

> 每条请判断五件事：问题是否自然且只有这一句能回答；key_text 是否最短且页内唯一（工具已核对唯一性）；span 是否完整条款；切片标签；部门归属。
> 确认方式：在「结论」列填 OK，或直接改写 query / key_text / span / slices；改动的条目我重新计算偏移。

| ID | 文档 | 页 | 切片 | query | key_text | evidence_span | 章节 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pc-0060 | ich-e8-r1-step4-2021 | 8 | negation, mixed_zh_en | ICH E8(R1) 对研究程序和评估的科学必要性及受试者负担有什么要求？ | do not place undue burden | Throughout drug development, care should be taken to ensure all study procedures and assessments are necessary from a scientific viewpoint and do not place undue burden on study participants. | 2.1 Protection of Clinical Study Participants | OK |

| pc-0061 | ich-e8-r1-step4-2021 | 9 | negation, mixed_zh_en | 按照 ICH E8(R1)，回顾性开展的文件和数据审查、监查，即使结合稽查，是否足以保证临床研究质量？ | not sufficient to ensure quality | Activities such as document and data review and monitoring, where conducted retrospectively, are an important part of a quality assurance process; but, even when combined with audits, they are not sufficient to ensure quality of a clinical study. | 3.1 Quality by Design of Clinical Studies | OK |

| pc-0062 | ich-e8-r1-step4-2021 | 11 | negation, mixed_zh_en | 按照 ICH E8(R1)，关键质量因素（critical to quality factors）应避免混入哪类事项？ | should not be cluttered with minor issues | The critical to quality factors should be clear and should not be cluttered with minor issues (e.g., due to extensive secondary objectives or processes/data collection not linked to the proper protection of the study participants and/or primary study objectives). | 3.2 Critical to Quality Factors | OK |

| pc-0063 | ich-e8-r1-step4-2021 | 7 | mixed_zh_en | ICH E8(R1) 的哪一节讨论研究实施、受试者安全和研究报告？ | Section 6 | Section 6 addresses study conduct, ensuring the safety of study participants, and study reporting. | 1. OBJECTIVES OF THIS DOCUMENT | OK |

| pc-0064 | ich-e8-r1-step4-2021 | 8 | mixed_zh_en | 按照 ICH E8(R1)，quality by design 要把质量主动设计进研究的哪些部分？ | study protocol and processes | Quality by design in clinical research sets out to ensure that the quality of a study is driven proactively by designing quality into the study protocol and processes. | 2.2 Scientific Approach in Clinical Study Design, Planning, Conduct, Analysis, and Reporting | OK |

| pc-0065 | ich-e6-r3-step4-2025 | 13 | negation, mixed_zh_en | 按照 ICH E6(R3) 的 GCP 原则，申办方能否给受试者和研究者增加不必要的负担？ | should not place unnecessary burden | The sponsor should not place unnecessary burden on participants and investigators. | II. PRINCIPLES OF ICH GCP / 7.4 | OK |

| pc-0066 | ich-e6-r3-step4-2025 | 16 | negation, mixed_zh_en | 按照 ICH E6(R3)，合理报销受试者实际发生的交通和住宿等费用，是否属于胁迫？ | is not coercive | Reasonable reimbursement of expenses incurred by participants, such as for travel and lodging, is not coercive. | III. ANNEX 1 / 1.2 Responsibilities / 1.2.8 | OK |

| pc-0067 | ich-e6-r3-step4-2025 | 13 | mixed_zh_en | 按照 ICH E6(R3)，必要记录应由哪些主体安全保存，保存期限依据什么确定？ | retained securely by sponsors and investigators | Essential records should be retained securely by sponsors and investigators for the required period in accordance with applicable regulatory requirements. | II. PRINCIPLES OF ICH GCP / 9.5 | OK |

| pc-0068 | ich-e6-r3-step4-2025 | 8 | mixed_zh_en | ICH E6(R3) 建立在哪份 ICH 指南的核心概念之上？ | ICH E8(R1) | This guideline builds on key concepts outlined in ICH E8(R1) General Considerations for Clinical Studies. | I. INTRODUCTION | OK |

| pc-0069 | ich-e6-r3-step4-2025 | 14 | mixed_zh_en | 按照 ICH E6(R3)，试验用药品应依据哪些文件使用？ | the protocol and relevant trial documents | Investigational products should be used in accordance with the protocol and relevant trial documents. | II. PRINCIPLES OF ICH GCP / 11.3 | OK |

| pc-0070 | ich-e6-r3-step4-2025 | 18 | mixed_zh_en | ICH E6(R3) 对 IRB/IEC 应保留的相关记录列举了哪些例子？ | retain all relevant records | The IRB/IEC should retain all relevant records (e.g., documented procedures, membership lists, lists of occupations/affiliations of members, submitted documents, minutes of meetings and correspondence) in accordance with applicable regulatory requirements and make them available upon request from the regulatory authority(ies). | III. ANNEX 1 / 1.5 Records / 1.5.1 | OK |

| pc-0071 | fda-protocol-deviations-draft-2024 | 7 | mixed_zh_en | FDA 2024 年《方案偏离》指南草案如何定义 important protocol deviation？ | might significantly affect the completeness | As noted above, in this guidance an important protocol deviation is a subset of protocol deviations that might significantly affect the completeness, accuracy, and/or reliability of the study data or that might significantly affect a subject’s rights, safety, or well-being. | III.A.1. Important Protocol Deviations | OK |

| pc-0072 | fda-protocol-deviations-draft-2024 | 5 | mixed_zh_en | FDA 2024 年《方案偏离》指南草案采用哪份 ICH 文件中的方案偏离和重要方案偏离定义？ | adopting the ICH E3(R1) | In this guidance, FDA is adopting the ICH E3(R1) definitions of protocol deviation and important protocol deviation. | II. BACKGROUND | OK |

| pc-0073 | fda-protocol-deviations-draft-2024 | 9 | time_window, mixed_zh_en | 按照 FDA 2024 年《方案偏离》指南草案，医疗器械研究为紧急保护受试者生命或身体健康而偏离研究计划时，研究者最迟应在紧急情况发生后几个工作日内通知申办方和 IRB？ | no later than 5 working days | Similarly, for device investigations, investigators must keep records of each protocol deviation (21 CFR 812.140(a)(4)) and must notify the sponsor and the IRB of any deviation from the investigational plan to protect the life or physical well-being of a subject in an emergency as soon as possible but no later than 5 working days after the emergency occurred (21 CFR 812.150(a)(4)). | III.B.1. Role of the Investigator in Monitoring, Mitigating, and Reporting Protocol Deviations | OK |

| pc-0074 | fda-protocol-deviations-draft-2024 | 13 | negation, mixed_zh_en | 按照 FDA 2024 年《方案偏离》指南草案，未被归类为 important 且不对受试者构成明显即时危险的方案偏离，需要立即报告给 IRB 吗？ | do not need to be immediately reported | All other protocol deviations that are not classified as important and do not present an apparent immediate hazard to participants do not need to be immediately reported to the IRB. | III.B.3. Role of the IRB in Evaluating Protocol Deviations | OK |

| pc-0075 | fda-protocol-deviations-draft-2024 | 4 | negation, mixed_zh_en | 根据 FDA 2024 年《方案偏离》指南草案的说明，FDA 法规是否给 protocol deviation 下了定义？ | do not include a definition | FDA regulations do not include a definition of the term protocol deviation or provide a system for classifying the various types of deviations that may occur during the conduct of a clinical investigation. | I. INTRODUCTION | OK |

切片计数：{'negation': 7, 'mixed_zh_en': 16, 'protocol_id': 0, 'time_window': 1}；部门：{'CO': 16}；语言：{'mixed': 16}
