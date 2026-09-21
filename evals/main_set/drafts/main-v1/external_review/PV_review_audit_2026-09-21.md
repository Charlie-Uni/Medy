# PV 批次逐条审校与自审记录

审校日期：2026-09-21  
审校身份：ChatGPT／AI辅助审校，未登记为 annotator-01 人工签署。  
状态：**main-v1-provisional；第二人工复核未完成。**

## 1. 结果与输入边界

| 项目 | 结果 |
| --- | ---: |
| 输入样本 | 120 |
| 原样建议接受 | 4 |
| 更新后建议接受 | 115 |
| 建议删除 | 1 |
| 建议保留 | 119 |
| 源PDF | 32 |
| 草稿引用的不同物理页 | 110 |
| 本地定位与包含关系通过 | 119 |
| 英文问法提议（未应用） | 7 |

输入文件：`粘贴的文本 (1).txt`；SHA-256：`e390dc924d57bd4d7eb9dbe11f32db62cbaa17aa61963db3a2038a885bbfa6bb`。

字段更新条数（可重叠）：`query` 47；`key_text` 100；`evidence_span` 89；`slices` 44；`section` 91。这些数字包括全文恢复、条款重新选择和章节定位，不代表相同数量的事实错误。

输入展示截断：`key_text` 39；`evidence_span` 77；`section` 61；`tool_hint` 23。建议保留条目恢复：`key_text` 39；`evidence_span` 76；`section` 60。未取得完整原始候选JSON，不能据展示截断推断其原有末尾或错误率。

## 2. 审校口径与限制

- 本结果为ChatGPT的AI辅助审校建议，不记作annotator-01人工标注；第二人工复核未完成。自审不是独立复核。
- 未取得完整SPEC.md、samples_draft_PV.json/candidates JSON、norm-v1页文本、apply_sheet_edits.py及正式文档manifest。
- 未执行项目norm-v1逐字定位或偏移重算；未执行数据库写回、状态迁移、孪生gold/slices联动、版本冻结或主评测集全量配额检查。
- 输入中77条span、39条key、61条章节、23条工具提示有展示省略；恢复后的字段是基于实际PDF的建议值，不能据此计算原JSON错误率。
- 本地排版折叠检查的唯一性不是规范文本唯一性，也不是整个语料只有一个语义答案的证明。
- 所有关于法规、指南、产品要求的内容仅审校所供快照，不构成现行法律/临床操作建议；未使用官网最新版本覆盖上传文件。
- version_conflict按同PDF合成fixture声明处理，真实版本有效性与fixture数据库状态分开记录；源Annex I Rev4明确标注superseded。
- 不要将DROP条目标为no_answer：ms-0195文档有答案，但本题需要跨页gold。
- 英文问法只提供7条query_en_proposal，未查看EN批次，不声称这些建议已通过父子问题一致性复核。
- ms-0124的long_context标签仅按本地1504字符暂留，正式norm-v1可能改变边界；所有切片下限须实际应用后重算。

完整性按当前问题必要的条件、例外、主体、比较对象与清单判断；允许完整条款包含多句，不以“只有一句”强行切断转折。key采用保留必要语义的短连续锚点，而不是单字符唯一即可，也不是字节级全局最短的数学证明。

## 3. 切片裁定

**`protocol_id`**：本轮操作口径：问题依赖明确法规编号/条款号、表号、明确修订版或版本号时保留；仅普通模块名称、普通缩略语或编号只出现在答案不自动触发。精确标识可来自对应页标题/表头等定位上下文；并不保证在每个精简span内重复。完整SPEC/P3未取得，须项目最终对齐。

**`negation`**：按所问命题和相关证据中的禁止、否定、豁免、排除或例外判断；单纯“无资料时”的触发背景、正向要求或数字上下限不自动标注。此为AI建议口径，不宣称等同未取得的完整SPEC。

**`time_window`**：适用期限、时间间隔、日历切换界限或历史日期范围，包括one-month、three months等文字写法。保留工作日/日历日与起算点，不自行补定未写出的日类型。

**`dose_unit`**：药品剂量/给药量及其单位要求；出生体重、实验室结果浓度不能仅因出现数字+单位而标为剂量。

**`mixed_zh_en`**：按中文问题与证据中的实质英文术语判断；英文缩略语是术语，单纯计量单位不自动作为实质术语。

**`long_context`**：按用户给定span超过1500字符的规则；本轮只计算本地PDF空白折叠表示，并非项目norm-v1。ms-0124为1504字符，属阈值边缘待复算。

**`version_conflict`**：按用户提供的同PDF合成fixture声明保留；未验证数据库旧版归档/现行状态、as_of与有效期过滤，不能证明真实内容版本冲突。

建议保留样本的本地切片计数：`negation` 52；`mixed_zh_en` 117；`version_conflict` 10；`protocol_id` 43；`time_window` 34；`long_context` 6；`dose_unit` 1。这是PV子集计数，不是全量主评测集配额结果。

长条款本地长度：ms-0124=1504；ms-0134=1952；ms-0169=1678；ms-0205=2032；ms-0233=1746；ms-0249=1931。ms-0241=1147、ms-0243=772，删除long_context；ms-0195随DROP不纳入计数。

## 4. 关键问题与裁决

### PV-01 — ms-0195

Summary/Background两部分问题的Background清单在物理19页继续；第18页末不是完整列表终点。

处理：`DROP_CURRENT_SAMPLE`。

### PV-02 — ms-0292

原问已获批，原文待批；改问待批或已落实的主动申请。

处理：`EDIT_QUERY`。

### PV-03 — ms-0084, ms-0092, ms-0124, ms-0169, ms-0201, ms-0205, ms-0223, ms-0249

多要点问题不能仅用首个要点、标题或通用引导句作关键答案；补齐题目要求的必要内容。

处理：`RESELECT_KEY`。

### PV-04 — ms-0137, ms-0156, ms-0187, ms-0209, ms-0239, ms-0266

保留持续EV监测来源、When available、紧急公告例外、most、方案可另行要求、致死结局标签例外。

处理：`PRESERVE_QUALIFIERS`。

### PV-05 — ms-0197

初始评估12–24月是e.g.示例，不变为无条件硬截止；总体4年与初始示例区分。

处理：`EDIT_QUERY_AND_KEY`。

### PV-06 — ms-0108, ms-0128, ms-0177, ms-0259

风险可调周期、曾被考察的间隔、可请求提交意见、many regions均不变成强制/通常/多数。

处理：`EDIT_QUERY`。

### PV-07 — ms-0191, ms-0167

删除问题中直接泄露ENS或第105天的提示。

处理：`EDIT_QUERY`。

### PV-08 — ms-0241, ms-0243

按题目所问内容重新选完整示例条款；本地1147、772字符，不补无关段落凑1500阈值。

处理：`TRIM_AND_REMOVE_LONG_CONTEXT`。

### PV-09 — ms-0219, ms-0284, ms-0291

出生体重和检验结果单位不是药物剂量；保留原例事实。

处理：`REMOVE_DOSE_UNIT`。

### PV-10 — ms-0291

图像核对矛盾报告示例选LLT血清钾异常，不用医学常识擅改成低钾血症。

处理：`PRESERVE_ORIGINAL_LLT`。

### PV-11 — ms-0145, ms-0181, ms-0235, ms-0237, ms-0245, ms-0249, ms-0250, ms-0260

区分切换当日、URD、获知事件/新资料/FDA请求、工作日/日历日、7日加额外8日。

处理：`PRESERVE_START_AND_DAY_TYPE`。

### PV-12 — ms-0287, ms-0293, ms-0294, ms-0295

历史修改数、征求期、截至25.0的SMQ数量、当时语言计划，不表述为当前事实。

处理：`SCOPE_TO_SOURCE_EDITION`。

### PV-13 — ms-0235, ms-0237, ms-0239, ms-0241, ms-0243

2021别名实际对应2025年12月最终版PDF；要求核实manifest，不擅改主键。

处理：`KEEP_KEY_FLAG_VERSION`。

### PV-14 — ms-0084, ms-0086, ms-0088, ms-0090, ms-0092, ms-0207, ms-0209, ms-0211, ms-0213, ms-0215

同PDF两个key不证明内容冲突；Annex I Rev4已被替代提示不可抹去。

处理：`ISOLATED_FIXTURE_ONLY`。

### PV-15 — ms-0157

图像自审移除抽取后追加的相邻NCA/MAH列，保留完整Description单元格。

处理：`REMOVE_ADJACENT_COLUMN`。

### PV-16 — ms-0124

本地span1504字符，仅高于1500四字符，正式norm-v1重算前不确认长条款配额。

处理：`PENDING_CANONICAL_LENGTH`。

## 5. PDF 来源登记与自审

32份PDF封面与样本证据区域均已图像核对；119条保留建议已完成本地文字定位、页内出现次数及key包含于span检查。ms-0195另查物理19页续项。源PDF重新计算的SHA-256均与文件名及登记哈希一致。没有修改原始草稿或PDF。

下述路径为用户原登记路径，仅导航，不代表容器内存在该项目目录；实际可访问副本与完整哈希在JSON记录中。文档key映射依据上传PDF标题、版本和对应页内容，不宣称正式项目manifest验证通过。

### `ema-gvp-annex-i-rev4`

EMA GVP Annex I - Definitions (Rev 4)  
版本：EMA/876333/2011 Rev 4；9 October 2017  
PDF：`93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`  
登记路径：`/sources_staging/93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`  
物理页数：33；本批引用页：10, 17, 20, 21, 30。  
哈希：`93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe`；文件名、登记哈希与重算结果一致。

注意：源 PDF 明确标注 Superseded/not valid anymore；保留仅作为隔离的合成版本状态 fixture 内容。未核验双 document_key、归档状态、as_of/effective date；不得据此宣称现实现行法规。

### `ema-gvp-module-i`

EMA GVP Module I – Pharmacovigilance systems and their quality systems  
版本：EMA/541760/2011；22 June 2012  
PDF：`197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`  
登记路径：`/sources_staging/197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`  
物理页数：25；本批引用页：13, 14, 18, 20。  
哈希：`197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-ii-rev2`

EMA GVP Module II – Pharmacovigilance system master file (Rev 2)  
版本：EMA/816573/2011 Rev 2；28 March 2017  
PDF：`14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf`  
登记路径：`/sources_staging/14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf`  
物理页数：20；本批引用页：5, 6, 20。  
哈希：`14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-iii-rev2`

EMA GVP Module III – Pharmacovigilance inspections (Rev 2)  
版本：EMA/119871/2012 Rev 2；4 September 2026  
PDF：`d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`  
登记路径：`/sources_staging/d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`  
物理页数：19；本批引用页：3, 4, 6, 18。  
哈希：`d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64`；文件名、登记哈希与重算结果一致。

注意：所供封面记载Rev2于2026-09-04定稿、2026-09-10生效；未进行官网时效审查。

### `ema-gvp-module-iv-rev1`

EMA GVP Module IV – Pharmacovigilance audits (Rev 1)  
版本：EMA/228028/2012 Rev 1；3 August 2015  
PDF：`d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`  
登记路径：`/sources_staging/d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`  
物理页数：12；本批引用页：8, 10, 11, 12。  
哈希：`d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-ix-addendum-i`

EMA GVP Module IX Addendum I – Methodological aspects of signal detection from spontaneous reports of suspected adverse reactions  
版本：EMA/209012/2015；9 October 2017  
PDF：`7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`  
登记路径：`/sources_staging/7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`  
物理页数：10；本批引用页：3, 5, 6, 8。  
哈希：`7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-ix-rev1`

EMA GVP Module IX – Signal management (Rev 1)  
版本：EMA/827661/2011 Rev 1；9 October 2017  
PDF：`801755430dbf3ac68dfed481afc642937b9dbb3c73e38a83e8cd767dc165d1b5.pdf`  
登记路径：`/sources/801755430dbf3ac68dfed481afc642937b9dbb3c73e38a83e8cd767dc165d1b5.pdf`  
物理页数：25；本批引用页：12, 16。  
哈希：`801755430dbf3ac68dfed481afc642937b9dbb3c73e38a83e8cd767dc165d1b5`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-v-rev2`

EMA GVP Module V – Risk management systems (Rev 2)  
版本：EMA/838713/2011 Rev 2；28 March 2017  
PDF：`85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf`  
登记路径：`/sources_staging/85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf`  
物理页数：36；本批引用页：21, 29。  
哈希：`85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-vi-addendum-i`

EMA GVP Module VI Addendum I – Duplicate management of suspected adverse reaction reports  
版本：EMA/405655/2016；28 July 2017  
PDF：`4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf`  
登记路径：`/sources_staging/4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf`  
物理页数：19；本批引用页：3, 8, 18。  
哈希：`4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-vi-addendum-ii`

EMA GVP Module VI Addendum II – Masking of personal data in individual case safety reports submitted to EudraVigilance  
版本：EMA/178902/2025；22 July 2025  
PDF：`53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf`  
登记路径：`/sources_staging/53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf`  
物理页数：14；本批引用页：3, 4, 5, 6。  
哈希：`53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-vi-rev2`

EMA GVP Module VI – Collection, management and submission of reports of suspected adverse reactions to medicinal products (Rev 2)  
版本：EMA/873138/2011 Rev 2；28 July 2017  
PDF：`f27a7f0d678b17f2d6374946ae03d0b59db18217ed0fabae0b2f8a9111513b9e.pdf`  
登记路径：`/sources/f27a7f0d678b17f2d6374946ae03d0b59db18217ed0fabae0b2f8a9111513b9e.pdf`  
物理页数：144；本批引用页：15, 103。  
哈希：`f27a7f0d678b17f2d6374946ae03d0b59db18217ed0fabae0b2f8a9111513b9e`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-vii-rev1`

EMA GVP Module VII – Periodic safety update report (Rev 1)  
版本：EMA/816292/2011 Rev 1；9 December 2013  
PDF：`49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`  
登记路径：`/sources_staging/49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`  
物理页数：68；本批引用页：5, 18, 40, 53。  
哈希：`49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-viii-rev3`

EMA GVP Module VIII – Post-authorisation safety studies (Rev 3)  
版本：EMA/813938/2011 Rev 3；9 October 2017  
PDF：`847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`  
登记路径：`/sources_staging/847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`  
物理页数：28；本批引用页：11, 13, 19, 20。  
哈希：`847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-x`

EMA GVP Module X – Additional monitoring  
版本：EMA/169546/2012；19 April 2013  
PDF：`15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`  
登记路径：`/sources_staging/15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`  
物理页数：9；本批引用页：5, 6, 7, 8。  
哈希：`15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-xv-rev1`

EMA GVP Module XV – Safety communication (Rev 1)  
版本：EMA/118465/2012 Rev 1；9 October 2017  
PDF：`790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`  
登记路径：`/sources_staging/790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`  
物理页数：20；本批引用页：11, 12, 15, 16, 18。  
哈希：`790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a`；文件名、登记哈希与重算结果一致。

### `ema-gvp-module-xvi-rev3`

EMA GVP Module XVI – Risk minimisation measures (Rev 3)  
版本：EMA/204715/2012 Rev 3；26 July 2024  
PDF：`9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`  
登记路径：`/sources_staging/9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`  
物理页数：43；本批引用页：7, 11, 19, 36, 38。  
哈希：`9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b`；文件名、登记哈希与重算结果一致。

### `ema-gvp-pp-i`

EMA GVP Product- or Population-Specific Considerations I: Vaccines for prophylaxis against infectious diseases  
版本：EMA/488220/2012 Corr；9 December 2013  
PDF：`0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`  
登记路径：`/sources_staging/0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`  
物理页数：25；本批引用页：8, 11, 14, 24。  
哈希：`0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412`；文件名、登记哈希与重算结果一致。

### `ema-gvp-pp-iii`

EMA GVP Product- or Population-Specific Considerations III: Pregnant and breastfeeding women and their children exposed in utero or via breastmilk  
版本：EMA/653036/2019 corr 1；2 February 2026  
PDF：`fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`  
登记路径：`/sources_staging/fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`  
物理页数：28；本批引用页：6, 7, 9。  
哈希：`fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd`；文件名、登记哈希与重算结果一致。

注意：所供封面记载EMA/653036/2019 corr1，2026-02-02定稿、2026-02-09生效；未以旧版替换。

### `ema-gvp-pp-iv`

EMA GVP Product- or Population-Specific Considerations IV: Paediatric population  
版本：EMA/572054/2016；25 October 2018  
PDF：`e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`  
登记路径：`/sources_staging/e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`  
物理页数：17；本批引用页：4, 9, 10, 12。  
哈希：`e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4`；文件名、登记哈希与重算结果一致。

### `fda-investigator-safety-reporting-2021`

FDA Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices Guidance for Investigators, Industry, and Institutional Review Boards  
版本：December 2025  
PDF：`c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`  
登记路径：`/sources_staging/c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`  
物理页数：14；本批引用页：7, 10, 11, 12。  
哈希：`c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c`；文件名、登记哈希与重算结果一致。

注意：草稿document_key后缀2021与所供PDF封面December 2025不一致；实际核对的是2025年12月最终指南。保持原key不擅改关联，要求项目manifest核实。

### `fda-sponsor-safety-reporting-2025`

FDA Sponsor Responsibilities — Safety Reporting Requirements and Safety Assessment for IND and Bioavailability/Bioequivalence Studies Guidance for Industry  
版本：December 2025  
PDF：`7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac.pdf`  
登记路径：`/sources/7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac.pdf`  
物理页数：43；本批引用页：37, 40。  
哈希：`7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac`；文件名、登记哈希与重算结果一致。

### `ich-e2a-step4-1994`

