# 探针集 v1 样本草稿：PV 批次（29 条，待决策人逐条确认）

> 每条请判断五件事：问题是否自然且只有这一句能回答；key_text 是否最短且页内唯一（工具已核对唯一性）；span 是否完整条款；切片标签；部门归属。
> 确认方式：在「结论」列填 OK，或直接改写 query / key_text / span / slices；改动的条目我重新计算偏移。

| ID | 文档 | 页 | 切片 | query | key_text | evidence_span | 章节 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pc-0031 | meddra-term-selection-ptc-4-26-zh-hans | 9 | negation, mixed_zh_en | MedDRA 的术语层级结构可以由使用机构自行更改吗？ | 不应更改 | MedDRA 是一个标准术语集，有预先界定的术语层级结构，不应更改。 | 2.3 不要改动 MedDRA | OK |

| pc-0032 | meddra-term-selection-ptc-4-26-zh-hans | 11 | negation, mixed_zh_en | 选择 MedDRA 术语时，可以使用非现行 LLT 吗？ | 不应使用非现行 LLT | 进行术语选择时不应使用非现行 LLT。 | 2.5 只选择现行低位语 | OK |

| pc-0033 | meddra-term-selection-ptc-4-26-zh-hans | 11 | negation, mixed_zh_en | MedDRA 缺少能充分反映报告信息的术语时，可以用机构自身的解决方法来处理这一不足吗？ | 不要用机构自身的解决方法 | 不要用机构自身的解决方法来处理 MedDRA 的不足。如果当前没有一个 MedDRA 术语足以反映报告的信息，请向 MSSO 提交变更申请。 | 2.6 何时就术语提出申请 | OK |
| pc-0034 | meddra-term-selection-ptc-4-26-zh-hans | 12 | mixed_zh_en | 选择一个 LLT 时，需要向上核对哪些 MedDRA 层级？ | PT 层级一直向上到 HLT、HLGT 和 SOC | 考虑选择一个 LLT 时，应查看该 LLT 之上的层级结构（PT 层级一直向上到 HLT、HLGT 和 SOC），以确保其放置位置准确反映了报告用语的含义。 | 2.9 查看层级结构 | OK |
| pc-0035 | meddra-term-selection-ptc-4-26-zh-hans | 35 | negation, mixed_zh_en | 在 E2B“相关实验室检查信息”中，为“血红蛋白 7.5 g/dL”编码检查名称时，可以选择 LLT 血红蛋白降低吗？ | 不应选择 LLT 血红蛋白降低 | 血红蛋白 7.5 g/dL 血红蛋白 不应选择 LLT 血红蛋白降低，因为它既有检查名称又有检查结果* *MedDRA 在用于 E2B 数据元素“相关实验室检查信息”部分时，只用于编码“检查项目”，而非“检查结果” | 3.14.5 不带限定词的检查结果 | OK |

|| pc-0036 | meddra-term-selection-ptc-4-26-zh-hans | 38 | time_window, mixed_zh_en | 药物说明书要求每月监测肝酶，患者却每六个月才测一次，这类用药错误应选择哪个 LLT？ | 用药监测步骤执行不正确 | 患者每 6 个月测一次肝酶，没有按照推荐日程即每月一次 用药监测步骤执行不正确 药物说明书上的监测日程是每月一次。该案例是在使用药物过程中没有遵照推荐的实验室检查执行的监测错误。 | 3.15.1.3 用药监测错误 | OK |

| pc-0037 | meddra-data-retrieval-ptc-3-26-zh-hans | 4 | mixed_zh_en | MedDRA 的多轴性是指什么？ | 将一个 PT 分配给多个系统器官分类 [SOC] | MedDRA 具备多轴性（将一个 PT 分配给多个系统器官分类 [SOC]），可通过主、次关联途径灵活地进行数据检索。 | SECTION 1 – 引言 | OK |

