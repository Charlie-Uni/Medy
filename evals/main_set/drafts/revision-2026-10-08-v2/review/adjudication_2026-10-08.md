# 19 题复核结果与已执行裁决

日期：2026-10-08。模型实际回显 `claude-opus-5`，请求 effort=high；19 次独立会话、每次 1 题。**19/19 完成，15 同意、4 争议；4 条争议归为 3 个决定。** 模型意见不是人工签字；下表建议尚未应用，第二独立人工仍 pending，数据集未冻结。

CLI 原始美元估算合计约 **2.91752125 USD**；逐次向上取整后的账本合计 **2.917528 USD**，5 USD 授权内剩余 **2.082472 USD**。没有失败、自动重试或未知费用。当前为 Claude 订阅登录，这些数字不等同于新增信用卡扣款。

## 2026-10-08 项目所有者裁决与执行

项目所有者回复“**三项按建议裁决，允许 EVAL-08 最多 0.75 USD**”。三项已写入 [v3 修订](../../revision-2026-10-08-v3/README.md)：`ms-0125` 保留 2226；`ms-0241/0242` 改为三个正式示例共同必需、standard-of-care 仅作背景；`ms-0280` 增加 `protocol_id`。新输入、映射、页级校验均已通过。受影响三题的 EVAL-08 已执行，2 agree、1 新的 key_text dispute；见 [v3 后续裁决](../../revision-2026-10-08-v3/review/followup_adjudication_2026-10-08.md)。第二人工仍 pending，未冻结数据集。

核验依据：[逐题调用与 39 个 gold 的检查](../../../../../docs/reviews/2026-10-08-implementation-143-review-audit.json) · [完整实现记录](../../../../../docs/reviews/2026-10-08-implementation-143-budgeted-model-review.md) · [未应用修改草案](resolution_suggestions_2026-10-08.json)。

## 已按建议裁决的三项

按主集 SPEC §4，模型争议须由人工标注人裁决。此前的“同意”确认了 v2 输入；本次新发现与建议分别列出，不自动覆盖原确认。

| 决定 | 样本 | 我的建议 | 具体影响 | 你的决定 |
| --- | --- | --- | --- | --- |
| 1 | ms-0125 | **保留现有标注，驳回这条模型意见** | 实际输入已经是 char_end=2226；模型误读为 2227。query、gold、key、标签均不改 | 待确认 |
| 2 | ms-0241、ms-0242 | **接受“补充说明不应必需”的意见；同步修订中英文两题** | query 不变。三类正式示例分别作为必需证据；standard-of-care 那句保留为补充背景。原第二单元拆成两个语义单元；新的三组证据映射到两个物理 chunk | 待确认 |
| 3 | ms-0280 | **补 protocol_id；保留原 query 和日期** | query 的发布版本 3.26 属精确标准版本标识，按现行规则应加标签。原件封面确有 2026 年 3 月，无需删日期；gold/key 不改 | 待确认 |

可以回复 **“三项按建议裁决”**，或逐项给出不同决定。确认后形成新修订输入，重新检查配额、映射和哈希，并对受影响的三题进行新的模型复核；旧意见与原输入保留。新调用另绑定变更后的范围和剩余额度，不删除本次费用记录、不自动重置为新的 5 USD。只有 ms-0125 保留原输入时可以用明确的人工 resolution_note 解决原争议。

## 逐项证据与具体改动

### 1. ms-0125：模型读错偏移，原数据正确

问题：According to GVP Module IV, how should pharmacovigilance audit findings be graded as critical, major, or minor, and what is the specific definition of each grade?

- 模型错误指称：ms-0125-g3 是 `[1755,2227)`，因此应将结束位置改为 2226。
- **实际发送的归档输入**：`[1755,2226)`，证据文本 471 字符；`page_text[1755:2226] == evidence_span.text` 为 true。
- `2226` 处才是下一个分隔空格；本次输入没有将它包含在 span 内。
- 实际提示 SHA-256：`5c01c84714852cf45a7251bc4172f763a0c0f0d24a6b143f7b239627ea523f2b`，归档在 `main/chunk_inputs/input_<sha256>.jsonl`（原页输入目录不入 Git）。
- 模型对四个证据单元的联合必要性、三级定义、其他字段均表示同意。中文对应题 ms-0124 也为 agree。