ICH CLINICAL SAFETY DATA MANAGEMENT: DEFINITIONS AND STANDARDS FOR EXPEDITED REPORTING E2A  
版本：Current Step 4 version dated 27 October 1994  
PDF：`1c095d80419287187bf5b2db5eba83864adccebf07b9c593bf5925b4ab6f7cf7.pdf`  
登记路径：`/sources/1c095d80419287187bf5b2db5eba83864adccebf07b9c593bf5925b4ab6f7cf7.pdf`  
物理页数：12；本批引用页：7, 9。  
哈希：`1c095d80419287187bf5b2db5eba83864adccebf07b9c593bf5925b4ab6f7cf7`；文件名、登记哈希与重算结果一致。

### `ich-e2c-r2-step4-2012`

ICH PERIODIC BENEFIT-RISK EVALUATION REPORT (PBRER) E2C(R2)  
版本：Current Step 4 version dated 17 December 2012  
PDF：`0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf`  
登记路径：`/sources_staging/0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf`  
物理页数：41；本批引用页：8, 11, 13, 18。  
哈希：`0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada`；文件名、登记哈希与重算结果一致。

### `ich-e2d-step4-2003`

ICH POST-APPROVAL SAFETY DATA MANAGEMENT: DEFINITIONS AND STANDARDS FOR EXPEDITED REPORTING E2D  
版本：Current Step 4 version dated 12 November 2003  
PDF：`c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`  
登记路径：`/sources_staging/c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`  
物理页数：15；本批引用页：6, 9, 10, 14。  
哈希：`c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d`；文件名、登记哈希与重算结果一致。

### `ich-e2e-step4-2004`

ICH PHARMACOVIGILANCE PLANNING E2E  
版本：Current Step 4 version dated 18 November 2004  
PDF：`8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`  
登记路径：`/sources_staging/8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`  
物理页数：20；本批引用页：7, 9, 13, 19。  
哈希：`8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7`；文件名、登记哈希与重算结果一致。

### `ich-e2f-step4-2010`

ICH DEVELOPMENT SAFETY UPDATE REPORT E2F  
版本：Current Step 4 version dated 17 August 2010  
PDF：`7912d4d0f2b5fa407a5e8fe3908a7e8262e4034c23409cd903e3646c5b7a693b.pdf`  
登记路径：`/sources/7912d4d0f2b5fa407a5e8fe3908a7e8262e4034c23409cd903e3646c5b7a693b.pdf`  
物理页数：35；本批引用页：7, 16。  
哈希：`7912d4d0f2b5fa407a5e8fe3908a7e8262e4034c23409cd903e3646c5b7a693b`；文件名、登记哈希与重算结果一致。

### `meddra-data-retrieval-ptc-3-26-zh-hans`

MedDRA 数据检索和展示：考虑要点 / Data Retrieval and Presentation: Points to Consider  
版本：发布版本 3.26；2026 年 3 月  
PDF：`ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938.pdf`  
登记路径：`/sources/ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938.pdf`  
物理页数：49；本批引用页：8, 25。  
哈希：`ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938`；文件名、登记哈希与重算结果一致。

### `meddra-intro-guide-25-zh-hans`

MedDRA 入门指南，第 25.0 版（中文，2022 年 3 月）  
版本：第25.0版；2022年3月  
PDF：`0f49c22f2c453ce74d202cf60ddef28f9aa1291d01192945d1574252500920c1.pdf`  
登记路径：`/sources_staging/0f49c22f2c453ce74d202cf60ddef28f9aa1291d01192945d1574252500920c1.pdf`  
物理页数：62；本批引用页：15, 21, 23, 25。  
哈希：`0f49c22f2c453ce74d202cf60ddef28f9aa1291d01192945d1574252500920c1`；文件名、登记哈希与重算结果一致。

### `meddra-smq-intro-guide-25-zh-hans`

标准 MedDRA 分析查询（SMQ）入门指南，第 25.0 版（中文，2022 年 3 月）  
版本：第25.0版；2022年3月  
PDF：`ae1ef0a4b12c2c1c914f03d1bb6503f3f3a3922f0eb176cca854927556fffffb.pdf`  
登记路径：`/sources_staging/ae1ef0a4b12c2c1c914f03d1bb6503f3f3a3922f0eb176cca854927556fffffb.pdf`  
物理页数：301；本批引用页：9, 19, 50, 128。  
哈希：`ae1ef0a4b12c2c1c914f03d1bb6503f3f3a3922f0eb176cca854927556fffffb`；文件名、登记哈希与重算结果一致。

### `meddra-term-selection-ptc-4-26-zh-hans`

MedDRA 术语选择：考虑要点，发布版本 4.26（中文，2026 年 3 月）  
版本：发布版本4.26；2026年3月  
PDF：`440123f479ab3c324337ef6f731fb6ab9303576c6c21ce30043e99a6d6b1a097.pdf`  
登记路径：`/sources/440123f479ab3c324337ef6f731fb6ab9303576c6c21ce30043e99a6d6b1a097.pdf`  
物理页数：61；本批引用页：21, 35。  
哈希：`440123f479ab3c324337ef6f731fb6ab9303576c6c21ce30043e99a6d6b1a097`；文件名、登记哈希与重算结果一致。

### `meddra-whats-new-25-zh-hans`

MedDRA 更新内容，第 25.0 版（中文，2022 年 3 月）  
版本：第25.0版；2022年3月  
PDF：`5fedc7fea0158b48c7fa8d3bb21d87bff04cf4f77df089f15e2f60f80f8f3be8.pdf`  
登记路径：`/sources_staging/5fedc7fea0158b48c7fa8d3bb21d87bff04cf4f77df089f15e2f60f80f8f3be8.pdf`  
物理页数：18；本批引用页：6, 9, 10, 11。  
哈希：`5fedc7fea0158b48c7fa8d3bb21d87bff04cf4f77df089f15e2f60f80f8f3be8`；文件名、登记哈希与重算结果一致。

### `tfda-adr-report-form-guide-4th`

藥品不良反應通報表填寫指引，第四版（2025 年 3 月）  
版本：第四版；2025年3月  
PDF：`f5f597affd022ec5b57293bf47d437f2f1fadff51f15dc263cfa58f4a6134c92.pdf`  
登记路径：`/sources/f5f597affd022ec5b57293bf47d437f2f1fadff51f15dc263cfa58f4a6134c92.pdf`  
物理页数：19；本批引用页：6, 15。  
哈希：`f5f597affd022ec5b57293bf47d437f2f1fadff51f15dc263cfa58f4a6134c92`；文件名、登记哈希与重算结果一致。

注意：保留项目tfda别名；封面实际署名为全国药物不良反应通报中心／财团法人药害救济基金会，不把别名当作出版者鉴定。

## 6. 逐条记录（120条）

下面的“通过”均指AI审校建议和本地快照检查，不是人工确认或规范文本正式校验。完整before/after在JSON中；本表保留原工具提示供追踪。

### ms-0084 — 更新后建议接受

定位：`ema-gvp-annex-i-rev4`；PDF `93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第20页；Non-interventional trial; synonym: Non-interventional study。

原问题：根据 Directive 2001/20/EC Art 2(c),非介入性试验(non-interventional trial)的法定定义是什么,是否需要额外的诊断或监测程序?

建议问题：按 GVP Annex I Rev 4 所引 Directive 2001/20/EC Art 2(c)，非干预性试验（non-interventional trial）在处方、治疗分配、入组决定、额外检查和数据分析方面须满足哪些条件？

裁决理由：原 key 只回答额外检查，未覆盖所问完整定义；恢复三句定义及所有累计条件。后面的 Thus 清单为等义复述，问题限定所引法条定义段，不将该复述另算独立答案。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`negation, mixed_zh_en, version_conflict` → `negation, mixed_zh_en, version_conflict, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 559字符，span 586字符。
最终key：`A study where the medicinal product(s) is (are) prescribed in the usual manner in accordance with the terms of the marketing authorisation. The assignment of the patient to a particular therapeutic strategy is not decided in advance by a trial protocol but falls within current practice and the prescription of the medicine is clearly separated from the decision to include the patient in the study. No additional diagnostic or monitoring procedures shall be applied to the patients and epidemiological methods shall be used for the analysis of collected data`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

范围提示：源 PDF 明确标注 Superseded/not valid anymore；保留仅作为隔离的合成版本状态 fixture 内容。未核验双 document_key、归档状态、as_of/effective date；不得据此宣称现实现行法规。

### ms-0086 — 更新后建议接受

定位：`ema-gvp-annex-i-rev4`；PDF `93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第30页；Traditional herbal medicinal product。

原问题：根据 Directive 2001/83/EC Art 16c(1)(c),传统草药医药产品(traditional herbal medicinal product)认定所需的传统使用年限要求是多久?

建议问题：按 GVP Annex I Rev 4 所引 Directive 2001/83/EC Art 16c(1)(c)，传统草药药品（traditional herbal medicinal product）的传统药用年限须达到多久，其中欧盟境内须达到多久？

裁决理由：恢复总体至少30年及欧盟境内至少15年，不能将key截在within。明确法条编号在query与span均出现，机械protocol_id漏检。

更新字段：`query`, `key_text`, `evidence_span`, `slices`。
切片：`time_window, mixed_zh_en, version_conflict` → `time_window, mixed_zh_en, version_conflict, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 127字符，span 178字符。
最终key：`the product must have been in medicinal use throughout a period of at least 30 years, including at least 15 years within the EU`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

范围提示：源 PDF 明确标注 Superseded/not valid anymore；保留仅作为隔离的合成版本状态 fixture 内容。未核验双 document_key、归档状态、as_of/effective date；不得据此宣称现实现行法规。

### ms-0088 — 更新后建议接受

定位：`ema-gvp-annex-i-rev4`；PDF `93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第17页；International birth date (IBD)。

原问题：若上市许可持有人没有产品实际国际首次上市日期(IBD)的信息,应如何确定该日期?

建议问题：上市许可持有人查不到产品实际国际诞生日（IBD）时，应先查什么；若仍查不到，应如何提出日期并取得确认？

裁决理由：IBD指首次上市许可日期而非产品实际首次销售日期；完整保留先查公开日期清单、再依已知最早许可日期提议并取得监管同意两步。has no information是触发背景，不作为禁止/排除型negation。

更新字段：`query`, `key_text`, `evidence_span`, `slices`。
切片：`negation, mixed_zh_en, version_conflict` → `mixed_zh_en, version_conflict`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 427字符，span 464字符。
最终key：`If a marketing authorisation holder has no information on the actual IBD for a product, it should first refer to listings of birth dates that some regions develop and make publicly available. If the product is not included in any listing, it should propose to the regulatory authority a birth date that is based on the earliest known marketing authorisation of the substance and then obtain the regulatory authority’s agreement`。

范围提示：源 PDF 明确标注 Superseded/not valid anymore；保留仅作为隔离的合成版本状态 fixture 内容。未核验双 document_key、归档状态、as_of/effective date；不得据此宣称现实现行法规。

### ms-0090 — 更新后建议接受

定位：`ema-gvp-annex-i-rev4`；PDF `93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第21页；Occupational exposure to a medicinal product。

原问题：职业暴露(occupational exposure)于药品的定义是否涵盖生产过程中对成分的暴露?

建议问题：按 GVP Annex I 的职业暴露（occupational exposure）定义，在成品放行前的生产过程中接触药品成分，是否属于该定义的报告范围？

裁决理由：恢复before the release as finished product这一关键时间/产品状态限定；不是排除所有药品成分接触。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en, version_conflict`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 130字符，span 299字符。
最终key：`It does not include the exposure to one of the ingredients during the manufacturing process before the release as finished product`。

范围提示：源 PDF 明确标注 Superseded/not valid anymore；保留仅作为隔离的合成版本状态 fixture 内容。未核验双 document_key、归档状态、as_of/effective date；不得据此宣称现实现行法规。

### ms-0092 — 更新后建议接受

定位：`ema-gvp-annex-i-rev4`；PDF `93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第10页；Company core safety information (CCSI)。

原问题：公司核心安全性信息(CCSI)是否要求在所有销售国家保持完全一致的安全性信息内容?有无例外情形?

建议问题：按公司核心安全性信息（CCSI）的定义，核心安全性信息在各销售国的列示要求是什么，何时允许按当地要求修改？

裁决理由：原问“所有安全性信息完全一致”过宽；CCSI规定的是核心安全性信息列示及当地监管明确要求修改的例外。key补足规则本身，不仅摘例外。

更新字段：`query`, `key_text`, `evidence_span`。
切片：`negation, mixed_zh_en, version_conflict`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 322字符，span 389字符。
最终key：`all relevant safety information contained in the company core data sheet prepared by the marketing authorisation holder and which the marketing authorisation holder requires to be listed in all countries where the company markets the product, except when the local regulatory authority specifically requires a modification`。

范围提示：源 PDF 明确标注 Superseded/not valid anymore；保留仅作为隔离的合成版本状态 fixture 内容。未核验双 document_key、归档状态、as_of/effective date；不得据此宣称现实现行法规。

### ms-0094 — 更新后建议接受

定位：`ema-gvp-module-i`；PDF `197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`，物理第18页；I.C.1.4. Specific quality system processes of the marketing authorisation holder in the EU。

原问题：MAH 的药物警戒系统主档案（PSMF）最少要素，在系统正式终止后需要保留多久？

裁决理由：key补足PSMF最低要素的保留对象、系统存续期及正式终止后至少5年。该页另规定EU/国家法律要求更长时适用更长期限；本问是最低基准，不将5年解释为可销毁的上限。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 273字符，span 289字符。
最终key：`the retention of minimum elements of the pharmacovigilance system master file (PSMF) (see IR Art 2 and Module II) as long as the system described in the PSMF exists and for at least further 5 years after it has been formally terminated by the marketing authorisation holder`。

### ms-0096 — 更新后建议接受

定位：`ema-gvp-module-i`；PDF `197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`，物理第20页；I.C.2.1. Role of the competent authorities in Member States。

原问题：在互认或分散程序下，参考成员国协调与MAH沟通的安排，是否可以取代持有人对各成员国主管当局和EMA的法律责任？

裁决理由：恢复reference Member State协调安排的前文，保留MAH对个别主管机关与EMA责任不被替代。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 162字符，span 589字符。
最终key：`These arrangements do not replace the legal responsibilities of the marketing authorisation holder with respect to individual competent authorities and the Agency`。

### ms-0098 — 更新后建议接受

定位：`ema-gvp-module-i`；PDF `197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`，物理第14页；I.C.1.1. Responsibilities of the marketing authorisation holder in relation to the qualified person responsible for pharmacovigilance in the EU。

原问题：根据 IR Art 10(2)，QPPV 的职责应记录在什么文件中？

裁决理由：原句完整、对象与文件要求充分；IR Art 10(2)是query中的明确法条标识，恢复protocol_id。

更新字段：`slices`, `section`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 76字符，span 76字符。
最终key：`The duties of the QPPV shall be defined in a job description [IR Art 10(2)].`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0100 — 更新后建议接受

定位：`ema-gvp-module-i`；PDF `197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`，物理第13页；I.B.12. Monitoring of the performance and effectiveness of the pharmacovigilance system and its quality system。

原问题：根据 IR Art 13(2)，MAH 药物警戒系统质量稽核结果的报告应发送给谁？

裁决理由：补齐报告发送对象为对受审事项负责的管理层，不能止于responsible；保留原文follow-up audits措辞，不静默修正文法。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 151字符，span 248字符。
最终key：`a report shall be drawn up on the results for each quality audit and any follow-up audits be sent to the management responsible for the matters audited`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0102 — 更新后建议接受

定位：`ema-gvp-module-ii-rev2`；PDF `14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf`，物理第6页；II.B.2.2. Location, registration and maintenance。

原问题：根据 GVP Module II，MAH 在 QPPV 详细信息或 PSMF 位置发生变更后，最迟须在多长时间内更新 Article 57 数据库中的相关信息？

裁决理由：key补足变更触发点、数据库及MAH主体，并保留immediately，不改写为可等待30天。源文此处拼为PMSF，gold照录，query保留正确术语PSMF。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 188字符，span 473字符。
最终key：`Upon a change in the QPPV or location of the PMSF information, the Article 57 database shall be updated by the marketing authorisation holder immediately and no later than 30 calendar days`。

### ms-0104 — 更新后建议接受

定位：`ema-gvp-module-ii-rev2`；PDF `14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf`，物理第20页；II.C.2. Accessibility of the pharmacovigilance system master file。

原问题：MAH 在收到国家主管机关就 PSMF 提出的请求后，最迟须在多少天内提交 PSMF 副本？

裁决理由：span补入PSMF副本所指对象，key保留主体、7日及收到请求的起算点。后文共享PSMF特例也有7日，记录为相关重述，不混成另一时限。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 155字符，span 311字符。
最终key：`The marketing authorisation holder must submit the copy 7 days at the latest after receipt of the request from a national competent authority or the Agency`。

### ms-0106 — 更新后建议接受

定位：`ema-gvp-module-ii-rev2`；PDF `14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf`，物理第6页；II.B.2.1. Summary of the applicant’s pharmacovigilance system。

原问题：透过简化注册程序注册的順勢療法（homeopathic）药品，是否需要维护并提交药物警戒系统主文件（PSMF）？

建议问题：按 GVP Module II，通过简化注册程序注册的顺势疗法（homeopathic）药品，是否适用建立药物警戒系统、维护并按要求提供 PSMF，以及提交系统摘要的要求？

裁决理由：避免将按请求提供PSMF与申请时提交系统摘要混为一谈；条件限定简化注册。原query_en缺失不视为内容错误，另提供待确认译文，不创建孪生ID。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 261字符，span 278字符。
最终key：`For homeopathic medicinal products registered via the simplified registration procedure the requirements to operate a pharmacovigilance system, to maintain and make available on request a PSMF and to submit a summary of the pharmacovigilance system do not apply`。

