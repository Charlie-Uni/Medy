# 实现记录 53：DEC-003 Verifier 判定臂对比（规则臂 + 订阅 CLI 臂）

- 日期：2026-09-23
- 范围：决策人指示先做不需要决定的事；DEC-003（基线 §10：Verifier 用 NLI 还是小 LLM）的实验数据与前两臂。API 臂等 `OPENAI_API_KEY`。设计与数据见 [evals/verifier/README.md](../../evals/verifier/README.md)。
- 花费：规则臂 0；CLI 臂消耗 Max 订阅额度，CLI 报出的 API 等价成本记录在结果文件，不计入 ADR-0010 的 30 美元上限。

## 1. 数据

`main-v1-provisional` 553 条有答案样本中 546 条 gold 可映射到 chunk → 2,076 对：supported 546、not_supported/same_doc 546、not_supported/other_doc 546、contradicted/numeric 148、contradicted/negation 290。标签全部机械可审（包含关系、数值×2、否定翻转，变换逐条记录）。局限已写入 README：陈述为逐字条款，非改写答案句；矛盾为合成。

## 2. 臂 0：确定性规则（`verifier-v1+support-rules-v1`）

三次迭代，每次改动都有单元测试：

| 版本 | 准确率 | 错接受率 | negation 类 | numeric 类 | same_doc | supported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 初版（陈述级包含/重叠不看否定） | 80.4% | 20.6% | 20.0% | 71.0% | 80.6% | 97.3% |
| 包含/重叠带布尔否定极性 | 89.0% | 7.0% | 80.3% | 71.0% | 85.2% | 92.9% |
| **对齐窗口内否定线索计数**（现行） | **91.0%** | **5.2%** | 90.0% | 71.0% | 85.2% | 95.4% |

- 现行混淆矩阵（行=标签，列=预测）：supported 521/0/25；not_supported 35/1003/54；contradicted 44/28/366。
- 规则单独决定（无需包含/重叠兜底）的比例 42.2%。
- 剩余错误形态（抽样核对）：(a) numeric 类 29% 漏判——证据里同族剂量不止一个（如"100 mg…增加 100 mg…不得超過 800 mg"），"唯一异值即矛盾"规则不触发，落到重叠→supported；(b) same_doc 负例 15% 误接受——同文档相邻 chunk 复述同一表述（SMQ 指南的并列条目、GVP 的重复句式）；(c) supported 4.6% 误判矛盾——长句中距离匹配窗口 24 字符内另有否定线索。
- 结论：规则臂把安全相关的错接受率压到 5%，但 numeric 多值与近邻复述两类需要模型判定；这正是 LLM 臂要回答的问题。

## 3. 臂 1/2：Claude 各档经订阅 CLI（300 对种子子集，seed 1）

（后台运行中，结果回填本节：准确率、错接受率、分类别、费用等价、与同子集规则臂的对照。）

## 4. 待 key 的臂

`gpt-6-luna` / `gpt-5.4-mini` / `gpt-6-sol` 经 `OpenAIModelGateway`，同一提示、同一 300 对子集；Gemini 3.5 Flash-Lite 可选。ADR-0011 在三臂齐后写。

## 5. 自审（§9）

- 数据不含新标注，标签可机械复核；页文本派生物（pairs、原始回复）不入 Git，结果报告入 Git。
- 规则修正的每一步都有反向测试（`test_containment_and_overlap_carry_negation_polarity`、`test_negation_flip_of_a_contained_statement_is_a_contradiction_not_support`）。
- CLI 臂的提示与运行时 `JUDGE_SYSTEM` 同源，但批量 10 组一问与运行时单组一问不同，结论对运行时只作近似；API 臂用运行时同一路径（Gateway、单组、JSON schema）。