建议裁决文字：**保留：本次实际输入 char_end 已是 2226，原页切片与 471 字符的证据全文一致；模型将其误读为 2227，未发现需要修改的标注。**

### 2. ms-0241 / ms-0242：三类示例与补充说明分开

中文问题：根据 FDA 2025 年 12 月《Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices》指南，§ 312.32(c)(1)(i) 的哪些示例说明药物与不良事件间存在因果关系的“合理可能性”（reasonable possibility）？

英文题含义相同。问题询问法规列举的示例，没有额外要求回答指南对 standard of care 的补充解释。中英文模型意见均认为现有第三组被过度要求。

建议保持问题文字，将必需 gold 调整如下（同一来源物理第 7 页）：

| 新单元 | 回答内容 | span | 定位方式 / 物理 chunk |
| --- | --- | --- | --- |
| g1 | 罕见且与药物暴露高度相关的单次事件 | `[753,1185)`；保留原 g1 | 保留原 key；`03b274ab-a8e2-4032-bbc7-10379ae547b9` |
| g2 | 与药物暴露不常相关、但在暴露人群中少见的事件 | `[1186,1362)`；从原 g2 拆出 | 新 key 保留对象及两项限定；`dc317e2b-b2e7-49ab-b9e7-298ff69fb957` |
| g3 | 汇总分析显示治疗组事件更频繁，并保留适用事件说明 | `[1363,1731)`；原 g2 的后半段 | 沿用原 aggregate-analysis key；同一个 `dc317e2b-b2e7-49ab-b9e7-298ff69fb957` |
| 补充背景 | standard-of-care 治疗也可能相关 | `[1732,1900)`；原 g3 | 原文保留在语料中，不再作为这个问题必须命中的 gold |

新的 g2 key 原文：`One or more occurrences of an event that is not commonly associated with drug exposure but is otherwise uncommon in the population exposed to the drug`。

三类信息都应覆盖，但后两类恰好共处一个物理 chunk；命中该块可以覆盖两组。逻辑证据单元与物理切块不是一一对应。必需信息应由问题和原文含义决定，不能因为说明文字落在另一个 chunk 就自动要求命中它。

所有建议 span 已用原页切片核对，新 key 页内唯一。**这些检查仅证明草案能定位，不等于新模型复核或人工裁决已经完成。** 未改 v2 proposals、输入、manifest、映射或用户确认文件。

### 3. ms-0280：补版本检索标签，日期有原文

问题：根据《MedDRA 数据检索和展示：考虑要点》发布版本 3.26（2026 年 3 月），用户能否临时改动 MedDRA 的术语层级结构，例如变更某个 PT 的主 SOC 分配？

- 现有 slices：`negation, mixed_zh_en`。
- 建议 slices：`negation, mixed_zh_en, protocol_id`。
- 依据：[主集 SPEC 的 2026-09-22 补充口径](../../../SPEC.md)：query 中用于锁定条款的标准版本号属于 protocol_id。该题明确写出 3.26。
- 模型只收到 gold 所在第 8 页及标题，因此说无法核对发布日期；这反映复核包提供的元数据上下文有限，不能据此断定日期错误。
- 自审检查了 source_hash=`ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938` 的[本地第 1 页](../../../pages/ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938/1.txt)，封面明确写“发布版本 3.26”“2026 年 3 月”；该文件哈希已记录在修改建议 JSON 中。

## 模型争议原话

下面保留原始 reason 与 suggestion；模型错误也原样保留。事实核对和采纳建议见上文。

### Claude：ms-0125

**reason 原文**：

> 联合证据内容上成立：g1 给出分级要求（“Audit findings should be reported in line with their relative risk level and should be graded in order to indicate their relative criticality to risks impacting the pharmacovigilance system, processes and parts of processes.”），g2/g3/g4 分别给出 critical/major/minor 三级定义，四个单元共同必需、无冗余，negation 由 span 内“which is however not considered serious”“that is not expected to adversely affect”承载，key_text 各自在第 8 页唯一出现。问题在偏移一致性：按所附第 8 页规范化页文本，g1=[952,1176) 与其 224 字文本吻合、g2=[1177,1754) 与其 577 字文本吻合、g4=[2227,2456) 与其 229 字文本吻合（各 span 间以单个空格分隔），但 gold ms-0125-g3 的文本“• major is a significant weakness … which is however not considered serious.”实际长度为 471 字符，而声明区间 [1755,2227) 宽度为 472，多包含了“serious.”与“• minor”之间的那个分隔空格，故偏移所指文本与 text 不完全一致。