工具提示裁定：提供query_en_proposal供人工/EN批次确认；未将其写入不存在的列，未生成孪生ID或执行联动。

英文问法提议（待确认、未应用）：Under GVP Module II, do the requirements to operate a pharmacovigilance system, maintain and make a PSMF available on request, and submit a system summary apply to homeopathic medicinal products registered through the simplified procedure?

### ms-0107 — 更新后建议接受

定位：`ema-gvp-module-ii-rev2`；PDF `14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf`，物理第5页；II.B.2.1. Summary of the applicant’s pharmacovigilance system。

原问题：传统草药制剂简化注册的申请人是否需要在上市许可申请中提交药物警戒系统摘要？

建议问题：按 GVP Module II，传统草药药品简化注册的申请人及持有人，在提交药物警戒系统摘要和建立、维护 PSMF 方面分别有什么要求？

裁决理由：保留不需提交摘要但仍须运行PV系统并建立/维护/按请求提供PSMF的转折，不外推为全面豁免。另附英文提议。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 283字符，span 310字符。
最终key：`Applicants for, and holders of simplified registrations of traditional herbal medicinal products are not required to submit a pharmacovigilance system summary, however, they are required to operate a pharmacovigilance system and prepare, maintain and make available on request a PSMF`。

工具提示裁定：提供query_en_proposal供人工/EN批次确认；未将其写入不存在的列，未生成孪生ID或执行联动。

英文问法提议（待确认、未应用）：Under GVP Module II, what requirements apply to applicants for and holders of simplified registrations of traditional herbal medicinal products regarding submission of a pharmacovigilance system summary and preparation and maintenance of a PSMF?

### ms-0108 — 更新后建议接受

定位：`ema-gvp-module-iii-rev2`；PDF `d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`，物理第18页；III.C.4.3. Inspection programmes。

原问题：对于中心化批准产品(centrally authorised products),常规药物警戒检查的标准检查周期是多长时间?

建议问题：按 GVP Module III Rev 2，对集中程序获批产品的上市许可持有人，首次常规药物警戒检查及之后的基准检查周期如何安排，能否依据持续风险评估调整？

裁决理由：恢复首次药品许可后4年内、此后4年周期以及可按持续风险评估缩短或延长，不能写成刚性的每4年必须一次。源PDF为2026-09-04 Rev2、生效2026-09-10。

更新字段：`query`, `key_text`, `evidence_span`, `slices`。
切片：`time_window, mixed_zh_en` → `time_window, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 270字符，span 390字符。
最终key：`In principle an inspection should be conducted within 4 years after the date of marketing authorisation of its first medicinal product, and thereafter a 4-years inspection cycle should be used, but this may be shortened or lengthened based on an on-going risk assessment`。

范围提示：所供封面记载Rev2于2026-09-04定稿、2026-09-10生效；未进行官网时效审查。

### ms-0110 — 更新后建议接受

定位：`ema-gvp-module-iii-rev2`；PDF `d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`，物理第6页；III.B.1.3. Pre-authorisation inspections。

原问题：上市前药物警戒检查(pre-authorisation inspection)对于新的上市许可申请是否属于强制性要求?

裁决理由：完整保留非强制但可在特定情形要求开展的对比。

更新字段：`evidence_span`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 94字符，span 170字符。
最终key：`Pre-authorisation inspections are not mandatory but may be requested in specific circumstances`。

范围提示：所供封面记载Rev2于2026-09-04定稿、2026-09-10生效；未进行官网时效审查。

### ms-0112 — 更新后建议接受

定位：`ema-gvp-module-iii-rev2`；PDF `d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`，物理第3页；III.A. Introduction。

原问题：根据IR Art 6(3),当一个已被分包的第三方将药物警戒任务进一步分包给另一第三方时,检查安排应当如何处理?

裁决理由：完整保留再次分包的触发条件及书面记录检查安排要求；编号确在query，机械漏检。

更新字段：`key_text`, `slices`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 136字符，span 157字符。
最终key：`where a subcontracted third party subcontracts (a) task(s) to another third party, inspections arrangements should be clearly documented`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

范围提示：所供封面记载Rev2于2026-09-04定稿、2026-09-10生效；未进行官网时效审查。

### ms-0114 — 更新后建议接受

定位：`ema-gvp-module-iii-rev2`；PDF `d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`，物理第4页；III.A. Introduction。

原问题：若检查结果显示上市许可持有人未遵守药物警戒义务,依据DIR Art 111(8),相关成员国应通知哪些机构?

裁决理由：完整保留违规检查结果及三个通知对象。does not comply是通知义务的触发背景，不是禁止/排除命题，删除negation；法条编号确在query。

更新字段：`key_text`, `evidence_span`, `slices`。
切片：`negation, mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 263字符，span 281字符。
最终key：`If the outcome of the inspection is that the marketing authorisation holder does not comply with the pharmacovigilance obligations, the Member State concerned shall inform the other Member States, the Agency and the European Commission in accordance with III.C.1.`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

范围提示：所供封面记载Rev2于2026-09-04定稿、2026-09-10生效；未进行官网时效审查。

### ms-0116 — 更新后建议接受

定位：`ema-gvp-module-iv-rev1`；PDF `d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第8页；IV.B.2.3.2. Reporting。

原问题：根据GVP Module IV审计发现分级标准，'major'（重大）级别的审计发现应如何定义？

裁决理由：原key只留significant weakness，遗漏第二种弱点及影响、违规但不被认为严重的限定；恢复完整分级定义。

更新字段：`key_text`, `evidence_span`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 468字符，span 469字符。
最终key：`major is a significant weakness in one or more pharmacovigilance processes or practices, or a fundamental weakness in part of one or more pharmacovigilance processes or practices that is detrimental to the whole process and/or could potentially adversely affect the rights, safety or well-being of patients and/or could potentially pose a risk to public health and/or represents a violation of applicable regulatory requirements which is however not considered serious`。

### ms-0118 — 更新后建议接受

定位：`ema-gvp-module-iv-rev1`；PDF `d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第12页；IV.C.4. Transparency。

原问题：根据GVP Module IV，欧盟委员会最迟应于何时首次公开有关欧洲药品管理局（EMA）药物警戒任务执行情况的报告？

裁决理由：区分EMA任务首报2014-01-02与成员国任务首报2015-07-21；完整句保留后续每3年，不当作新的未来截止时间。

更新字段：`key_text`, `evidence_span`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 142字符，span 375字符。
最终key：`The European Commission shall make public a report on the performance of pharmacovigilance tasks by the Agency on 2 January 2014 at the latest`。

### ms-0120 — 更新后建议接受

定位：`ema-gvp-module-iv-rev1`；PDF `d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第10页；IV.C.1.1. Requirement to perform an audit。

原问题：根据DIR Art 104(2)，欧盟上市许可持有人（MAH）对其药物警戒系统负有什么审计义务？

裁决理由：补齐包括质量系统在内的定期风险导向审计，span保留日期结果记录的紧随要求；精确法条是有效query标识。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 295字符，span 383字符。
最终key：`The marketing authorisation holder in the EU is required to perform regular risk-based audit(s) of their pharmacovigilance system [DIR Art 104(2)], including audit(s) of its quality system to ensure that the quality system complies with the quality system requirements [IR Art 8,10,11,12,13(1)].`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0122 — 更新后建议接受

定位：`ema-gvp-module-iv-rev1`；PDF `d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第11页；IV.C.1.2.3. The Pharmacovigilance Risk Assessment Committee (PRAC)。

原问题：根据REG Art 61a(6)，PRAC（药物警戒风险评估委员会）的职责范围与药物警戒审计有何关联？

裁决理由：key补足PRAC职权主体与药物风险管理职责，不留孤立having due regard短语。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 239字符，span 257字符。
最终key：`The mandate of the Pharmacovigilance Risk Assessment Committee (PRAC) shall cover all aspects of the risk management of the use of medicinal products for human use, having due regard to the design and evaluation of pharmacovigilance audits`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0124 — 更新后建议接受

定位：`ema-gvp-module-iv-rev1`；PDF `d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第8页；IV.B.2.3.2. Reporting。

原问题：根据 GVP Module IV,药物警戒审计发现(audit findings)应如何分级为 critical、major、minor 三个等级?每个等级的具体定义是什么?

裁决理由：三等级定义必须全部纳入key，不以critical开头短语代表整个答案；span只保留分级引导及三等级，不为了阈值追加后续CAPA章节。 阈值边缘：本地空白折叠文本为1504字符，仅比1500多4字符；保留标签为待norm-v1复算的建议，不据此宣布正式长条款配额通过。

更新字段：`key_text`, `evidence_span`。
切片：`negation, mixed_zh_en, long_context`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 1028字符，span 1504字符。
最终key：`critical is a fundamental weakness in one or more pharmacovigilance processes or practices that adversely affects the whole pharmacovigilance system and/or the rights, safety or well-being of patients, or that poses a potential risk to public health and/or represents a serious violation of applicable regulatory requirements. • major is a significant weakness in one or more pharmacovigilance processes or practices, or a fundamental weakness in part of one or more pharmacovigilance processes or practices that is detrimental to the whole process and/or could potentially adversely affect the rights, safety or well-being of patients and/or could potentially pose a risk to public health and/or represents a violation of applicable regulatory requirements which is however not considered serious. • minor is a weakness in the part of one or more pharmacovigilance processes or practices that is not expected to adversely affect the whole pharmacovigilance system or process and/or the rights, safety or well-being of patients.`。

范围提示：本地span1504字符，仅超阈值4字符；canonical norm-v1的long_context待复算。

### ms-0126 — 更新后建议接受

定位：`ema-gvp-module-ix-addendum-i`；PDF `7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第5页；IX. Add I.2.1.1. Considerations related to performance of signal detection systems — MedDRA hierarchy。

原问题：根据EMA GVP Module IX Addendum I,自发报告信号检测中筛查MedDRA术语时,应选用哪一级别的术语粒度以获得较好的灵敏度和阳性预测值?

建议问题：在常规自发报告统计信号检测中，GVP Module IX Addendum I 指出，哪一级 MedDRA 术语粒度在灵敏度与阳性预测值方面表现良好？

裁决理由：将“应选用”改为文献证据表述；原文has been shown不是强制唯一层级，且后文明确针对具体风险的targeted monitoring可用其他层级。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 167字符，span 169字符。
最终key：`Screening at the second finest level of granularity, i.e. Preferred Term (PT), has been shown to be a good choice in terms of sensitivity and positive predictive value`。

### ms-0128 — 更新后建议接受

定位：`ema-gvp-module-ix-addendum-i`；PDF `7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第6页；IX. Add I.2.1.1. Considerations related to performance of signal detection systems — Periodicity of monitoring。

原问题：根据GVP Module IX Addendum I,信号检测方法验证研究中通常采用多长的时间间隔来生成连续的数据汇总(data summaries)?

建议问题：GVP Module IX Addendum I 提到，信号检测方法的验证研究曾考察相邻两次数据汇总（data summaries）之间多长的间隔？

裁决理由：“has been investigated”不能译为“通常采用”或必须按月；one-month是文字书写的明确间隔，time_window保留，原正则漏检。

更新字段：`query`, `key_text`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 129字符，span 129字符。
最终key：`A one-month interval between consecutive data summaries has been investigated in validation studies for signal detection methods.`。

工具提示裁定：保留time_window：核对到原文文字形式的期限/时间界限；不能按正则未匹配认定标签错误。

### ms-0130 — 更新后建议接受

定位：`ema-gvp-module-ix-addendum-i`；PDF `7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第8页；IX. Add I.3.2. Serious events。

原问题：GVP Module IX Addendum I如何看待自发报告中不良事件的严重程度与其因果关系可能性之间的关系?

建议问题：按 GVP Module IX Addendum I，自发 ICSR 中事件的严重性（seriousness）能否直接说明该事件与药物存在因果关系的可能性？

裁决理由：将severity式“严重程度”纠正为监管概念seriousness（严重性）；key补入被比较对象，保留does not obviously relate，不夸大为绝无任何关联。

更新字段：`query`, `key_text`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 151字符，span 151字符。
最终key：`The seriousness of events described in spontaneous ICSRs does not obviously relate to the probability that they are causally related with the medicine.`。

### ms-0132 — 更新后建议接受

定位：`ema-gvp-module-ix-addendum-i`；PDF `7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第3页；IX. Add I.1. Introduction — footnote 2。

原问题：EMA GVP Module IX Addendum I所依据的Commission Implementing Regulation (EU) No 520/2012具体对应该法规的哪几条?

裁决理由：保留完整法规名称与19、23条；query的Regulation(EU)No520/2012为明确标识，非仅答案孤立编号。脚注2为该答案定位处。

更新字段：`section`。
切片：`protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 69字符，span 70字符。
最终key：`Commission Implementing Regulation (EU) No 520/2012 Article 19 and 23`。

### ms-0134 — 更新后建议接受

定位：`ema-gvp-module-ix-addendum-i`；PDF `7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第5页；IX. Add I.2.1.1. Considerations related to performance of signal detection systems — MedDRA hierarchy。

原问题：在设计自发报告的统计学信号检测系统时,针对MedDRA术语层级结构的使用(粒度层级选择、是否优先采用Preferred Term层级筛查、以及如何界定两个PT是否属于同义术语),GVP Module IX Addendum I给出了哪些具体考虑要点?

建议问题：设计常规自发报告统计信号检测系统时，GVP Module IX Addendum I 对 MedDRA 筛查层级、PT 层级的表现及适用范围，以及何时可将两个 PT 视为同义术语，有哪些考虑要点？

裁决理由：原key只覆盖PT表现；扩展至层级选择、routine而非targeted的范围及两个PT的实用同义判定。恢复完整MedDRA hierarchy条目，未跨入Thresholds。仅模块标题不单独触发protocol_id。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`protocol_id, mixed_zh_en, long_context` → `mixed_zh_en, long_context, negation`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 1595字符，span 1952字符。
最终key：`MedDRA (see GVP Annex IV), used for reporting suspected adverse reactions for regulatory purposes, provides terms for adverse events and classifies them in a multi- axial hierarchical structure and a choice must be made whether to screen at one level of granularity (e.g. SOC, HLT, PT) or several and whether to include all terms or only a subset. Screening at the second finest level of granularity, i.e. Preferred Term (PT), has been shown to be a good choice in terms of sensitivity and positive predictive value5. Finally, focus of statistical signal detection on adverse events considered clinically most important avoids time spent in assessments that are less likely to benefit patient and public health. A subset of MedDRA terms judged to be important medical events (IMEs6) is thus considered a useful tool in statistical signal detection when filtering results for medical review. The remarks above relate to routine signal detection and not to targeted monitoring of potential risks associated with specific products where ad hoc use of other levels of MedDRA terms may be appropriate. In addition, although no formally defined MedDRA term subgroups (e.g. HLT, SMQ) have proven better for signal detection than the PTs, some of them are effectively synonymous. The definition of a synonym in this context is the pragmatic one, i.e. that two PTs are considered synonyms if it is reasonable to suppose that a primary reporter of a suspected adverse reaction, presented with a single patient and without a specialist evaluation, would not necessarily be able to decide which term to use.`。

工具提示裁定：提供query_en_proposal供人工/EN批次确认；未将其写入不存在的列，未生成孪生ID或执行联动。

英文问法提议（待确认、未应用）：When designing a system for routine statistical signal detection from spontaneous reports, what considerations does GVP Module IX Addendum I give for selecting MedDRA screening levels, interpreting the performance and scope of PT-level screening, and deciding when two PTs may be treated as synonyms?

### ms-0135 — 更新后建议接受

定位：`ema-gvp-module-ix-rev1`；PDF `801755430dbf3ac68dfed481afc642937b9dbb3c73e38a83e8cd767dc165d1b5.pdf`，物理第12页；IX.C.2. Emerging safety issues。

原问题：MAH发现某信号符合emerging safety issue定义后，最迟应在多少个工作日内以书面形式通知相关成员国主管机关及EMA？

裁决理由：保留as soon as possible、3个工作日及确认满足定义的起算点；span补齐书面通知主体和接收方。原文机构邮箱仅在证据中保留，未放入query。

更新字段：`key_text`, `evidence_span`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 198字符，span 530字符。
最终key：`This should be done as soon as possible and no later than 3 working days after establishing that a validated signal or a safety issue from any source meets the definition of an emerging safety issue`。

### ms-0137 — 更新后建议接受

定位：`ema-gvp-module-ix-rev1`；PDF `801755430dbf3ac68dfed481afc642937b9dbb3c73e38a83e8cd767dc165d1b5.pdf`，物理第16页；IX.C.4.2. Inclusion of the signal in the periodic safety update report (PSUR)。

原问题：若某活性物质已列入EURD清单，且其PSUR预计在信号评估完成后6个月内提交，MAH是否仍需另外提交standalone signal notification？

建议问题：MAH 对通过持续 EudraVigilance 监测发现的信号完成评估后，若该活性物质已列入 EURD 清单，且 PSUR 在评估完成后6个月内到期提交，是否还需单独提交 standalone signal notification？

裁决理由：补入持续EudraVigilance监测来源及MAH完成评估条件，不能外推为所有来源信号；due不译成仅计划/预计提交。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`negation, time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 440字符，span 441字符。
最终key：`If an active substance is included in the List of Union Reference Dates and Frequency of Submission of Periodic Safety Update Reports (PSURs) (EURD List)16 and a PSUR is due to be submitted within 6 months of the completion, by the marketing authorisation holder, of the assessment of a signal detected through continuous EudraVigilance monitoring, the submission of a separate standalone signal notification (see IX.C.4.3.) is not required`。

