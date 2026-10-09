# 回答语义支持与完整性：answer-quality-v1-provisional

日期：2026-10-08；记录 136。依据工程基线 §5.3、§5.4、§5.9，以及本次迭代要求分别报告语义支持与完整性。

**状态：诊断协议，尚未完成真实输出的独立裁判校准。** 主集 `main-outcome-v2`、原始门槛及旧成绩继续保留。本协议的报告固定 `formal_gate=false`；不能仅凭测试 fixture 或裁判一致就宣称引用准确率门禁通过。

## 1. 输入证据

每次新的主集运行在 `answer_review_inputs/<SHA-256>.json` 保存最终输入快照，行记录固定文件 SHA-256 与 canonical case hash。快照包含：

- 问题、部门、样本身份和原标注哈希；是否有答案及终态。
- 最终 `Answer.claims`、每句的 `citation_chunk_ids`、带版本/页码的引用对象。
- 当时已经授权并回查的 Evidence 原文与内容哈希。
- 对应文档的标题、document_key、版本和 source_hash；通过提问者权限连接读取。
- 原样本的 gold 单元与运行版本。

不放入生成时的 Verifier 判断、旧成功/失败标签、人工批准或候选名称。快照是最终原文证据，不代表所有裁剪策略给 Answer 模型发送的具体提示字节；分析提示裁剪还须查看实际模型调用证据。

正文快照留本地，由 Git 忽略。保存失败会明确记录 `answer_review_error`，已完成的回答、耗时和费用行仍保留；缺快照的运行不能继续做本协议的语义统计。旧运行只有句子和引用总列表时，不从今天的数据库猜出当时逐句关系。

## 2. Claim 支持度

每个 claim 按零起始 `claim_index` 审一次，联合阅读该句实际引用的片段。不能用未被此句引用的 gold 或其他片段替它补依据。

| 值 | 判断规则 |
| --- | --- |
| supported | 实际引用的联合证据直接支持该句全部事实、数字、单位、否定、对象和适用条件；必要的跨块信息可以联合成立 |
| not_supported | 原文未给足依据，添加了条件/结论，混淆文件归属，或只支持该句的一部分 |
| contradicted | 该句与引用原文有直接冲突，例如把“不得”写成“可以”、数值/单位/对象错误 |
| unverifiable | 输入缺失、原文质量或真实语义歧义导致无法可靠判定；说明具体缺口 |

不得用医学常识纠正原文、替换限制或补完答案；原文质量有疑点时交人工处理。每条意见必须有 reason，指出句子位置和证据依据。

## 3. 引用支持度

分母是最终答案 `citations` 列表中的引用条目数，按零起始 `citation_index` 完整覆盖，保持运行中的条目顺序与出现次数。同一 chunk 若被多个 claim 关联，要核对每个关联；不因其他句子用对过一次就自动认可全部用途。

- supported：该引用对关联陈述提供直接、相关的支持，且关联使用没有矛盾或错误归属。联合证据中的一个片段可以只承担其中一个必要部分；完整联合支持另由 Claim 审查保证。
- not_supported：引用未参与支持、与关联陈述无关、归属错误或关联使用中存在无依据之处。列出受影响 claim_index。
- contradicted：关联陈述与该引用原文冲突。
- unverifiable：无法从保存的材料判定。

未被任何 claim 使用的多余引用应记 not_supported。结构上存在、可读、在 Evidence 中，以及命中 gold，均只是审查输入；仍须给出语义判断。

## 4. 答案完整性

对每道有答案问题给出一项 `completeness`：

- complete：回答了问题要求的全部部分，并保留影响含义的对象、范围、适用条件和来源约束。
- incomplete：漏答、答非所问、错误部分使任务未完成，或所问的文件/产品/版本未被满足。
- unverifiable：问题或 gold 本身存在需要裁决的歧义；不得为给分而补造答案。

参考 query 和完整 gold span 判断哪些内容是问题所必需的，不能把 key_text 命中或“已引用全部 gold ID”直接当作完整回答。若 query 要求两种替代情况都作说明，应解释两种；原文业务逻辑仍保持“或”，不能误写成必须同时成立。