| pc-0038 | meddra-data-retrieval-ptc-3-26-zh-hans | 4 | time_window, mixed_zh_en | MedDRA《数据检索和展示：考虑要点》多久更新一次？ | 每年更新一次 | 本《数据检索和展示：考虑要点》（DRP:PTC）文档是 ICH 认可的 MedDRA 用户指南，每年更新一次，与 MedDRA 三月份版本同步发布（从 MedDRA 23.0 版本开始）。 | SECTION 1 – 引言 | OK |

| pc-0039 | meddra-data-retrieval-ptc-3-26-zh-hans | 9 | negation, mixed_zh_en | 在特定 HLT 或 HLGT 中检索多轴性 PT 时，能否假定该 PT 会显示在其次 SOC 路径中？ | 不要假定 PT 会显示在其次 SOC 路径中 | 在特定的 HLT 或 HLGT 中搜索时，不要假定 PT 会显示在其次 SOC 路径中，因为数据库结构可能不允许次 SOC 路径的输出或者展示。 | 2.4 机构自身数据的特点 | OK |

| pc-0040 | meddra-data-retrieval-ptc-3-26-zh-hans | 26 | negation, mixed_zh_en | 修改过术语内容或结构的 SMQ，还可以继续称为 SMQ 吗？ | 不应再称其为“SMQ” | 如果对一个 SMQ 的术语内容或结构作出任何修改，则不应再称其为“SMQ”，而应称其为“根据 SMQ 修改的 MedDRA 分析查询”。 | 4.4 SMQ 修改和机构所构建的分析查询 | OK |

| pc-0041 | ema-gvp-module-vi-rev2 | 9 | mixed_zh_en | 按照 GVP Module VI，一份有效的 ICSR 至少需要包含哪些要素？ | A valid ICSR should include | A valid ICSR should include at least one identifiable reporter, one single identifiable patient, at least one suspect adverse reaction, and at least one suspect medicinal product (see VI.B.2. for ICSRs validation). | VI.A.1.7. Individual case safety report (ICSR) | OK |

| pc-0042 | ema-gvp-module-vi-rev2 | 22 | time_window, mixed_zh_en | 按照 GVP Module VI，已按严重个案提交的 ICSR 因本次随访改判为非严重，这次随访信息仍应在多少天内提交？ | should still be submitted within 15 days | Where a case initially sent as serious becomes non-serious based on new follow-up information, this information should still be submitted within 15 days; the submission time frame for non-serious reports should then be applied for the subsequent follow-up reports. | VI.B.7.1. Submission time frames of ICSRs | OK |

| pc-0043 | ema-gvp-module-vi-rev2 | 41 | time_window, mixed_zh_en | 按照 GVP Module VI，对于需在欧盟提交的非严重有效 ICSR，成员国主管机构或上市许可持有人应在收到报告后多少天内提交？ | within 90 days | non-serious valid ICSRs shall be submitted by the competent authority in a Member State or by the marketing authorisation holder within 90 days from the date of receipt of the reports. | VI.C.3. Submission time frames of ICSRs in EU | OK |

| pc-0044 | ema-gvp-module-vi-rev2 | 7 | negation, mixed_zh_en | 按照 GVP Module VI，在成品放行前的生产过程中接触药品某一成分，是否属于这里定义的职业暴露？ | does not include the exposure to one of the ingredients | Occupational exposure: This refers to the exposure to a medicinal product (see definition in VI.A.1.3.), as a result of one’s professional or non-professional occupation. It does not include the exposure to one of the ingredients during the manufacturing process before the release as finished product. | VI.A.1.2. Overdose, off-label use, misuse, abuse, occupational exposure, medication error, falsified medicinal product | OK |