### ms-0139 — 更新后建议接受

定位：`ema-gvp-module-v-rev2`；PDF `85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf`，物理第21页；V.B.6.3. RMP part III section “Summary table of additional pharmacovigilance activities”。

原问题：如果某项研究并非受EMA或国家主管当局要求进行，该研究是否应纳入RMP的药物警戒计划中？

裁决理由：span补入不影响按适用法律报告此类研究安全性问题的保留条款；不能从不纳入RMP推出无需报告安全问题。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 130字符，span 266字符。
最终key：`Studies not required by the EMA or a national competent authority should not be included in the pharmacovigilance plan in the RMP.`。

### ms-0141 — 更新后建议接受

定位：`ema-gvp-module-v-rev2`；PDF `85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf`，物理第29页；V.C.1. Requirements for the applicant/marketing authorisation holder in the EU。

原问题：根据 DIR Art 8(3)(iaa)，所有新上市许可申请人在提交申请时应随附提交什么文件？

裁决理由：key涵盖RMP及其摘要两项，不截在summary there；明确法条恢复protocol_id。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 122字符，span 179字符。
最终key：`the applicant shall submit the risk management plan describing the risk management system, together with a summary thereof`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0143 — 更新后建议接受

定位：`ema-gvp-module-v-rev2`；PDF `85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf`，物理第21页；V.B.6.3. RMP part III section “Summary table of additional pharmacovigilance activities”。

原问题：当非干预性PASS被作为上市许可条件或特定义务实施时，其监督依据是DIR哪一条款？

建议问题：非干预性 PASS 被作为上市许可条件或特定义务实施时，GVP Module V 指明其监督适用 DIR 的哪些条款？

裁决理由：答案是107m至107q的范围，不是单一条款；key保留研究性质及施加条件，完整span保留格式内容依IR Annex III。编号只在答案，不增protocol_id。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 137字符，span 258字符。
最终key：`If the condition or the specific obligation is a non-interventional PASS, it will be subject to the supervision set out in DIR Art 107m-q`。

工具提示裁定：当前query不依赖需保留的精确标识，维持无protocol_id。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0145 — 更新后建议接受

定位：`ema-gvp-module-vi-addendum-i`；PDF `4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf`，物理第18页；Table VI. Add I.4. Process description — Step 9. Send (Master) report to EDI partner。

原问题：如果一个病例在2017年11月22日之前已发送给某成员国主管机关（NCA），而其最新版本要在该日期之后发送，应将其发送给谁？

建议问题：某病例原报告在2017年11月22日前已发送给成员国主管机关（NCA），其最新版本在该日期当日或之后发送时，应送往何处，还应送给原 NCA 吗？

裁决理由：已查看表格图像；原文on or after含边界当日，query修复“之后”遗漏；保留改送EV且不送NCA的否定。固定切换日期属于time_window，原正则漏检。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`negation, time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 181字符，span 182字符。
最终key：`If the original case was sent to an NCA before 22 Nov 2017 and the latest version is to be sent on or after 22 Nov 2017, then you should send it to EudraVigilance and not to the NCA`。

工具提示裁定：保留time_window：核对到原文文字形式的期限/时间界限；不能按正则未匹配认定标签错误。

### ms-0147 — 更新后建议接受

定位：`ema-gvp-module-vi-addendum-i`；PDF `4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf`，物理第3页；VI. Add I.1. Introduction — footnote 3, Article 107(5)。

原问题：根据Directive 2001/83/EC第107(5)条，上市许可持有人（marketing authorisation holder）在检测重复的疑似不良反应报告方面应承担什么合作义务？

建议问题：GVP Module VI Addendum I 引用的 Directive 2001/83/EC 第107(5)条，要求上市许可持有人与哪些机构合作检测重复疑似不良反应报告？

裁决理由：限定脚注的法律引文，避免与正文多方协作概述混淆；key完整保留合作主体及任务。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 156字符，span 194字符。
最终key：`Marketing authorisation holders shall collaborate with the Agency and the Member States in the detection of duplicates of suspected adverse reaction reports`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0149 — 更新后建议接受

定位：`ema-gvp-module-vi-addendum-i`；PDF `4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf`，物理第8页；VI. Add I.3.2. Confirmation of duplicates cases。

原问题：在ICH-E2B(R2)报告中，如何通过'Linked reports'字段（数据字段A.1.12）来确认多个病例彼此并非重复报告？

建议问题：在 ICH-E2B(R2) 的 Linked reports 字段 A.1.12 中，应如何填写具有共同要素但彼此独立的病例，以帮助确认它们并非重复报告？

裁决理由：恢复完整首句，不把“填写字段”误当作独立的绝对判定证明；span保留与Report duplicates字段的对比以免混淆两个字段。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`negation, protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 333字符，span 608字符。
最终key：`Population of the ‘Linked reports’ section (ICH-E2B(R2) data field ‘A.1.12’)/ICH-E2B(R3) data field ‘C.1.10.r’) with the numbers of other cases that are linked by a common element or elements, but are distinct from one another, is a particularly effective method of enabling confirmation that cases are not duplicates of one another.`。

### ms-0151 — 更新后建议接受

定位：`ema-gvp-module-vi-addendum-ii`；PDF `53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf`，物理第3页；VI.Add.II.1. Introduction。

原问题：GVP Module VI Addendum II 说明书本身是为了补充 GVP Module VI 中关于数据保护法律的哪一节内容?

建议问题：GVP Module VI Addendum II 这份附录补充了主模块中关于数据保护法律的哪一节？

裁决理由：“说明书”改为附录；具体节号仅在答案，不能因文档普通模块名称标protocol_id。

更新字段：`query`, `key_text`, `evidence_span`, `slices`。
切片：`protocol_id, mixed_zh_en` → `mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 113字符，span 189字符。
最终key：`This Addendum to GVP Module VI provides instructions to complement Section VI.C.6.2.2.10. on data protection laws`。

### ms-0153 — 更新后建议接受

定位：`ema-gvp-module-vi-addendum-ii`；PDF `53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf`，物理第4页；VI.Add.II.2. Purposes of personal data processing。

原问题：根据 Commission Implementing Regulation (EU) 2022/20 第5(1)条,负责安全评估的成员国 (safety assessing Member State) 需要筛查评估哪些信息?

裁决理由：补齐全部SUSAR（不论成员国或第三国）及年度安全报告的信息；不能将key截在suspected unexpected，遗漏serious及第二信息来源。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 506字符，span 595字符。
最终key：`the safety assessing Member State shall amongst other tasks screen and assess information about all suspected unexpected serious adverse reactions reported to the EudraVigilance database in accordance with Article 42 of Regulation (EU) No 536/2014, regardless of whether they occurred in Member States or in third countries, as well as information contained in annual safety reports, in accordance with Articles 6 and 7 of the Commission Implementing Regulation (EU) 2022/20 following a risk based approach`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0155 — 更新后建议接受

定位：`ema-gvp-module-vi-addendum-ii`；PDF `53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf`，物理第5页；VI.Add.II.4. ICH-E2B(R3) data elements to be left blank。

原问题：对于 GVP Module VI Addendum II 表 VI.Add.II.2 所列的11个数据元素,发送方在向 EudraVigilance 提交 ICSR 时应如何处理这些字段?

裁决理由：11项应留空，不使用该类字段不支持的nullFlavors；与前一表13项MSK规则区分。已核查表头及上下文；query有精确表号，增加protocol_id。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`negation, mixed_zh_en` → `negation, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 208字符，span 347字符。
最终key：`Since the use of nullFlavors is not supported by the ICH E2B(R3) guideline (see Annex IV ICH-E2B(R3)), the sender of the ICSRs should leave these 11 data elements blank when submitting ICSRs to EudraVigilance`。

工具提示裁定：提供query_en_proposal供人工/EN批次确认；未将其写入不存在的列，未生成孪生ID或执行联动。

英文问法提议（待确认、未应用）：For the 11 data elements listed in Table VI.Add.II.2 of GVP Module VI Addendum II, how should a sender handle these fields when submitting an ICSR to EudraVigilance?

### ms-0156 — 更新后建议接受

定位：`ema-gvp-module-vi-addendum-ii`；PDF `53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf`，物理第6页；VI.Add.II.5. ICH-E2B(R3) data elements that may contain personal data and are required for pharmacovigilance processes。

原问题：对于 GVP Module VI Addendum II 表 VI.Add.II.3 中可能含有个人识别信息、但为信号管理和重复病例侦测所需的数据元素,发送方能否将其遮蔽或留空?

建议问题：对 GVP Module VI Addendum II 表 VI.Add.II.3 中可能含个人标识、但药物警戒处理需要的数据，发送方在已经掌握这些数据时，能否遮蔽或留空？

裁决理由：必须保留When available，不能要求补造未知个人资料。源正文or/not to语法照录，表头明确should not be masked and not be left blank，已用图像交叉核对。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`negation, mixed_zh_en` → `negation, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 141字符，span 326字符。
最终key：`When available, data related to these data elements should not be masked or not to be left blank by the senders of the ICSR to EudraVigilance`。

工具提示裁定：提供query_en_proposal供人工/EN批次确认；未将其写入不存在的列，未生成孪生ID或执行联动。

英文问法提议（待确认、未应用）：For data in Table VI.Add.II.3 of GVP Module VI Addendum II that may contain personal identifiers but are needed for pharmacovigilance processing, may the sender mask the data or leave the fields blank when the data are available?

### ms-0157 — 更新后建议接受

定位：`ema-gvp-module-vi-rev2`；PDF `f27a7f0d678b17f2d6374946ae03d0b59db18217ed0fabae0b2f8a9111513b9e.pdf`，物理第103页；Table VI.6. Process description — Step 4. Submit ICSR to EV。

原问题：在 GVP Module VI 附录中的 ICSR 提交流程（Table VI.6）里，NCA/MAH 创建一份有效 ICSR 后，应在多长时间内以规定格式提交至 EudraVigilance，而非严重的非 EEA 病例是否需要提交？

建议问题：按 GVP Module VI 的 Table VI.6 第4步，有效 ICSR 应以何种格式、在何种适用时限内提交至 EudraVigilance，非严重的非 EEA 病例如何处理？

裁决理由：原问“创建后”容易误设时限起算点，改为该表明示的适用时限；此行只写15或90日as applicable，不单靠该行强行映射或解释完整计时规则。已查看表格，保留ICSR范围、格式和排除类别。 图像自审去除抽取顺序追加在段尾的相邻Responsible Organisation列NCA/MAH；保留完整Description单元格。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`time_window, negation, mixed_zh_en` → `time_window, negation, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 249字符，span 464字符。
最终key：`Submit the ICSR (EEA and non-EEA serious, and EEA non-serious) to EudraVigilance (EV) in ICH- E2B(R2/R3) format as an XML message within the relevant time frame (15 or 90 days, as applicable). Non-serious non-EEA ICSRs should not be submitted to EV.`。

### ms-0159 — 更新后建议接受

定位：`ema-gvp-module-vi-rev2`；PDF `f27a7f0d678b17f2d6374946ae03d0b59db18217ed0fabae0b2f8a9111513b9e.pdf`，物理第15页；VI.B.2. Validation of ICSRs — criterion d。

原问题：若原始报告者明确声明疑似药品与不良事件之间不存在因果关系，且主管机关或 MAH 也认同该判断，这份报告是否构成有效 ICSR？

裁决理由：key完整保留报告者明确排除因果且接收方同意两个必要条件，避免误读为任一方否认就一定无效。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 402字符，span 403字符。
最终key：`If the primary source has made an explicit statement that a causal relationship between the medicinal product and the reported adverse event has been excluded and the notified competent authority or marketing authorisation holder agrees with this assessment, the report does not qualify as a valid ICSR since the minimum information for validation is incomplete (there is no suspected adverse reaction)`。

### ms-0161 — 更新后建议接受

定位：`ema-gvp-module-vii-rev1`；PDF `49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第5页；VII.A. Introduction — submission timelines。

原问题：EMA GVP Module VII规定,涵盖时间不超过12个月(含恰好12个月)的PSUR,应在数据锁定点后多少天内提交?

裁决理由：恢复完整时间窗，明确DLP为day0，12个月整包含在70个日历日组；不混入超过12个月及临时要求的90日规则。

更新字段：`key_text`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 142字符，span 142字符。
最终key：`within 70 calendar days of the data lock point (day 0) for PSURs covering intervals up to 12 months (including intervals of exactly 12 months)`。

### ms-0163 — 更新后建议接受

定位：`ema-gvp-module-vii-rev1`；PDF `49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第18页；VII.B.5.6.2. PSUR sub-section “Cumulative summary tabulations of serious adverse events from clinical trials”。

原问题：GVP Module VII是否允许申办方或MAH仅为撰写PSUR而对临床试验数据进行破盲?

裁决理由：补入申办者和MAH主体；禁止的是专为编写PSUR而解盲，不能推成禁止使用已经因安全原因解盲的数据。

更新字段：`key_text`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 135字符，span 135字符。
最终key：`Sponsors of clinical trials and marketing authorisation holders should not unblind data for the specific purpose of preparing the PSUR.`。

### ms-0165 — 更新后建议接受

定位：`ema-gvp-module-vii-rev1`；PDF `49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第40页；VII.C.3.3.2. Submission of PSURs for generic, well-established use, traditional herbal and homeopathic medicinal products。

原问题：根据DIR Art 107b(3),仿制药、well-established use、同源顺势及传统草药药品在哪些情形下仍需提交PSUR?

建议问题：按 GVP Module VII 所引 DIR Art 107b(3)，仿制药、已确立使用（well-established use）、顺势疗法和传统草药药品，在哪些例外情况下仍须提交 PSUR？

裁决理由：修正“同源顺势”；key补齐许可条件及主管机关基于警戒数据担忧/缺少PSUR提出要求两类例外；完整span保留第二项后续报告流转条款。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`negation, mixed_zh_en` → `negation, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 717字符，span 1080字符。
最终key：`By way of derogation, generics (authorised under DIR Art 10(1)), well-established use (authorised under DIR Art 10a), homeopathic (authorised under DIR Art 14) and traditional herbal (authorised under DIR Art 16a) medicinal products are exempted from submitting PSURs except in the following circumstances [DIR Art 107b(3)]: • the marketing authorisation provides for the submission of PSURs as a condition; • PSURs is (are) requested by a competent authority in a Member State on the basis of concerns relating to pharmacovigilance data or due to the lack of PSURs relating to an active substance after the marketing authorisation has been granted (e.g. when the “reference” medicinal product is no longer marketed).`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0167 — 更新后建议接受

定位：`ema-gvp-module-vii-rev1`；PDF `49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第53页；VII.C.4.2.2. Assessment of PSURs for medicinal products subject to different marketing authorisations containing the same active substance (EU single assessment)。

原问题：在PSUR单一评估程序中,PRAC Rapporteur/成员国收到评论后,须在多少天内完成更新评估报告(即第105天)?

建议问题：在 PSUR 单一评估程序中，PRAC 报告员或负责成员国收到评论后，应在多少天内完成更新评估报告？

裁决理由：移除query中“即第105天”的答案提示；key补齐起算点和责任主体。原文15日不自行改作工作日或日历日。

更新字段：`query`, `key_text`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 159字符，span 159字符。
最终key：`Following receipt of comments, the PRAC Rapporteur/Member State shall prepare an updated assessment report [DIR Art 107e (3)] within 15 days (i.e. by Day 105).`。

### ms-0169 — 更新后建议接受

定位：`ema-gvp-module-vii-rev1`；PDF `49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第18页；VII.B.5.6.2. PSUR sub-section “Cumulative summary tabulations of serious adverse events from clinical trials”。

原问题：在撰写PSUR VII.B.5.6.2子章节“Cumulative summary tabulations of serious adverse events from clinical trials”时,MAH在准备该临床试验严重不良事件累积汇总表(tabulation)时应考虑哪些要点?

裁决理由：generic引导句不能单独作gold命中；key覆盖全部4项：SAE非仅SAR、严重性术语范围、盲态及不得专为PSUR解盲、允许排除情况及说明。span不延入下一子节，long_context按实际长度重算。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`negation, mixed_zh_en, long_context` → `negation, mixed_zh_en, long_context, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 1633字符，span 1678字符。
最终key：`Causality assessment is generally useful for the evaluation of individual rare adverse drug reactions. Individual case causality assessment has less value in the analysis of aggregate data, where group comparisons of rates are possible. Therefore, the summary tabulations should include all serious adverse events and not just serious adverse reactions for the investigational drug, comparators and placebo. It may be useful to give rates by dose. • In general, the tabulation(s) of serious adverse events from clinical trials should include only those terms that were used in defining the case as serious and non-serious events should be included in the study reports. • The tabulations should include blinded and unblinded clinical trial data. Unblinded serious adverse events might originate from completed trials and individual cases that have been unblinded for safety-related reasons (e.g. expedited reporting), if applicable. Sponsors of clinical trials and marketing authorisation holders should not unblind data for the specific purpose of preparing the PSUR. • Certain adverse events can be excluded from the clinical trials summary tabulations, but such exclusions should be explained in the report. For example, adverse events that have been defined in the protocol as “exempt” from special collection and entry into the safety database because they are anticipated in the patient population, and those that represent study endpoints, can be excluded (e.g. deaths reported in a trial of a drug for congestive heart failure where all-cause mortality is the primary efficacy endpoint, disease progression in cancer trials).`。

### ms-0171 — 更新后建议接受

定位：`ema-gvp-module-viii-rev3`；PDF `847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`，物理第13页；VIII.B.4.3.2. Final study report。

原问题：对于依据EU主管当局强制要求开展的非干预性PASS，final study report应在数据收集结束后多长时间内提交？

建议问题：GVP Module VIII 的 VIII.B.4.3.2 对欧盟主管当局强制要求开展的非干预性 PASS，给出的最终研究报告一般提交时限是数据收集结束后多久？

裁决理由：明确所问为本节的一般时限；第20物理页另有书面waiver例外，不将12个月说成绝无豁免的期限。key保留报告对象、研究性质及起算点。

更新字段：`query`, `key_text`, `evidence_span`, `slices`。
切片：`time_window, mixed_zh_en` → `time_window, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 277字符，span 294字符。
最终key：`For non-interventional PASS conducted pursuant to an obligation imposed by an EU competent authority, the final study report shall follow the format described in this section [IR Annex III) and shall be submitted within 12 months of the end of data collection [DIR Art 107p(1)]`。