**suggestion 原文**：

> 将 ms-0125-g3 的 evidence_span.char_end 由 2227 改为 2226（保持 char_start=1755），使偏移所指文本与 text 逐字一致；其余 gold 偏移与切片、部门标注保持不变。

### Claude：ms-0241

**reason 原文**：

> query 问的是 § 312.32(c)(1)(i) 列举的哪些示例说明“合理可能性”，该法规示例共三项，已由 ms-0241-g1（“• A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure (e.g., angioedema, hepatic injury, Stevens-Johnson Syndrome).”）与 ms-0241-g2（第 7 页“• One or more occurrences of an event that is not commonly associated with drug exposure but is otherwise uncommon in the population exposed to the drug (e.g., tendon rupture). • An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group.”）完整覆盖，联合证据已足以回答。ms-0241-g3 的原句为第 7 页“For aggregate analysis under § 312.32(c)(1)(i)(C), such events could also be associated with treatment or therapy that is standard of care for the disease or condition.”，这是 FDA 对第三项示例适用范围的补充说明，本身并不是法规列举的示例，属可选补充而非回答本 query 的必需单元，却被 evidence_rule=all_gold_units_required 强制要求。其余项核对无误：三个 span 偏移与页文本一致（g1 753–1185、g2 1186–1731、g3 1732–1900 逐字吻合），两个 key_text 在第 7 页各出现一次且保留对象与约束；切片 protocol_id（query 锁定 § 312.32(c)(1)(i)）、mixed_zh_en（中文 query 含英文术语）成立，gold 全在第 7 页且各 span 均短于 1,500 字符故无 long_context，span 内无剂量、否定或时间窗表达；安全性报告指南归 PV 恰当。

**suggestion 原文**：

> 将 ms-0241-g3 降为可选补充（从必需单元移除），或把其内容并入 ms-0241-g2 的 span 作为第三项示例的限定说明而不单列为独立必需 gold；若确实希望考查该补充说明，建议改写 query 明确询问“对于 § 312.32(c)(1)(i)(C) 的汇总分析，哪些事件也可纳入”，使该单元成为必需。

### Claude：ms-0242

**reason 原文**：

> ms-0242-g3（第 7 页）被列为共同必需单元，但其原文为「For aggregate analysis under § 312.32(c)(1)(i)(C), such events could also be associated with treatment or therapy that is standard of care for the disease or condition.」——这是指南对聚合分析中事件来源的补充说明，并不是 § 312.32(c)(1)(i) 列举的第三个「示例」本身；query 问的是哪些示例说明因果关系的「reasonable possibility」，该句属可选补充而非回答所必需。g1 + g2 的两个 span 已连续覆盖同页三个条目（单次罕见且与药物暴露强相关的事件、虽与药物暴露不常相关但在暴露人群中罕见的事件、以及「An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group.」），联合证据已完整。把 g3 设为共同必需构成冗余/过度要求。其余项核对无误：三个 key_text 均在第 7 页逐字出现且各只出现一次；偏移与 text 一致，span 连续衔接且保留限定条件；query 自然、含锁定条号 § 312.32(c)(1)(i) 符合 protocol_id；英文 query 与 parent_query 问同一件事、限定条件一致；safety reporting 指南归 PV 正确。

**suggestion 原文**：

> 将 ms-0242-g3 从共同必需单元降为可选补充（或删除该 gold 单元），仅以 g1、g2 作为联合必需证据；如确需保留聚合分析的 standard-of-care 说明，建议把该句并入 g2 的 span 作为同一条款上下文，而不再作为独立的必需 gold。另可考虑为第二个示例（“not commonly associated with drug exposure but is otherwise uncommon in the population exposed to the drug”）补一个共享该 span 的 key_text，使三个示例的命中点齐备。

### Claude：ms-0280