| pc-0045 | ema-gvp-module-ix-rev1 | 6 | time_window, mixed_zh_en | 按照 GVP Module IX，PRAC 报告员或负责的成员国应在收到已验证信号后多少天内完成信号确认？ | within 30 days | Signal confirmation by the PRAC Rapporteur or (lead) Member State: The process of deciding whether or not a validated signal entered in the European Pharmacovigilance Issues Tracking Tool (EPITT) requires further analysis and prioritisation by the PRAC. This should be done by the PRAC Rapporteur or the (lead) Member State within 30 days from receipt of the validated signal. | IX.A.1.2. Terminology specific to the EU signal management process with oversight of the Pharmacovigilance Risk Assessment Committee (PRAC) | OK |

| pc-0046 | ema-gvp-module-ix-rev1 | 12 | time_window, mixed_zh_en | 按照 GVP Module IX，欧盟上市许可持有人确认某个经验证的信号或其他来源的安全问题符合 emerging safety issue 定义后，最迟多久应通知有关监管机构？ | no later than 3 working days | When the marketing authorisation holder in the EU becomes aware of an emerging safety issue from any source (see IX.A.1.1.), they should notify it in writing to the competent authority(ies) of Member State(s) where the medicinal product is authorised11 and to the Agency to the mailbox “P-PV-emerging-safety-issue@ema.europa.eu”. This should be done as soon as possible and no later than 3 working days after establishing that a validated signal or a safety issue from any source meets the definition of an emerging safety issue. | IX.C.2. Emerging safety issues | OK |

| pc-0047 | ema-gvp-module-ix-rev1 | 6 | negation, mixed_zh_en | 按照 GVP Module IX，信号确认是否等同于对信号的完整评估？ | not intended to be a full assessment | Signal confirmation is not intended to be a full assessment of the signal. | IX.A.1.2. Terminology specific to the EU signal management process with oversight of the Pharmacovigilance Risk Assessment Committee (PRAC) | OK |

| pc-0048 | fda-sponsor-safety-reporting-2025 | 12 | time_window, mixed_zh_en | 按照 FDA 的 IND 安全报告要求，申办方首次收到未预期的致死或危及生命的可疑不良反应信息后，最迟多久必须通知 FDA？ | in no case later than 7 calendar days | For unexpected fatal or life-threatening suspected adverse reaction reports, the sponsor must notify FDA as soon as possible but in no case later than 7 calendar days after the sponsor’s initial receipt of the information (§ 312.32(c)(2)). | IV. OVERVIEW OF IND SAFETY REPORTING REQUIREMENTS | OK |

| pc-0049 | fda-sponsor-safety-reporting-2025 | 25 | mixed_zh_en | 按照 FDA 这份申办方安全报告指南，需要通过汇总分析来判断是否满足 IND 安全报告标准的两类事件是什么？ | anticipated SAEs and expected serious suspected adverse reactions | For anticipated SAEs and expected serious suspected adverse reactions, an aggregate analysis of the data is necessary to determine whether these events meet the criteria for reporting under § 312.32(c)(1)(i)(C) and (c)(1)(iv), respectively. | VI.C.1. Approach to Aggregate Analyses | OK |

| pc-0050 | fda-sponsor-safety-reporting-2025 | 5 | mixed_zh_en | 21 CFR 312.32 中，哪两条 IND 安全报告条款要求评估汇总数据？ | § 312.32(c)(1)(i)(C) and (c)(1)(iv) | To facilitate appropriate IND safety reporting practices, this guidance also provides recommendations related to the two IND safety reporting provisions (§ 312.32(c)(1)(i)(C) and (c)(1)(iv)) that require assessment of aggregate data. | I. INTRODUCTION | OK |
| pc-0051 | ich-e2a-step4-1994 | 4 | negation, mixed_zh_en | 按照 ICH E2A，不良事件的定义是否要求与治疗存在因果关系？ | does not necessarily have to have a causal relationship | Any untoward medical occurrence in a patient or clinical investigation subject administered a pharmaceutical product and which does not necessarily have to have a causal relationship with this treatment. | II.A.1. Adverse Event (or Adverse Experience) | OK |