### ms-0173 — 更新后建议接受

定位：`ema-gvp-module-viii-rev3`；PDF `847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`，物理第20页；VIII.C.2.1. Roles and responsibilities of the marketing authorisation holder。

原问题：当PRAC负责监督某项non-interventional PASS时，MAH应至少提前多久向Agency书面申请final study report的waiver？

裁决理由：保留PRAC监督前提、向EMA书面请求、至少提前3个月和以报告提交到期日为基准；原正则漏检three months，time_window有效。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 219字符，span 278字符。
最终key：`When the PRAC is responsible for supervision of the PASS, the marketing authorisation holder should request the waiver in writing to the Agency at least three months before the due date for the submission of the report.`。

工具提示裁定：保留time_window：核对到原文文字形式的期限/时间界限；不能按正则未匹配认定标签错误。

### ms-0175 — 更新后建议接受

定位：`ema-gvp-module-viii-rev3`；PDF `847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`，物理第11页；VIII.B.3.1. Format and content of the study protocol — item 11。

原问题：对于基于二手数据（secondary use of data）设计的非干预性PASS，是否需要以individual case safety report（ICSR）形式报告疑似不良反应？

裁决理由：key连同二手数据研究限定，不能解读成所有非干预PASS都不报ICSR；同页明确混合设计按数据取得方式分别适用要求。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 349字符，span 349字符。
最终key：`For studies based on secondary use of data, a statement should indicate if adverse events/adverse reactions are analysed; in this instance they should be specified using the appropriate level of the MedDRA classification. The reporting of suspected adverse reactions in the form of individual case safety reports is not required (see GVP Module VI).`。

### ms-0177 — 更新后建议接受

定位：`ema-gvp-module-viii-rev3`；PDF `847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`，物理第19页；VIII.C.1.5. Written observations in response to the imposition of an obligation。

原问题：根据REG Art 10a(2)和DIR Art 22a(2)，MAH在收到强制要求的书面通知后，应在多少天内提出written observations请求？

建议问题：按 REG Art 10a(2) 和 DIR Art 22a(2)，MAH 希望针对被施加的义务陈述书面意见时，应在收到书面通知后多久内提出这一请求？

裁决理由：may request是可行使的请求权，不是必须提出意见；30日针对提出请求，主管机关另设实际提交意见期限，两者不混淆。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`time_window, mixed_zh_en` → `time_window, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 206字符，span 240字符。
最终key：`Within 30 days of receipt of the written notification of an obligation imposed, the marketing authorisation holder may request to present written observations in response to the imposition of the obligation`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0179 — 更新后建议接受

定位：`ema-gvp-module-x`；PDF `15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`，物理第5页；X.C.1.1. Mandatory scope。

原问题：根据GVP Module X强制纳入范围（Article 23(1)）,如果一款药品所含新活性成分在2011年1月1日前未曾在欧盟获批准的任何药品中出现过，是否必须列入additional monitoring list？

建议问题：按 GVP Module X 所引 Regulation (EC) No 726/2004 Article 23(1)，一款在欧盟获准的药品所含新活性物质，在2011年1月1日尚未包含于任何欧盟已批准药品中，是否属于必须纳入额外监测清单的类别？

裁决理由：原文on 1 January不能仅写该日前；补明成品已获欧盟许可，并用清单引导句保证证据明确表达“必须纳入”。

更新字段：`query`, `key_text`, `evidence_span`, `slices`。
切片：`negation, mixed_zh_en` → `negation, mixed_zh_en, protocol_id, time_window`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 320字符，span 320字符。
最终key：`According to Article 23(1) of Regulation (EC) No 726/2004 (REG), it is mandatory to include the following categories of medicinal products in the list:  medicinal products authorised in the EU that contain a new active substance which, on 1 January 2011, was not contained in any medicinal product authorised in the EU;`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0181 — 更新后建议接受

定位：`ema-gvp-module-x`；PDF `15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`，物理第6页；X.C.2.1. Mandatory scope。

原问题：对于2011年1月1日之后获批的新活性成分或生物制品，根据GVP Module X其在additional monitoring list中的初始纳入期限是多长？

建议问题：GVP Module X 对2011年1月1日后获批、含新活性物质的药品及生物药品，规定额外监测清单初始纳入期从哪个日期起算、持续多久？

裁决理由：保留five years及URD起算点，不以每个产品本国获批日代替；文字时间表达应保留time_window。

更新字段：`query`, `key_text`, `evidence_span`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 226字符，span 282字符。
最终key：`For medicinal products containing new active substances as well as for all biological medicinal products approved after 1 January 2011 the initial period of time for inclusion is five years after the Union Reference Date (URD)`。

工具提示裁定：当前query不依赖需保留的精确标识，维持无protocol_id。完整SPEC/P3需另行对齐。 保留time_window：核对到原文文字形式的期限/时间界限；不能按正则未匹配认定标签错误。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0183 — 更新后建议接受

定位：`ema-gvp-module-x`；PDF `15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`，物理第8页；X.C.4.2.1. Inclusion of medicinal products in the list — Mandatory scope。

原问题：在互认或分散上市许可程序下，成员国主管机关须在国家层面批准上市许可后多久内通知EMA以便将该产品列入additional monitoring list？

裁决理由：key补入成员国主管机关的通知动作与国家许可起算点；span保留同句提供国家网页链接要求，避免错用RMS的once authorisation granted表述。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 153字符，span 310字符。
最终key：`each national competent authority included in such procedures should inform the Agency, within 15 days of granting the marketing authorisation nationally`。

### ms-0185 — 更新后建议接受

定位：`ema-gvp-module-x`；PDF `15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`，物理第7页；X.C.3.4. The Pharmacovigilance Risk Assessment Committee (PRAC)。

原问题：根据GVP Module X, PRAC在Article 23(2) of Regulation (EC) 726/2004所述附条件药品的清单纳入问题上承担什么职责？

裁决理由：完整列示PRAC依据EC/NCA请求提出纳入建议，不能写成PRAC独自作出最终纳入决定；保留精确Article23(2)标识。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 256字符，span 256字符。
最终key：`The PRAC:  recommends, upon request of the European Commission or a national competent authority, as appropriate, if a medicinal product which is subject to conditions as set out in Article 23(2) of Regulation (EC) 726/2004 should be included in the list.`。

### ms-0187 — 更新后建议接受

定位：`ema-gvp-module-xv-rev1`；PDF `790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第11页；XV.C.1. Coordination of safety announcements in the EU。

原问题：根据GVP Module XV，在发布安全公告（safety announcement）前，成员国、EMA与欧盟委员会须提前多久互相通知，才符合DIR Art 106a(2)的要求？

建议问题：按 GVP Module XV 所引 DIR Art 106a(2)，成员国、EMA 与欧盟委员会发布安全公告前互相通知的一般提前时限是什么，何种紧急情况可例外？

裁决理由：保留至少提前24小时及保护公共卫生所需的紧急公告例外；不是任何情况下必须等待24小时。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`time_window, protocol_id, mixed_zh_en` → `time_window, protocol_id, mixed_zh_en, negation`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 250字符，span 269字符。
最终key：`Prior to the publication of a safety announcement, the Member States, the Agency or the European Commission shall inform each other not less than 24 hours in advance, unless urgent public announcements are required for the protection of public health`。

### ms-0189 — 更新后建议接受

定位：`ema-gvp-module-xv-rev1`；PDF `790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第15页；XV.C.2.1. Processing of DHPCs — core EU DHPC。

原问题：根据GVP Module XV，各成员国在对core EU DHPC进行本国化调整（national tailoring）时，是否可以与EU层面已议定的核心信息相冲突？

裁决理由：key补足EU层面已议定核心信息的指代；允许本国化但不得与核心信息冲突，不能改成禁止一切本国化。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 175字符，span 176字符。
最终key：`Although there will be national tailoring of such DHPCs, any core messages agreed at EU level should be preserved (i.e. tailoring should not conflict with these core messages)`。

### ms-0191 — 更新后建议接受

定位：`ema-gvp-module-xv-rev1`；PDF `790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第12页；XV.C.1.1. Process for exchange and coordination of safety announcements。

原问题：根据GVP Module XV，欧盟监管网络内安全公告的交流与协调应使用哪个系统（ENS）？

建议问题：按 GVP Module XV，欧盟监管网络应通过哪个系统交流和协调安全公告？

裁决理由：移除query括号中直接泄露的答案ENS；普通系统缩略语不是protocol_id，key保留具体用途与系统全称。

更新字段：`query`, `key_text`, `slices`, `section`。
切片：`protocol_id, mixed_zh_en` → `mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 145字符，span 145字符。
最终key：`The exchange and coordination of safety announcements within the EU regulatory network should make use of the EU Early Notification System (ENS).`。

### ms-0193 — 更新后建议接受

定位：`ema-gvp-module-xv-rev1`；PDF `790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第16页；XV.C.2.2. Translation and dissemination of DHPCs。

原问题：根据GVP Module XV，成员国对DHPC翻译文本进行语言审阅的期限最长不得超过多久？

裁决理由：区分指南最长合理审阅期4–5工作日和理想目标48小时；not exceed只表达数值时限上限，不重复计negation。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`time_window, negation, mixed_zh_en` → `time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 188字符，span 268字符。
最终key：`The draft translations should be submitted to the Member States for a language review and such review should be done within a reasonable timeframe which should not exceed 4-5 working days.`。

### ms-0195 — 建议删除当前样本

定位：`ema-gvp-module-xv-rev1`；PDF `790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第18页；GVP Annex II – Templates: Direct Healthcare Professional Communication — Summary and Background on the safety concern (physical pages 18–19)。

原问题：根据 GVP Module XV Annex II 的 DHPC (Direct Healthcare Professional Communication) 信件模板，正文中 Summary 部分与 Background on the safety concern 部分分别应包含哪些具体内容要素？

裁决理由：当前单页gold无法完整覆盖问题：Background on the safety concern在物理第19页仍有“Any schedule for follow-up action(s)...if applicable”续项。第18页末并非该部分结束。不能将第18页截断列表标作完整，也不把跨页拼接伪称单页连续span；建议拆为Summary单页题和支持多页gold的Background题后另行送审。

更新字段：`section`。
切片：`protocol_id, mixed_zh_en, long_context`。
部门：PV（不变）。
五项核查：问题在文档范围内，但单页完整gold不可成立；key/span不予通过；不转no_answer；需拆题或采用真正的多页gold后另审。

### ms-0197 — 更新后建议接受

定位：`ema-gvp-module-xvi-rev3`；PDF `9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第19页；XVI.B.5.2. Schedule and documentation of studies evaluating risk minimisation measures。

原问题：根据GVP Module XVI, 上市许可持有人在RMM监管实施后应在何时进行RMM有效性的初步评估和总体有效性评估？

建议问题：GVP Module XVI 对 MAH 与主管机关商定 RMM 有效性评价计划提出了哪些初步评价和总体评价时间点？

裁决理由：原key仅涵盖4年，漏初评示例12–24个月；补足两个时间点并保留should be considered和e.g.，不将初评示例变成强制硬截止。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 364字符，span 515字符。
最终key：`After regulatory implementation an initial evaluation of RMM, e.g. within 12-24 months to allow the possibility of necessary changes in healthcare; and • Within 4 years of regulatory implementation the overall effectiveness evaluation of the RMM (see XVI.B.5.3.), which, where applicable, can also inform the evaluation of the renewal of a marketing authorisation.`。

### ms-0199 — 更新后建议接受

定位：`ema-gvp-module-xvi-rev3`；PDF `9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第11页；XVI.B.1.5. Non-promotional nature of risk minimisation and personal data protection。

原问题：根据GVP Module XVI, 依据DIR Art 107m(3), 非介入性上市后安全性研究(PASS)在什么情况下不得进行？

裁决理由：补全研究行为推广药品使用这一禁止条件；保留与RMM评价不得含推广内容的完整同句。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 160字符，span 337字符。
最终key：`non-interventional post-authorisation safety studies (PASS) shall not be performed where the act of conducting the study promotes the use of a medicinal product`。

### ms-0201 — 更新后建议接受

定位：`ema-gvp-module-xvi-rev3`；PDF `9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第38页；XVI.App1.5.1. Subject to medical prescription。

原问题：根据DIR Art 71(1), GVP Module XVI中列出了哪些情况下药品须归类为处方药(subject to medical prescription)？

裁决理由：原key仅标题不能回答哪些情况；保留4个充分条件及or逻辑，不能写成四项同时满足。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 640字符，span 640字符。
最终key：`Medicinal products shall be subject to medical prescription where: • The medicinal product is likely to present a danger either directly or indirectly, even when used correctly, if utilised without medical supervision; or • The medicinal product is frequently and to a very wide extent used incorrectly, and as a result is likely to present a direct or indirect danger to human health; or • The medicinal product contains (a) substance(s) or preparations thereof, the activity and/or adverse reactions of which require further investigation; or • The medicinal product is normally prescribed to be administered parenterally [DIR Art 71(1)].`。

### ms-0203 — 更新后建议接受

定位：`ema-gvp-module-xvi-rev3`；PDF `9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第7页；XVI.A.1.3. Healthcare professionals。

原问题：根据GVP Module XVI对'healthcare professional'的定义，受雇于上市许可持有人或主管机关的具备医事资格人员是否包含在内？

裁决理由：明确仅是本GVP模块的用词范围，不否定MAH/主管机关雇员持有的医疗专业资格。

更新字段：`key_text`, `evidence_span`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 223字符，span 224字符。
最终key：`For the purpose of this GVP Module, the term ‘healthcare professional’ does not include those who are qualified as a healthcare professional but work as employees of a marketing authorisation holder or a competent authority`。

### ms-0205 — 更新后建议接受

定位：`ema-gvp-module-xvi-rev3`；PDF `9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第36页；XVI.App1.1. Summary of product characteristics。

原问题：根据GVP Module XVI，SmPC(产品特性概要)各相关章节应呈现哪些与风险最小化措施(RMM)相关的信息，如果该药品配有额外RMM材料，SmPC 4.4节又应额外说明什么？

裁决理由：以完整各节RMM信息及额外材料对应4.4节的行动、目的和范围替换空泛key；未延入boxed warning或package leaflet以凑长度。query的明确SmPC4.4节构成精确编号。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`mixed_zh_en, long_context` → `mixed_zh_en, long_context, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 1832字符，span 2032字符。
最终key：`the summary of product characteristics (SmPC) (see GVP Annex I) presents information relevant to RMM in: • SmPC section 4.8 ‘Undesirable Effects’: Information on adverse reactions, including information characterising the reaction which may be useful to prevent, monitor or manage its occurrence; • SmPC section 4.4 ‘Special Warnings and Precautions for Use’: Warnings and actions to be taken to avoid specific possible adverse reactions or to be taken if a specific reaction occurs or, if deemed necessary, actions to be taken as a precaution for potential risks; • SmPC section 4.6 ‘Fertility, Pregnancy and Lactation’: Information on risks of the medicinal product impacting on fertility, pregnancy and lactation, including risks for the embryo/foetus/child due to adverse effects at conception, in utero or through breastfeeding, and actions to be taken to avoid or minimise these risks; • SmPC sections 4.1 ‘Therapeutic Indications’, 4.2 ‘Posology and Method of Administration’, 4.3 ‘Contraindications’, 4.5 ‘Interaction with Other Medicinal Products and Other Forms of Interaction’, 4.7 ‘Effects on Ability to Drive and Use Machines’ and 4.9’ Overdose’: Safe use advice regarding indications, dosing and administration, contraindications, interactions, ability to drive and use machines, and overdose. For medicinal products with additional RMM materials, according to the Guideline on Summary of Product Characteristics26 and supplementary Guidance on Frequently Asked Questions on SmPC Section 4.427, the SmPC section 4.4. should describe the intended actions for risk minimisation and should include a statement on the educational/safety advice materials addressed to healthcare professionals or patients which clearly and succinctly explains the purpose (e.g. “to be handed out to the patient”) and scope of the materials.`。

### ms-0207 — 更新后建议接受

定位：`ema-gvp-pp-i`；PDF `0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第24页；P.I.C.2.1. Reporting of vaccination failures。

原问题：疫苗接种失败(vaccination failure)病例应在多少天内作为缺乏疗效(lack of therapeutic efficacy)病例上报?

裁决理由：补全疫苗接种失败作为缺乏疗效报告的对象及15日期限；不从此句额外推断工作日或另一个计时触发点。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en, version_conflict`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 104字符，span 385字符。
最终key：`Cases of vaccination failures should be reported as cases of lack of therapeutic efficacy within 15 days`。

范围提示：保留合成版本状态fixture标签；本轮只核验所供PDF内容及哈希，未核验两个document_key和实际归档/生效过滤配置。

### ms-0209 — 更新后建议接受