**reason 原文**：

> 切片标签缺 protocol_id。query 以“发布版本 3.26”锁定具体标准版本（并附节级主题“不要改动 MedDRA”所在版本），按切片定义“protocol_id：query 中有锁定条款的精确标识，如法规条号、标准版本、批准号或节编号；只有指南名不计”，此处不只是指南名，检索依赖该版本号的精确匹配，应加 protocol_id。其余各项核对无误：key_text“用户不得对 MedDRA 进行临时的结构改动,包括变更主 SOC 分配”在页文本中仅出现一次且逐字原文，同时保留对象（MedDRA 层级结构/主 SOC 分配）与否定约束；evidence_span 为 2.3 节完整条款，含禁止表述“不应更改”“不得”及补救途径“应向 MSSO 提交变更申请”，偏移 535–657 与所给 text 逐字一致（按 norm-v1 页文本计数，第 535 字符正是“MedDRA 是一个标准术语集”之“M”，长度 122）；negation（“不得”“不应更改”）与 mixed_zh_en（query/key_text 含 MedDRA、PT、SOC）成立；MedDRA 文档归 PV 正确。另备注：query 中“（2026 年 3 月）”无法由所给页文本或 document.title 核实，仅作提示，不单独计为问题。

**suggestion 原文**：

> 在 slices 中补加 "protocol_id"，即 ["negation", "mixed_zh_en", "protocol_id"]；若起草者认为版本号不构成检索依赖，则建议从 query 中删去“发布版本 3.26（2026 年 3 月）”改为仅引用指南名，以与现有标签一致。同时建议核实“2026 年 3 月”这一发布日期是否有原文依据，否则删除该括注。

## 全部 19 题原始结果

同意只表示本次模型意见；争议未裁决，第二人工未完成。

| 样本 | 批次 | 模型意见 | 争议字段 | CLI 估算 USD |
| --- | --- | --- | --- | ---: |
| ms-0124 | main/PV | 同意 | — | 0.240535 |
| ms-0125 | main/EN | 争议 | evidence_span | 0.362760 |
| ms-0177 | main/PV | 同意 | — | 0.079885 |
| ms-0178 | main/EN | 同意 | — | 0.082498 |
| ms-0205 | main/PV | 同意 | — | 0.148498 |
| ms-0206 | main/EN | 同意 | — | 0.232297 |
| ms-0241 | main/PV | 争议 | evidence_span | 0.185672 |
| ms-0242 | main/EN | 争议 | evidence_span | 0.102566 |
| ms-0243 | main/PV | 同意 | — | 0.235366 |
| ms-0244 | main/EN | 同意 | — | 0.187210 |
| ms-0280 | main/PV | 争议 | slices | 0.149954 |
| ms-0298 | main/CO | 同意 | — | 0.174029 |
| ms-0299 | main/CO | 同意 | — | 0.117504 |
| ms-0336 | main/CO | 同意 | — | 0.064310 |
| ms-0337 | main/EN | 同意 | — | 0.078423 |
| ms-0525 | main/PV | 同意 | — | 0.140929 |
| pc-0017 | probe/MA | 同意 | — | 0.105035 |
| pc-0028 | probe/MA | 同意 | — | 0.158297 |
| pc-0029 | probe/MA | 同意 | — | 0.071754 |

原始意见文件：[CO](main/verdicts_CO.jsonl) · [EN](main/verdicts_EN.jsonl) · [PV](main/verdicts_PV.jsonl) · [探针 MA](probe/verdicts_MA.jsonl)。所有 agree 的解释也保存在其中，未用实现方摘要覆盖。

## 名词速查

- `query`：给系统的问题。
- `gold`：评测标准证据；必需组必须全部覆盖，组内等价块任选。
- `key_text`：从原文逐字选出的定位锚点。
- `evidence_span`：标准证据的完整原文及半开区间 `[char_start,char_end)`；结束位置不包含在内。
- `chunk`：实际检索的物理文本块；一个块可以支持多个逻辑证据单元。
- `protocol_id`：这个项目的切片名，涵盖用于锁定目标的法规条号、标准版本等精确标识。
- `provisional`：证据链尚未满足全部正式验收条件；本轮模型完成不能替代第二独立人工。