| pc-0052 | ich-e2a-step4-1994 | 4 | negation, mixed_zh_en | 按照 ICH E2A，side effect 能否作为 adverse event 或 adverse reaction 的同义词？ | should not be regarded as synonymous | The old term "side effect" has been used in various ways in the past, usually to describe negative (unfavourable) effects, but also positive (favourable) effects. It is recommended that this term no longer be used and particularly should not be regarded as synonymous with adverse event or adverse reaction. | II.A.2. Adverse Drug Reaction (ADR) | OK |

| pc-0053 | ich-e2a-step4-1994 | 7 | time_window, mixed_zh_en | 按照 ICH E2A，申办方首次获知临床研究病例符合致死或危及生命的未预期不良反应快速报告条件后，最迟多久应首次通知监管机构？ | no later than 7 calendar days | Fatal or life-threatening, unexpected ADRs occurring in clinical investigations qualify for very rapid reporting. Regulatory agencies should be notified (e.g., by telephone, facsimile transmission, or in writing) as soon as possible but no later than 7 calendar days after first knowledge by the sponsor that a case qualifies, followed by as complete a report as possible within 8 additional calendar days. | III.B.1. Fatal or Life-Threatening Unexpected ADRs | OK |

| pc-0054 | ich-e2f-step4-2010 | 8 | time_window, mixed_zh_en | 按照 ICH E2F，同步 DSUR 与 PSUR 的数据锁定点时，下一份 DSUR 最多可以覆盖多长时间？ | no longer than one year | In synchronising the data lock points for the DSUR and PSUR, the period covered by the next DSUR should be no longer than one year. | 2.2 Periodicity and DSUR Data Lock Point | OK |

| pc-0055 | ich-e2f-step4-2010 | 8 | time_window, mixed_zh_en | 按照 ICH E2F，DSUR 最迟应在数据锁定点后多少个日历日内提交给监管机构？ | no later than 60 calendar days | The DSUR should be submitted to all concerned regulatory authorities no later than 60 calendar days after the DSUR data lock point. | 2.2 Periodicity and DSUR Data Lock Point | OK |

| pc-0056 | ich-e2f-step4-2010 | 6 | negation, mixed_zh_en | 按照 ICH E2F，DSUR 可以用于首次通报重大新安全信息吗？ | should not be used to provide the initial notification | All safety issues discovered during the reporting period should be discussed in the text of the DSUR; however, it should not be used to provide the initial notification of significant new safety information or provide the means by which new safety issues are detected. | 1.2 Objectives | OK |

| pc-0057 | tfda-adr-report-form-guide-4th | 15 | negation | 填寫藥品不良反應通報表時，用來治療或緩解不良反應的藥品，要填進「可疑藥品」欄位嗎？ | 不應列入可疑藥品通報 | 用以治療或緩解藥品不良反應之藥品不應列入可疑藥品通報。 | 6.1 可疑藥品（必填） | OK |

| pc-0058 | tfda-adr-report-form-guide-4th | 17 | dose_unit | 藥品不良反應通報表以 mg 或 mg/kg 填寫劑量時，指引列出的範例是什麼？ | 「10mg」、「5mg/kg」 | 請填寫通報藥品或產品之投予劑量、劑量單位，例如:「10mg」、「5mg/kg」。 | 6.10 劑量 | OK |

| pc-0059 | tfda-adr-report-form-guide-4th | 5 | mixed_zh_en | 依 TFDA《藥品不良反應通報表填寫指引》，臨床試驗中的 SUSAR 應填寫哪一份通報表？ | 「藥品臨床試驗未預期嚴重藥品不良反應通報表」 | 藥品臨床試驗未預期嚴重藥品不良反應（SUSAR）通報請填寫「藥品臨床試驗未預期嚴重藥品不良反應通報表」 | 目的 | OK |

切片计数：{'negation': 12, 'mixed_zh_en': 27, 'dose_unit': 1, 'time_window': 10, 'protocol_id': 0}；部门：{'PV': 29}；语言：{'mixed': 27, 'zh': 2}