定位：`ema-gvp-pp-i`；PDF `0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第8页；P.I.B.1.2.3. RMP module SIV “Populations not studied in clinical trials” — Pregnancy。

原问题：活减毒疫苗(live attenuated vaccine)在妊娠期妇女中是否属于禁忌?

建议问题：GVP P.I 如何概括大多数活减毒疫苗（live attenuated vaccines）在妊娠期的禁忌情况及其原因？

裁决理由：原key删除most会把大多数误读为全部；补回most、妊娠人群及已知/疑似经胎盘感染风险，非一概判断每种疫苗。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en, version_conflict`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 144字符，span 448字符。
最终key：`most live attenuated vaccines are contraindicated in pregnant women due to the known or suspected risk of transplacental infection of the foetus`。

范围提示：保留合成版本状态fixture标签；本轮只核验所供PDF内容及哈希，未核验两个document_key和实际归档/生效过滤配置。

### ms-0211 — 更新后建议接受

定位：`ema-gvp-pp-i`；PDF `0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第24页；P.I.C.2. Reporting of reactions and emerging safety issues。

原问题：未伴随不良反应的疫苗接种错误(vaccination error)是否应作为个案安全性报告(ICSR)提交?

裁决理由：key原义可接受；span补入适用时PSUR考虑及影响获益风险/显著公共卫生危害时另须立即书面通知，避免不报ICSR被误读成不做任何处理。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en, version_conflict`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 123字符，span 589字符。
最终key：`Reports of vaccination errors with no associated adverse reaction should not be reported as individual case safety reports.`。

范围提示：保留合成版本状态fixture标签；本轮只核验所供PDF内容及哈希，未核验两个document_key和实际归档/生效过滤配置。

### ms-0213 — 更新后建议接受

定位：`ema-gvp-pp-i`；PDF `0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第11页；P.I.B.1.3.1. RMP section “Routine pharmacovigilance activities”。

原问题：根据GVP Module VI,RMP中常规药物警戒活动应如何处理批次相关不良反应的可追溯性?

建议问题：按 GVP P.I，疫苗 RMP 的常规药物警戒活动部分应如何描述批次相关不良反应的产品识别及制造变更可追溯性？

裁决理由：所供证据来自P.I而非Module VI正文；key需同时涵盖产品名/批号及制造变更追溯，不截在batch numbers。普通模块名不单独触发protocol_id。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`protocol_id, mixed_zh_en, version_conflict` → `mixed_zh_en, version_conflict`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 300字符，span 301字符。
最终key：`batch-related adverse reactions, including the measures taken to clearly identify the name of the product and the batch numbers involved in suspected adverse reactions (see GVP Module VI) and a description of how traceability of manufacturing changes will allow identify any related adverse reactions`。

范围提示：保留合成版本状态fixture标签；本轮只核验所供PDF内容及哈希，未核验两个document_key和实际归档/生效过滤配置。

### ms-0215 — 更新后建议接受

定位：`ema-gvp-pp-i`；PDF `0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第14页；P.I.B.3. Post-authorisation safety studies。

原问题：根据GVP Module VIII,疫苗上市后安全性研究(PASS)的目标、方法和程序应遵循什么规定?

建议问题：GVP P.I 指定疫苗上市后安全性研究（PASS）的目标、方法和程序应遵循哪个 GVP 模块？

裁决理由：原query先说“根据Module VIII”再问遵循何规定，直接暴露答案且归错证据主体；改问P.I的交叉引用，不把答案中的模块名计protocol_id。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`protocol_id, mixed_zh_en, version_conflict` → `mixed_zh_en, version_conflict`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 130字符，span 131字符。
最终key：`Objectives, methods and procedures for post-authorisation safety studies (PASS) as described in GVP Module VIII should be followed`。

范围提示：保留合成版本状态fixture标签；本轮只核验所供PDF内容及哈希，未核验两个document_key和实际归档/生效过滤配置。

### ms-0217 — 更新后建议接受

定位：`ema-gvp-pp-iii`；PDF `fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`，物理第9页；P.III.B.2. Management and reporting of suspected adverse reactions — footnote 11。

原问题：根据GVP P.III脚注引用的GVP Module VI规定，哪些妊娠相关报告不应作为ICSR提交，因为不构成疑似不良反应？

裁决理由：key补齐无畸形信息的人工终止、无结局资料的妊娠暴露、正常结局三类，原key只覆盖第三类；保留无疑似不良反应理由。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 260字符，span 261字符。
最终key：`Reports of induced termination of pregnancy without information on congenital malformation, reports of pregnancy exposure without outcome data, or reports which have a normal outcome should not be submitted as ICSRs since there is no suspected adverse reaction`。

范围提示：所供封面记载EMA/653036/2019 corr1，2026-02-02定稿、2026-02-09生效；未以旧版替换。

### ms-0219 — 更新后建议接受

定位：`ema-gvp-pp-iii`；PDF `fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`，物理第7页；P.III.A.2. Terminology — Low birth weight。

原问题：GVP P.III中，新生儿“低出生体重（low birth weight）”的定义体重界限是多少？

裁决理由：key保留术语对象及小于2500g（包含2499g）界限；这是新生儿出生体重，不是药物剂量，删除dose_unit。

更新字段：`key_text`, `slices`, `section`。
切片：`dose_unit, mixed_zh_en` → `mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 117字符，span 117字符。
最终key：`Low birth weight: Less than 2,500 grams (up to and including 2,499 g) of body weight of the neonate at time of birth.`。

范围提示：所供封面记载EMA/653036/2019 corr1，2026-02-02定稿、2026-02-09生效；未以旧版替换。

### ms-0221 — 更新后建议接受

定位：`ema-gvp-pp-iii`；PDF `fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`，物理第6页；P.III.A.2. Terminology — Miscarriage。

原问题：GVP P.III中，欧盟对流产（miscarriage）最常用定义所依据的妊娠周数界限是多少？

裁决理由：key保留最常用的EU定义及completed weeks；span补足国家/地区定义差异。取至gestation是完整主句末端，未将脚注号6并入孕周；附注需明确实际分析所用界限。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 123字符，span 342字符。
最终key：`The most recognised definition of miscarriage in the EU is a fetal death that occurs before 20 completed weeks of gestation`。

工具提示裁定：保留time_window：核对到原文文字形式的期限/时间界限；不能按正则未匹配认定标签错误。

范围提示：所供封面记载EMA/653036/2019 corr1，2026-02-02定稿、2026-02-09生效；未以旧版替换。

### ms-0223 — 更新后建议接受

定位：`ema-gvp-pp-iii`；PDF `fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`，物理第9页；P.III.B.2. Management and reporting of suspected adverse reactions — coding principles。

原问题：根据GVP P.III，母乳喂养期间用药暴露的给药途径应如何在ICH-E2B(R3)报告中编码？

建议问题：按 GVP P.III，母乳喂养造成的药物暴露在 ICH-E2B(R3) 中，应如何填写给药途径和 Reaction/event 部分的 MedDRA 术语？

裁决理由：明确问两个对应字段，key包含transmammary及Drug exposure via breast milk和所在字段，不能混成母亲本人的给药途径。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 212字符，span 244字符。
最终key：`In the case of exposure during breastfeeding, route of administration should be coded as “transmammary” and the MedDRA term “Drug exposure via breast milk” should be used in the Reaction/event ICH-E2B(R3) section`。

范围提示：所供封面记载EMA/653036/2019 corr1，2026-02-02定稿、2026-02-09生效；未以旧版替换。

### ms-0225 — 更新后建议接受

定位：`ema-gvp-pp-iv`；PDF `e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第4页；P.IV.A. Introduction。

原问题：GVP P.IV 关于儿科人群的指南章节是否会取代或在现有 GVP Module I 至 XVI 所涵盖的监管要求之外再新增要求？

裁决理由：保留配合适用、不替代、不新增监管要求；后句是针对儿科挑战的解释用途。

更新字段：`key_text`, `evidence_span`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 242字符，span 534字符。
最终key：`P.IV therefore applies in conjunction with the GVP Modules I to XVI on pharmacovigilance processes in the EU and does not replace these GVP Modules or introduce regulatory requirements in addition to those already covered in existing Modules.`。

### ms-0227 — 更新后建议接受

定位：`ema-gvp-pp-iv`；PDF `e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第9页；P.IV.B.2.1. Age information。

原问题：在儿科 ICSR 报告中，如果无法获得患儿的确切年龄或出生日期，应改为记录什么信息以替代？

裁决理由：key原先仅截取“如果无法获得”条件，漏实际答案儿科年龄亚组；补齐替代记录。保留获取不到/隐私法律限制两类条件及无任何年龄信息需随访的上下文；negation不按缺资料背景计。

更新字段：`key_text`, `evidence_span`, `slices`。
切片：`negation, mixed_zh_en` → `mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 268字符，span 660字符。
最终key：`affiliation to one of the paediatric age subsets if it is not possible to obtain the exact age or date of birth or if personal data protection legislation do not permit this in order to prevent identifying the patient, in particular when the medical condition is rare.`。

### ms-0229 — 更新后建议接受

定位：`ema-gvp-pp-iv`；PDF `e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第10页；P.IV.B.3. Periodic safety update report (PSUR)。

原问题：药品已获批儿科适应症后，在没有豁免理由的情况下，是否仍需通过 PSUR 持续监测该适应症的风险获益平衡？

裁决理由：补足生命周期持续监测义务及有理由的PSUR提交豁免，不以单独unless例外短语代表完整回答。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 254字符，span 352字符。
最终key：`When a paediatric indication has been granted, ongoing monitoring of the risk-benefit balance specifically for this indication throughout the product life-cycle should be performed (unless exempted from PSUR submission with a justification) via the PSURs`。

### ms-0231 — 更新后建议接受

定位：`ema-gvp-pp-iv`；PDF `e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第12页；P.IV.B.5. Signal management。

原问题：根据 IR 520/2012 Art 19(1)，什么样的信息可以被认定为一个‘信号’(signal)?

裁决理由：补全signal一般定义：新关联/已知关联新方面、干预与事件、有害或有益及足够可能性；query所引IR条号恢复protocol_id。后句EV监测仅考虑ADR信号，不能混成一般定义排除有益事件。

更新字段：`key_text`, `evidence_span`, `slices`。
切片：`mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 364字符，span 469字符。
最终key：`A signal is the information arising from one or multiple sources, including observations and experiments, suggesting a new potentially causal association, or a new aspect of a known association, between an intervention and an event, or set of related events, either adverse or beneficial that is judged to be of sufficient likelihood to justify verificatory action`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0233 — 更新后建议接受

定位：`ema-gvp-pp-iv`；PDF `e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第9页；P.IV.B.2.1. Age information。

原问题：在儿科不良反应个案报告（ICSR）中，除了患者年龄本身外，还应尽可能完整收集并报告哪些与年龄相关的具体信息要素？

建议问题：按 GVP P.IV 的 P.IV.B.2.1，儿科 ICSR 应怎样记录年龄或年龄亚组、处理年龄资料缺失，并在相关且可获得时补充哪些发育、父母用药暴露及出生史信息？

裁决理由：原问排除年龄本身但key只含年龄，覆盖不符；重写为完整同节记录任务，保留相关性/可能性限制及随访。不得仅凭if no信息标否定；不扩展到下一节剂型剂量等信息凑长。

更新字段：`query`, `key_text`, `evidence_span`, `slices`。
切片：`negation, mixed_zh_en, long_context` → `mixed_zh_en, long_context, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 1746字符，span 1746字符。
最终key：`As far as possible, the ICSRs should indicate either: • the age at time of onset of reaction or the date of birth, and for neonates, pre-term neonates and infants in addition the gestational age; or • affiliation to one of the paediatric age subsets if it is not possible to obtain the exact age or date of birth or if personal data protection legislation do not permit this in order to prevent identifying the patient, in particular when the medical condition is rare. If no age-related information is provided by the initial reporter, the marketing authorisation holder or the competent authority should request, as appropriate, follow-up information on age. Additionally, information on major developmental parameters like prematurity, pubertal development stage or cognitive and motor developmental milestones should be collected and reported when relevant to the suspected adverse reaction, because maturation can highly vary in children and can be clinically more important than age. Particularly in younger subjects, information on maternal and paternal exposure to medicines during conception or pregnancy as well as exposure of the neonate/infant through breastfeeding may also be of relevance since such exposure can lead to adverse reactions in the off-spring. Additionally, information on birth history as well as major developmental parameters should be collected when possible and where relevant. Maturation at that early time of life is rapidly evolving and cellular metabolism, receptor expression, receptor activity, enzymatic activity interrelate strongly with growth. Therefore, precise information on this can reveal factors leading to a different pattern in susceptibility to an adverse reaction in term or pre-term neonates.`。

### ms-0235 — 更新后建议接受

定位：`fda-investigator-safety-reporting-2021`；PDF `c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第10页；V.B. Timing of Serious Adverse Event Reporting。

原问题：对于严重不良事件(SAE)的首次报告,FDA建议研究者向申办者提交初始信息的时限一般不应超过多久?

裁决理由：保留立即报告的解释、方案中规定和一般不超过1日的推荐；不能删generally或把1日当作允许拖延时长。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 224字符，span 611字符。
最终key：`FDA recommends that this time frame for submitting such initial information also be specified in the protocol and anticipates that the time frame for submission of initial information will generally not exceed 1 calendar day`。

工具提示裁定：当前query不依赖需保留的精确标识，维持无protocol_id。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

范围提示：草稿document_key后缀2021与所供PDF封面December 2025不一致；实际核对的是2025年12月最终指南。保持原key不擅改关联，要求项目manifest核实。

范围提示：文档键带2021但实际源PDF封面及版本为December 2025，14物理页；保留键以免破坏上游联动，需维护者核对manifest别名。本轮非核验该指南现行法律效力。

### ms-0237 — 更新后建议接受

定位：`fda-investigator-safety-reporting-2021`；PDF `c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第12页；VII. Investigator reporting to sponsors and institutional review boards for IDE studies。

原问题：在IDE研究中,研究者首次获知UADE(unanticipated adverse device effect)后,最迟须在多长时间内向申办者和审查IRB提交报告?

裁决理由：key补齐向申办者和reviewing IRB的报告动作、as soon as possible及首次获知后10工作日上限，不误成日历日。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 208字符，span 227字符。
最终key：`The investigator is required to submit a report of a UADE to the sponsor and the reviewing IRB as soon as possible, but in no event later than 10 working days after the investigator first learns of the effect`。

工具提示裁定：当前query不依赖需保留的精确标识，维持无protocol_id。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

范围提示：草稿document_key后缀2021与所供PDF封面December 2025不一致；实际核对的是2025年12月最终指南。保持原key不擅改关联，要求项目manifest核实。

范围提示：文档键带2021但实际源PDF封面及版本为December 2025，14物理页；保留键以免破坏上游联动，需维护者核对manifest别名。本轮非核验该指南现行法律效力。

### ms-0239 — 更新后建议接受

定位：`fda-investigator-safety-reporting-2021`；PDF `c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第11页；V.D. Nonserious Adverse Event Reporting。

原问题：依据§ 312.64(b),研究者是否必须对非严重不良事件(nonserious adverse event)进行因果关系评估?

裁决理由：保留法条本身不要求、但方案可能要求的例外；不将not required误译为不得评估。 编辑后自审将方案例外也纳入key，防止仅命中不要求的半句。

更新字段：`key_text`, `section`。
切片：`negation, protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 155字符，span 155字符。
最终key：`The investigator is not required to assess causality of nonserious adverse events under § 312.64(b), although many sponsors may require it in the protocol.`。

范围提示：草稿document_key后缀2021与所供PDF封面December 2025不一致；实际核对的是2025年12月最终指南。保持原key不擅改关联，要求项目manifest核实。

范围提示：文档键带2021但实际源PDF封面及版本为December 2025，14物理页；保留键以免破坏上游联动，需维护者核对manifest别名。本轮非核验该指南现行法律效力。

### ms-0241 — 更新后建议接受

定位：`fda-investigator-safety-reporting-2021`；PDF `c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第7页；III.A.2. Adverse Reaction and Suspected Adverse Reaction。

原问题：依据IND安全报告法规§ 312.32(c)(1)(i)所举实例,判定药物与不良事件之间存在'合理可能性'(reasonable possibility)因果关系时可参考哪些示例情形?

裁决理由：只选本题所问三类因果关系示例及第三类紧接解释；原表span展示起点位于术语定义段，超出本题示例范围；按PDF另选所问示例，不推定未取得的原JSON终点。key不再只写illustrate。long_context按去除无关前文后的实长决定。 依本地PDF文本实长小于等于1500字符，删除long_context；项目norm-v1长度仍应重算。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`protocol_id, mixed_zh_en, long_context` → `protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 711字符，span 1147字符。
最终key：`A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure (e.g., angioedema, hepatic injury, Stevens-Johnson Syndrome). • One or more occurrences of an event that is not commonly associated with drug exposure but is otherwise uncommon in the population exposed to the drug (e.g., tendon rupture). • An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group. Examples of such events are known consequences of the underlying disease or condition or events that commonly occur in the study population independent of drug therapy.`。

范围提示：草稿document_key后缀2021与所供PDF封面December 2025不一致；实际核对的是2025年12月最终指南。保持原key不擅改关联，要求项目manifest核实。

范围提示：文档键带2021但实际源PDF封面及版本为December 2025，14物理页；保留键以免破坏上游联动，需维护者核对manifest别名。本轮非核验该指南现行法律效力。

### ms-0243 — 更新后建议接受

定位：`fda-investigator-safety-reporting-2021`；PDF `c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第12页；VI. Investigator reporting to institutional review boards for IND studies。

原问题：在IND研究中,除IND安全报告和BA/BE研究中的SAE外,哪些其他类型的事件即使不符合IND安全报告标准,仍必须作为涉及受试者风险的意外问题(unanticipated problem)报告给IRB,请举例说明?