有答案题发生弃答/系统故障时，完整性为 incomplete，保留在分母。无答案题为 not_applicable，不进入该完整性分母，其行为由原无答案评分负责。

例如：问题要求“等级定义”和“后续措施”，回答只解释等级，即使每句引用都支持，也属于 incomplete；问题点名 A 文件，B 文件的相同句子可能支持文字事实，但仍未满足 A 文件的来源要求。

## 5. 输出与身份

每个 case 输出一条 `answer-review-verdict-v1`，绑定 canonical `case_sha256` 和 `rubric_version=answer-quality-v1-provisional`。必需字段：

```json
{
  "format": "answer-review-verdict-v1",
  "rubric_version": "answer-quality-v1-provisional",
  "case_sha256": "该输入 canonical SHA-256",
  "reviewer": {
    "kind": "llm",
    "id": "实际复核者标识",
    "model": "实际观测的模型标识",
    "prompt_sha256": "实际提示的 SHA-256",
    "independent_second_human": false
  },
  "claims": [{"claim_index": 0, "verdict": "supported", "reason": "填写实际原文依据"}],
  "citations": [{"citation_index": 0, "verdict": "supported", "reason": "填写实际关联与依据"}],
  "completeness": {"verdict": "incomplete", "reason": "填写具体漏答点"}
}
```

以上仅为结构示例，不能登记为已发生的模型意见。完整执行还需保存调用提示、原始回复、观测模型、时间和费用；结构校验本身不能证明模型真正执行过。人工意见使用真实 human 身份，模型绝不登记为第二人工。

同一 case 有多个意见时保留各自原始记录。汇总器拒绝重复 case，须明确选择待比较的复核批次，或以有据可查的人工裁决生成最终意见；不按文件最后一行自动覆盖争议。

## 6. 统计与使用

独立报告 `claim_support`、`citation_support`、`answer_completeness`；每项给出 numerator、denominator、pending、unverifiable 和 rate。尚未复核或仍无法判定时 rate=null，展示已知计数；零分母也为 null。模型一致性、人工抽检比例及争议类型需在真实复核后另报。

```sh
# 无模型调用；不传 --reviews 时只报告材料数量与 pending
venv/bin/python evals/harness/tools/answer_review.py \
  --run PATH_TO_NEW_MAIN_RUN --out NEW_DIAGNOSTIC.json

# 导入已发生并保存证据的意见；输出文件已存在会拒绝覆盖
venv/bin/python evals/harness/tools/answer_review.py \
  --run PATH_TO_NEW_MAIN_RUN --reviews ACTUAL_VERDICTS.jsonl --out NEW_REVIEW_REPORT.json
```

下一步是在真实新版问题与输出上执行独立模型复核，抽查支持/矛盾/遗漏/指定来源/跨块情况，将实质分歧交用户裁决。裁判尚未校准时，此处的实现不能单独替代正式验收。

## 7. EVAL-12 校准面板

`calibration-v1-plan.json` 固定 10 道 `main-v5-provisional` 题，覆盖三类历史裁判误判、点名产品、等价载体、宿主文件引用、英文、两到五个共同必需证据、长上下文、版本冲突和文件关系。每项绑定完整样本 SHA-256。该面板是有目的的开发集诊断，不是随机样本，也不估计总体准确率。

执行分两次单独授权：

1. 先用已发布运行配置生成 10 个真实回答和逐句证据快照，本次进程上限 0.35 USD；
2. 确认至少 8 个有回答且快照完整后，再为实际 case hash 生成精确复核授权；计划上限为 10 次、每次 0.30 USD、合计 3.00 USD，遇首个未校验回复停止。

API Gateway 的进程上限在每次 provider call 前按价格表最坏费用预留；provider 失败按该预留计入本次上限。它与 PostgreSQL 月度总账并行生效，不能替代用户对本次运行的授权。

模型意见逐句和逐引用覆盖完整后，交项目所有者处理实质分歧。当前只有一名人工，所有者裁决只能作为本项目的 owner calibration，不能登记成第二独立人工或正式门禁。