裁决理由：key与span只覆盖题目明确所问的其他unanticipated problems及两组示例；原表span展示起点位于前面的IND安全报告/BA/BE SAE解释处，本次不纳入这些背景段，不能为了长条款标签把问题已排除的内容算入span。 依本地PDF文本实长小于等于1500字符，删除long_context；项目norm-v1长度仍应重算。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`negation, mixed_zh_en, long_context` → `negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 772字符，span 772字符。
最终key：`Certain events may not meet the criteria for reporting in an IND safety report or as a BA/BE study premarket SAE, but still must be reported to the IRB because they represent unanticipated problems involving risk to human participants or others. − Such events may occur at the participant, site, and/or study level and may include serious and unexpected adverse events that occur prior to test article administration, during a washout period, or that are attributable to a screening procedure. − Other examples may include reports of medication errors (such as receipt of wrong dose or contaminated study medication), breach of privacy/confidentiality (such as disclosure of personally identifiable information), untimely destruction of study records, and other scenarios.`。

范围提示：草稿document_key后缀2021与所供PDF封面December 2025不一致；实际核对的是2025年12月最终指南。保持原key不擅改关联，要求项目manifest核实。

范围提示：文档键带2021但实际源PDF封面及版本为December 2025，14物理页；保留键以免破坏上游联动，需维护者核对manifest别名。本轮非核验该指南现行法律效力。

### ms-0245 — 更新后建议接受

定位：`fda-sponsor-safety-reporting-2025`；PDF `7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac.pdf`，物理第37页；VIII.E. Reporting Time Frame。

原问题：根据FDA该指南,若IND临床试验中发生非预期的致命或危及生命的可疑不良反应(suspected adverse reaction),申办者最迟应在获知后多少天内向FDA报告?

建议问题：按所供 FDA《Sponsor Responsibilities》2025年12月版，非预期的致命或危及生命的可疑不良反应应最迟在申办者初次收到信息后多久向 FDA 报告？

裁决理由：恢复as soon as possible及7个日历日、初次收到信息的起算点；不以完成内部评估之日替代这一规则。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 216字符，span 234字符。
最终key：`The requirement for reporting any unexpected fatal or life-threatening suspected adverse reaction to FDA is as soon as possible but no later than 7 calendar days after the sponsor’s initial receipt of the information`。

### ms-0247 — 更新后建议接受

定位：`fda-sponsor-safety-reporting-2025`；PDF `7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac.pdf`，物理第40页；X.A. BA/BE Study Safety Reporting Requirements (§ 320.31(d)(3))。

原问题：根据FDA该指南,§320.31(d)(3)项下的BA/BE研究安全性报告要求是否适用于豁免IND要求且在美国境外进行的人体BA/BE研究?

裁决理由：span保留境外IND豁免研究不适用本项快速报告，但相应NDA/ANDA仍须包含国外研究不良事件资料的转折；不扩展为一切境外安全资料免报。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`negation, mixed_zh_en` → `negation, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 155字符，span 537字符。
最终key：`The requirements under § 320.31(d)(3) do not apply to human BA and BE studies that are exempt from IND requirements and conducted outside the United States`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0249 — 更新后建议接受

定位：`fda-sponsor-safety-reporting-2025`；PDF `7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac.pdf`，物理第40页；X.A. BA/BE Study Safety Reporting Requirements (§ 320.31(d)(3))。

原问题：根据 § 320.31(d)(3)，进行 IND 豁免的 BA/BE 研究的申办方（含合同研究机构）在 SAE 初始通知、随访报告以及 FDA 要求的补充资料提交、致死/危及生命事件额外通知等方面，完整的时限与对象要求分别是什么？

建议问题：按所供 FDA 指南 § 320.31(d)(3)，在美国开展 IND 豁免 BA/BE 研究的责任方（含合同研究机构），对 SAE 初始通知、随访报告、FDA 要求的补充资料及致死或危及生命事件额外通知，分别有哪些时限和接收对象要求？

裁决理由：补明美国境内适用范围；完整key覆盖初报15日、随访尽快且建议15日、FDA请求15日、OGD额外通知7日及其他通知对象，时钟分别为获知事件、收到新资料、收到请求。保留试验/参比药及不论相关性条件；完整条款含解盲要求。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`time_window, mixed_zh_en, long_context` → `time_window, mixed_zh_en, long_context, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 1931字符，span 1931字符。
最终key：`The person conducting an IND-exempt BA or BE study, including any contract research organization, must notify FDA and all participating investigators of any SAE observed for the test or reference drug during conduct of the study, regardless of whether the event is considered drug-related, as soon as possible but in no case later than 15 calendar days after becoming aware of its occurrence (§ 320.31(d)(3)). This includes, for example, SAEs listed in the reference listed product’s approved labeling, the investigator brochure, and the protocol. If any information necessary to evaluate the SAE is missing or unknown, the company conducting the study should actively seek such information and maintain records of efforts to obtain additional information. Any relevant additional information obtained that pertains to a previously submitted safety report must be submitted as a Follow-up Bioavailability/Bioequivalence Safety Report as soon as the information is available (§ 320.31(d)(3)) but should be submitted no later than 15 calendar days after the company receives the information. In addition, upon request from FDA, the company conducting the study must submit to FDA any additional data or information that FDA deems necessary as soon as possible but in no case later than 15 calendar days after receiving the request (e.g., hospital record, autopsy report) (§ 320.31(d)(3)). Study drug exposure for the participant who experienced the SAE should be unblinded. If the adverse event is fatal or life-threatening, the company conducting the study must also notify the Director in CDER’s Office of Generic Drugs as soon as possible but in no case later than 7 calendar days after becoming aware of its occurrence (§ 320.31(d)(3)). In doing so, the company should also notify the appropriate review division in CDER’s Office of New Drugs or the Division of Clinical Safety and Surveillance in CDER’s Office of Generic Drugs.`。

工具提示裁定：建议保留/补回protocol_id：当前query存在明确定位标识。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0250 — 更新后建议接受

定位：`ich-e2a-step4-1994`；PDF `1c095d80419287187bf5b2db5eba83864adccebf07b9c593bf5925b4ab6f7cf7.pdf`，物理第7页；III.B.1. Fatal or Life-Threatening Unexpected ADRs。

原问题：根据ICH E2A,临床试验中出现致命或危及生命的非预期ADR时,申办者最迟应在获知后多少天内通知监管机构?

建议问题：按 ICH E2A，临床试验中出现符合快速报告条件的致命或危及生命的非预期 ADR，申办者首次获知符合条件后最迟多久通知监管机构，之后多久补交尽可能完整的报告？

裁决理由：将问题扩至原key涉及的7日初报及额外8日补报两步；保留“首次获知符合条件”，不把两个期限混作同日起算。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 292字符，span 580字符。
最终key：`Regulatory agencies should be notified (e.g., by telephone, facsimile transmission, or in writing) as soon as possible but no later than 7 calendar days after first knowledge by the sponsor that a case qualifies, followed by as complete a report as possible within 8 additional calendar days.`。

### ms-0252 — 更新后建议接受

定位：`ich-e2a-step4-1994`；PDF `1c095d80419287187bf5b2db5eba83864adccebf07b9c593bf5925b4ab6f7cf7.pdf`，物理第9页；III.E.1. Reactions Associated with Active Comparator or Placebo Treatment。

原问题：根据ICH E2A,安慰剂相关的不良事件是否需要作为ADR进行快速报告?

建议问题：按 ICH E2A，安慰剂相关事件通常是否满足 ADR 及快速报告的标准？

裁决理由：保留usually这一重要非绝对限定；所供E2A此处没有进一步列举具体例外，不以外部知识补写gold。

更新字段：`query`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 120字符，span 120字符。
最终key：`Events associated with placebo will usually not satisfy the criteria for an ADR and, therefore, for expedited reporting.`。

### ms-0254 — 更新后建议接受

定位：`ich-e2c-r2-step4-2012`；PDF `0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf`，物理第13页；2.8.3. Time Interval Between Data Lock Point and the Submission。

原问题：PBRER 涵盖 6 个月或 12 个月的报告区间时，应在数据锁定点(DLP)后多少天内完成提交？

裁决理由：原key和条目完整，6或12个月70日历日成立；同节正文明确DLP为day0，未将该期限误作年度以上90日。

更新字段：`section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 68字符，span 69字符。
最终key：`PBRERs covering intervals of 6 or 12 months: within 70 calendar days`。

### ms-0256 — 更新后建议接受

定位：`ich-e2c-r2-step4-2012`；PDF `0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf`，物理第18页；3.6.2. Cumulative Summary Tabulations of Serious Adverse Events from Clinical Trials。

原问题：在准备 PBRER 时，申办方/药品上市许可持有人(MAH)是否可以为了撰写该报告而专门对临床试验数据解盲？

裁决理由：原文本Sponsor s为抽取空格变体，按所供PDF恢复；规则仅针对专为PBRER解盲，非排斥已有解盲资料。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 86字符，span 86字符。
最终key：`Sponsors/MAHs should not unblind data for the specific purpose of preparing the PBRER.`。

### ms-0258 — 更新后建议接受

定位：`ich-e2c-r2-step4-2012`；PDF `0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf`，物理第8页；1.4. Relation of the PBRER to Other ICH Documents — Modular Approach。

原问题：ICH E2C(R2) 指南的哪个附录列出了可与 DSUR(ICH E2F)或风险管理计划安全性规格(ICH E2E)共享的 PBRER 章节？

裁决理由：恢复附录D与可共享章节适用语境，ICH E2C(R2)为精确修订标识；英文仅作为待确认补充，不创建孪生。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 180字符，span 180字符。
最终key：`Appendix D of this Guideline lists the PBRER sections that can be shared with either the DSUR (ICH E2F) or safety specification of a risk management plan (ICH E2E), if appropriate.`。

工具提示裁定：提供query_en_proposal供人工/EN批次确认；未将其写入不存在的列，未生成孪生ID或执行联动。

英文问法提议（待确认、未应用）：Which appendix of ICH E2C(R2) lists the PBRER sections that can be shared, where appropriate, with the DSUR (ICH E2F) or the safety specification of a risk management plan (ICH E2E)?

### ms-0259 — 更新后建议接受

定位：`ich-e2c-r2-step4-2012`；PDF `0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf`，物理第11页；2.8.2. Managing Different Frequencies of PBRER Submission。

原问题：新获批产品在获批后至少多长时间内，多数地区要求按6个月一次的频率提交PBRER？

建议问题：ICH E2C(R2) 描述，新获批产品在许多地区适用每6个月提交一次 PBRER，这一频率至少覆盖获批后的多久？

裁决理由：many regions不是多数地区，更非全球强制统一频率；改为许多地区，保留至少前2年。

更新字段：`query`, `key_text`, `slices`, `section`。
切片：`time_window, mixed_zh_en` → `time_window, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 124字符，span 124字符。
最终key：`For newly approved products, a 6-monthly periodicity applies in many regions, for at least the first 2 years after approval.`。

工具提示裁定：提供query_en_proposal供人工/EN批次确认；未将其写入不存在的列，未生成孪生ID或执行联动。

英文问法提议（待确认、未应用）：According to ICH E2C(R2), for at least how long after approval does a six-monthly PBRER periodicity apply to newly approved products in many regions?

### ms-0260 — 更新后建议接受

定位：`ich-e2d-step4-2003`；PDF `c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`，物理第10页；4.3. Reporting Time Frames。

原问题：对于既严重又非预期的ADR，MAH自获知信息之日起最迟应在多少天内完成加速报告？

建议问题：按 ICH E2D，对已满足最低资料和快速报告标准的严重且非预期 ADR，MAH 初次收到信息后的一般最迟快速报告时限是多少？

裁决理由：补入最低资料/快速报告标准的起算限定；span保留MAH任何人员首次收件和day0，不能以PV部门最终接收日改写。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`time_window, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 188字符，span 563字符。
最终key：`In general, expedited reporting of serious and unexpected ADRs is required as soon as possible, but in no case later than 15 calendar days of initial receipt of the information by the MAH.`。

### ms-0262 — 更新后建议接受

定位：`ich-e2d-step4-2003`；PDF `c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`，物理第9页；4.1.2.2. Overdose。

原问题：根据ICH E2D，如果药物过量(overdose)但没有伴随不良结果，是否需要作为不良反应报告？

裁决理由：不作为ADR报告不等于不收集/随访；span补齐局部条款的严重ADR报告及本产品过量信息收集要求。

更新字段：`evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 99字符，span 472字符。
最终key：`Reports of overdose with no associated adverse outcome should not be reported as adverse reactions.`。

### ms-0264 — 更新后建议接受

定位：`ich-e2d-step4-2003`；PDF `c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`，物理第14页；Attachment — Recommended key data elements — 2. Suspected Medicinal Product(s)。

原问题：根据ICH E2D附件建议的关键数据要素，报告日剂量(Daily dose)时应注明哪些单位示例？

裁决理由：此处明确daily dose单位示例mg、ml、mg/kg，dose_unit适当；不额外补编具体剂量数值。

更新字段：`section`。
切片：`dose_unit, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 60字符，span 60字符。
最终key：`Daily dose (specify units - e.g., mg, ml, mg/kg) and regimen`。

### ms-0266 — 更新后建议接受

定位：`ich-e2d-step4-2003`；PDF `c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`，物理第6页；2.4. Unexpected ADR。

原问题：如果预期的ADR导致死亡(fatal outcome)，是否仍应被视为非预期(unexpected)？

建议问题：按 ICH E2D，预期 ADR 若出现致死结局，何时应按非预期处理，药品当地或区域说明书有何例外？

裁决理由：补齐unless当地/区域产品标签明确可伴致死结局的例外；不能只根据已列ADR名称推定死亡亦预期。

更新字段：`query`, `key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 185字符，span 186字符。
最终key：`An expected ADR with a fatal outcome should be considered unexpected unless the local/regional product labeling specifically states that the ADR might be associated with a fatal outcome`。

### ms-0268 — 更新后建议接受

定位：`ich-e2e-step4-2004`；PDF `8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`，物理第13页；Annex — Pharmacovigilance Methods — 1. Passive Surveillance — Systematic Methods for the Evaluation of Spontaneous Reports。

原问题：根据ICH E2E，在评估spontaneous reports时使用的data mining技术（如比例报告比）能否用来量化某药物风险的大小？

裁决理由：span补前句以明确This tool指数据挖掘；不改成可由自发报告数量推估发生风险。原key完整保留不能量化风险大小及跨药比较审慎。 编辑后自审将前句的数据挖掘主体纳入key以解除This tool指代。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 257字符，span 257字符。
最终key：`Data mining techniques facilitate the evaluation of spontaneous reports by using statistical methods to detect potential signals for further evaluation. This tool does not quantify the magnitude of risk, and caution should be exercised when comparing drugs.`。

### ms-0270 — 更新后建议接受

定位：`ich-e2e-step4-2004`；PDF `8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`，物理第7页；2. Safety Specification。

原问题：根据ICH E2E，撰写Safety Specification时，安全性问题的认定应以CTD的哪些具体章节（如Overview of Safety等）为基础？

裁决理由：完整key覆盖CTD三个章节及作为Safety Specification基础的关系；具体编号只在答案，query普通ICH E2E标记不计精确查号切片。

更新字段：`key_text`, `evidence_span`, `slices`, `section`。
切片：`protocol_id, mixed_zh_en` → `mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 317字符，span 440字符。
最终key：`The Common Technical Document (CTD), especially the Overview of Safety [2.5.5], Benefits and Risks Conclusions [2.5.6], and the Summary of Clinical Safety [2.7.4] sections, includes information relating to the safety of the product, and should be the basis of the safety issues identified in the Safety Specification.`。

### ms-0272 — 更新后建议接受

定位：`ich-e2e-step4-2004`；PDF `8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`，物理第19页；References — reference 1。

原问题：ICH E2E参考文献中，关于spontaneous report定义所引用的是哪一份ICH指南及其具体章节编号？

裁决理由：完整引用E2D全名及3.1.1，无需将文献引用内容扩作实质定义；章节号仅在答案，不增protocol_id。

更新字段：`section`。
切片：`mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 119字符，span 135字符。
最终key：`E2D: Post-approval Safety Data Management: Definitions and Standards for Expedited Reporting; 3.1.1 Spontaneous Reports`。

工具提示裁定：当前query不依赖需保留的精确标识，维持无protocol_id。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0274 — 更新后建议接受

定位：`ich-e2e-step4-2004`；PDF `8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`，物理第9页；2.1.2.f. Pharmacological Class Effects。

原问题：根据ICH E2E，Safety Specification中关于Pharmacological Class Effects的部分应说明什么内容？

裁决理由：原句直接完整回答，应列明被认为属于药理类别共同的风险；believed不能强译成已证实。

更新字段：`section`。
切片：`mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 98字符，span 98字符。
最终key：`The Safety Specification should identify risks believed to be common to the pharmacological class.`。

### ms-0276 — 更新后建议接受

定位：`ich-e2f-step4-2010`；PDF `7912d4d0f2b5fa407a5e8fe3908a7e8262e4034c23409cd903e3646c5b7a693b.pdf`，物理第16页；3.7. Data in Line Listings and Summary Tabulations。

原问题：在DSUR的严重不良事件（SAE）汇总列表（Summary Tabulations）中，是否可以纳入非严重不良事件？

裁决理由：key补足SAE汇总表对象及仅纳入用于严重性判定术语的限定；不混同SAR个案line listings。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 160字符，span 161字符。
最终key：`In general, the tabulation(s) of SAEs should include only those terms that were used in defining the case as serious; they should not include non-serious events`。

### ms-0278 — 更新后建议接受

定位：`ich-e2f-step4-2010`；PDF `7912d4d0f2b5fa407a5e8fe3908a7e8262e4034c23409cd903e3646c5b7a693b.pdf`，物理第7页；1.5. Recipients of the DSUR — footnote 7。

原问题：DSUR文件中的serious adverse reaction、serious adverse event与adverse drug reaction这些术语的定义参照的是哪份ICH指南？

裁决理由：完整恢复脚注7的三个被定义术语和E2A引文，不将表内页码/脚注号当作定义编号。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 186字符，span 200字符。
最终key：`“Serious adverse reaction,” “serious adverse event” and “adverse drug reaction” are defined in ICH E2A Clinical Safety Data Management: Definitions and Standards for Expedited Reporting.`。

工具提示裁定：当前query不依赖需保留的精确标识，维持无protocol_id。完整SPEC/P3需另行对齐。 原告警单元格已截断，仅裁定可见内容，不宣称看过候选JSON中的完整告警。

### ms-0280 — 原样建议接受

定位：`meddra-data-retrieval-ptc-3-26-zh-hans`；PDF `ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938.pdf`，物理第8页；2.3 不要改动 MedDRA。

原问题：使用 MedDRA 时,能否对术语的层级结构进行临时改动,比如变更某个 PT 的主 SOC 分配?

裁决理由：保留不得自行临时改结构/变主SOC及向MSSO提变更申请，原问答覆盖充分。

更新字段：无。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 35字符，span 122字符。
最终key：`用户不得对 MedDRA 进行临时的结构改动,包括变更主 SOC 分配`。

### ms-0281 — 原样建议接受

定位：`meddra-data-retrieval-ptc-3-26-zh-hans`；PDF `ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938.pdf`，物理第25页；4.1 引言。

原问题：从 MedDRA 23.1 版本开始,新增 SMQ 课题的专项开发工作由谁负责?

裁决理由：原句含版本23.1、COVID-19起点及MSSO与监管/业界专家合作；不混成此前CIOMS工作组继续独立负责。

更新字段：无。
切片：`protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 76字符，span 77字符。
最终key：`从 MedDRA 23.1 版的 COVID-19 (SMQ) 开始,由 MSSO 与来自监管部门和业界的专家合作,负责各个新增 SMQ 课题的专项开发`。

### ms-0282 — 更新后建议接受

定位：`meddra-intro-guide-25-zh-hans`；PDF `0f49c22f2c453ce74d202cf60ddef28f9aa1291d01192945d1574252500920c1.pdf`，物理第15页；3.5 系统器官分类（SOC）— 主SOC指定原则。

原问题：MedDRA 中,PT 耳息肉这类息肉相关术语的主 SOC 是按照肿瘤类术语的一般归类原则确定,还是依发病部位确定?

裁决理由：key补齐发病部位原则及PT耳息肉的主SOC实例，不只摘排除句。源文肿瘤主SOC句缺标点照录，不悄改原始gold。

更新字段：`key_text`, `evidence_span`, `section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 99字符，span 135字符。
最终key：`此原则不适用于囊肿和息肉相关的术语。这些术语将发病部位 SOC 作为主 SOC。例如:PT 耳息肉的主 SOC 为耳及迷路类疾病;而良性、 恶性及性质不明的肿瘤(包括囊状和息肉状)作为其次 SOC。`。

### ms-0283 — 更新后建议接受

定位：`meddra-intro-guide-25-zh-hans`；PDF `0f49c22f2c453ce74d202cf60ddef28f9aa1291d01192945d1574252500920c1.pdf`，物理第21页；4.2 缩略语。

原问题：为什么在不同 ICH 地区含义不同的缩略语或首字母缩写词不会被收入 MedDRA 术语集?

建议问题：MedDRA 对在不同 ICH 地区含义不同的缩略语或首字母缩写词设置收录限制，主要是为了避免什么问题？

裁决理由：原key漏“为什么”的原因；恢复为避免歧义。完整span保留个别多义缩写在LLT代表全球最常用含义的例外，不以“不会收录”作无条件绝对化。

更新字段：`query`, `key_text`, `evidence_span`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 65字符，span 251字符。
最终key：`为避免歧义,在不同 ICH 地区有不同含义的缩略语 (abbreviation)或首字母缩写词(acronyms)未收入本术语集。`。

### ms-0284 — 更新后建议接受

定位：`meddra-intro-guide-25-zh-hans`；PDF `0f49c22f2c453ce74d202cf60ddef28f9aa1291d01192945d1574252500920c1.pdf`，物理第23页；4.9 数值。

原问题：为什么 LLT 未特别指明的胎儿发育迟缓 这个术语中会包含 1,500-1,749 克 的具体数值,这类含临床参数数值的LLT术语通常处于什么状态?

建议问题：根据 MedDRA 入门指南，为何部分 LLT 含有具体临床参数数值，例如“未特别指明的胎儿发育迟缓，1,500-1,749克”；其中不符合 MedDRA 规则的术语如何标记？

裁决理由：补回原span漏掉的“部分”；key回答术语来源和条件性非现行状态，而非只重复例子。不把所有含数值LLT都说成非现行；胎儿体重不是药物剂量。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`dose_unit, mixed_zh_en` → `mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 43字符，span 107字符。
最终key：`通常这些术语是从其他术语集并入的,且不符合MedDRA 规则 的术语将被标为“非现行”`。

### ms-0285 — 更新后建议接受

定位：`meddra-intro-guide-25-zh-hans`；PDF `0f49c22f2c453ce74d202cf60ddef28f9aa1291d01192945d1574252500920c1.pdf`，物理第25页；5.1 常见词语用法 — 衰竭和功能不全。

原问题：在 MedDRA 中,针对心、肝、肺、肾这些主要身体系统,“衰竭(Failure)”和“功能不全(Insufficiency)”这两个概念在 PT 和 LLT 层级如何分别使用?

裁决理由：恢复完整段落，保留特定心肝肺肾系统及通常PT/LLT层级，不扩大到任意器官或临床术语完全同义。

更新字段：`evidence_span`, `section`。
切片：`mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 34字符，span 205字符。
最终key：`“衰竭”通常用于 PT 层级术语,“功能不全”用于 LLT 层级术语`。

### ms-0286 — 更新后建议接受

定位：`meddra-smq-intro-guide-25-zh-hans`；PDF `ae1ef0a4b12c2c1c914f03d1bb6503f3f3a3922f0eb176cca854927556fffffb.pdf`，物理第9页；致读者 — 对SMQ的机构修改。

原问题：如果某机构对某个 SMQ 的术语内容或结构做了修改,这个修改后的工具还能否继续被称为“SMQ”?

裁决理由：原句完整且给出修改后的正确称呼；不需要将其改成允许继续使用SMQ名称。

更新字段：`section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 64字符，span 74字符。
最终key：`对 SMQ 的术语内容或结构作出任何修改,则不能再称其为“SMQ”,而应该称其为“根据 SMQ 修改的 MedDRA 分析查询”`。

### ms-0287 — 更新后建议接受

定位：`meddra-smq-intro-guide-25-zh-hans`；PDF `ae1ef0a4b12c2c1c914f03d1bb6503f3f3a3922f0eb176cca854927556fffffb.pdf`，物理第19页；2.2.2 纳入/排除标准 — 第18.0版重新测试说明。

原问题：MedDRA 第 18.0 版对急性呼吸中枢抑制 (SMQ) 的术语修改共涉及多少项?

裁决理由：28项是18.0版急性呼吸中枢抑制SMQ术语修改数，不是全部SMQ数量；版本标识匹配正确。

更新字段：`section`。
切片：`protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 45字符，span 52字符。
最终key：`MedDRA 第 18.0 版纳入了急性呼吸中枢抑制 (SMQ) 的 28 项术语修改内容`。

### ms-0288 — 更新后建议接受

定位：`meddra-smq-intro-guide-25-zh-hans`；PDF `ae1ef0a4b12c2c1c914f03d1bb6503f3f3a3922f0eb176cca854927556fffffb.pdf`，物理第50页；2.16.3 层级结构。

原问题：出血性或缺血性性质不明的中枢神经系统血管疾病 (SMQ) 能不能单独作为一个独立的 SMQ 使用?

裁决理由：已查看原页，两个相似下级SMQ都有非独立表述；所选key完整命名目标并保留上级脑血管障碍SMQ。

更新字段：`section`。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 71字符，span 72字符。
最终key：`出血性或缺血性性质不明的中枢神经系统血管疾病 (SMQ)不是一个独立的 SMQ 主题。它只能与上级 SMQ 主题脑血管障碍 (SMQ)配合使用`。

### ms-0289 — 原样建议接受

定位：`meddra-smq-intro-guide-25-zh-hans`；PDF `ae1ef0a4b12c2c1c914f03d1bb6503f3f3a3922f0eb176cca854927556fffffb.pdf`，物理第128页；2.44.4 执行注意事项和查询结果预期。

原问题：仅使用下级 SMQ 肝部感染 (SMQ) 检索,能否获得全部“肝部感染”相关病例?

裁决理由：完整span同时保留辅助检查结果来源；不能把单独肝部感染SMQ检索结果当作完整病例集。

更新字段：无。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 30字符，span 124字符。
最终key：`通过下级 SMQ 肝部感染 (SMQ) 检索到的结果并不完全`。

工具提示裁定：保留negation：原文存在实际否定/限制（并不完全、没有待批或已落实），原告警为词形漏检。

### ms-0290 — 原样建议接受

定位：`meddra-term-selection-ptc-4-26-zh-hans`；PDF `440123f479ab3c324337ef6f731fb6ab9303576c6c21ce30043e99a6d6b1a097.pdf`，物理第35页；3.14.5 不带限定词的检查结果。

原问题：SOC「各类检查」下不带限定词的检查名称术语（例如LLT 血葡萄糖）可以用来编码不良反应或病史等其他数据区域吗？

裁决理由：原句禁止跨数据区域用不带限定词检查名编码，范围清楚；不把检查名称编码等同检查结果编码。

更新字段：无。
切片：`negation, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 41字符，span 42字符。
最终key：`不带限定词的检查名称术语不应用于编码其他数据区域的信息(如 AR/AE 和病史等)`。

### ms-0291 — 更新后建议接受

定位：`meddra-term-selection-ptc-4-26-zh-hans`；PDF `440123f479ab3c324337ef6f731fb6ab9303576c6c21ce30043e99a6d6b1a097.pdf`，物理第21页；3.4.1 矛盾的信息 — 示例表。

原问题：报告中同时出现“高钾血症”诊断与偏低的血清钾检验值（1.6 mEq/L）这类矛盾信息时，应选择哪个MedDRA LLT进行编码？

建议问题：按《MedDRA 术语选择：考虑要点》3.4.1的示例，报告同时写有“高钾血症”和“血清钾1.6 mEq/L”时，表中选择哪个 LLT 来涵盖这两个矛盾概念？

裁决理由：已用表格图像核对报告信息、选取LLT和备注三列；答案血清钾异常，不按单一数值擅改为低钾血症。mEq/L是检验结果单位，不是药物剂量。

更新字段：`query`, `key_text`, `evidence_span`, `slices`, `section`。
切片：`dose_unit, mixed_zh_en` → `mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 24字符，span 82字符。
最终key：`高钾血症,血清钾1.6 mEq /L 血清钾异常`。

### ms-0292 — 更新后建议接受

定位：`meddra-whats-new-25-zh-hans`；PDF `5fedc7fea0158b48c7fa8d3bb21d87bff04cf4f77df089f15e2f60f80f8f3be8.pdf`，物理第10页；3.3 主动申请。

原问题：MedDRA第25.0版变更申请处理期间是否有已获批或已落实的主动申请?

建议问题：MedDRA 第25.0版变更申请处理期间，是否有待批或已落实的主动申请？

裁决理由：关键事实错误：原文是“待批”不是query的“已获批”；修复后方可回答否定。版本数字是明确查版本标识。

更新字段：`query`, `key_text`, `slices`。
切片：`negation, mixed_zh_en` → `negation, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 31字符，span 32字符。
最终key：`在第 25.0 版变更申请处理期间,没有待批或已落实的主动申请`。

工具提示裁定：保留negation：原文存在实际否定/限制（并不完全、没有待批或已落实），原告警为词形漏检。

### ms-0293 — 更新后建议接受

定位：`meddra-whats-new-25-zh-hans`；PDF `5fedc7fea0158b48c7fa8d3bb21d87bff04cf4f77df089f15e2f60f80f8f3be8.pdf`，物理第6页；2.2 复杂变更。

原问题：MedDRA复杂变更提议在网站上公布、供用户提供反馈意见的具体起止日期是什么?

建议问题：《MedDRA 第25.0版更新内容》记载，针对该版复杂变更提议，用户反馈意见的起止日期是什么？

裁决理由：补明第25.0版历史征求反馈范围，不能写成MedDRA所有复杂变更的通用/当前征求期；保留起止两日期。

更新字段：`query`, `key_text`, `slices`。
切片：`time_window, mixed_zh_en` → `time_window, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 78字符，span 78字符。
最终key：`复杂变更提议曾在 MedDRA 网站上公布,供 MedDRA 广大用户在 2021 年 7 月 29 日至 2021 年 9 月 24 日期间提供反馈意见。`。

### ms-0294 — 更新后建议接受

定位：`meddra-whats-new-25-zh-hans`；PDF `5fedc7fea0158b48c7fa8d3bb21d87bff04cf4f77df089f15e2f60f80f8f3be8.pdf`，物理第9页；3.2 标准MedDRA分析查询（SMQ）。

原问题：截至MedDRA第25.0版,已有多少个一级SMQ正式使用?

裁决理由：保留“截至本版”及query第25.0版，110是历史版本一级SMQ数，不宣称现在总数。

更新字段：`section`。
切片：`protocol_id, mixed_zh_en`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 19字符，span 25字符。
最终key：`已有 110 个一级 SMQ 正式使用`。

### ms-0295 — 更新后建议接受

定位：`meddra-whats-new-25-zh-hans`；PDF `5fedc7fea0158b48c7fa8d3bb21d87bff04cf4f77df089f15e2f60f80f8f3be8.pdf`，物理第11页；3.5 正在开发中的新MedDRA语言。

原问题：MedDRA计划中,希腊语、拉脱维亚语、马耳他语、波兰语和瑞典语的翻译预计何时完成?

建议问题：《MedDRA 第25.0版更新内容》当时预计，希腊语、拉脱维亚语、马耳他语、波兰语和瑞典语的翻译何时完成？

裁决理由：明确是2022年文档当时的预测，不证明实际按期完成，也不作为2026年未来计划；key补齐五种语言以区别后面其他语言计划。

更新字段：`query`, `key_text`, `slices`, `section`。
切片：`time_window, mixed_zh_en` → `time_window, mixed_zh_en, protocol_id`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 54字符，span 54字符。
最终key：`目前正在开发中的语言有希腊语、拉脱维亚语、马耳他语、波兰语和瑞典语的翻译,预计将于 2022 年上半年完成。`。

### ms-0296 — 更新后建议接受

定位：`tfda-adr-report-form-guide-4th`；PDF `f5f597affd022ec5b57293bf47d437f2f1fadff51f15dc263cfa58f4a6134c92.pdf`，物理第15页；6.1 可疑藥品（必填）。

原问题：藥品不良反應通報表中,用以治療或緩解本次不良反應症狀的藥品,是否應列為「可疑藥品」通報?

裁决理由：繁体问题及单句gold完整；本次不良反应的治疗/缓解用药不可误作可疑药品。

更新字段：`section`。
切片：`negation`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 26字符，span 27字符。
最终key：`用以治療或緩解藥品不良反應之藥品不應列入可疑藥品通報`。

范围提示：保留项目tfda别名；封面实际署名为全国药物不良反应通报中心／财团法人药害救济基金会，不把别名当作出版者鉴定。

### ms-0297 — 更新后建议接受

定位：`tfda-adr-report-form-guide-4th`；PDF `f5f597affd022ec5b57293bf47d437f2f1fadff51f15dc263cfa58f4a6134c92.pdf`，物理第6页；通則。

原问题：通報藥品不良反應時,是否需要先確定藥品與不良反應之間的因果關係才能通報?

裁决理由：key补足至少合理可能性即足够的下限，不能只保留无需确定因果而误成毫无合理关联亦同样构成理由。

更新字段：`key_text`。
切片：`negation`。
部门：PV（不变）。
五项核查：问题按修改后意图可回答；key本地页内出现1次；完整span出现1次，key包含于span；切片按本轮口径暂定；部门PV。key 77字符，span 78字符。
最终key：`通報藥品不良反應並不需要確定藥品與不良反應間的因果關係,若藥品和事件之間的因果關係至少存在合理的可能性(意即不能排除兩者之間的關係),即足以構成通報的理由`。

范围提示：保留项目tfda别名；封面实际署名为全国药物不良反应通报中心／财团法人药害救济基金会，不把别名当作出版者鉴定。

## 7. 应用前检查

人工确认本表后，使用项目实际apply工具重定位所有改变的key/span、重算norm-v1偏移与出现次数，复算long_context（特别是ms-0124），再对照正式SPEC/P3确认标识符切片。重新检查父样本和英文孪生的gold/slices一致性；处理ms-0195的删除是否需联动。核实FDA 2021别名的2025版本映射，并确认合成fixture的as_of、状态和有效期不与PDF真实历史状态混用。最后重跑主评测集全量数量、每文档非派生上限和九类切片下限。

本轮没有执行上述项目写操作，也不创建不存在的英文孪生、偏移或人工复核人。

来源原文归EMA/HMA、ICH/MedDRA及相应发布机构所有；改写问法和审校建议不表示获得任何来源机构认可。
