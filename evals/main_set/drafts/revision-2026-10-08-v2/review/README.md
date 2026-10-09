# 19 条修订的独立模型复核包

准备日期：2026-10-08。第一人工确认见上级目录的 `human_confirmation_2026-10-08.json`。

## 输入与状态

本包共 19 题、39 个 gold 单元：主集 16 题，探针 3 题。其中 10 题含多个共同必需的证据单元。`preparation.json` 固定样本 ID、输入文件和提示的 SHA-256；它只记录准备步骤，实际调用与意见须另查 `run_*.json` 和 `verdicts_*.jsonl`。

2026-10-08 用户回复“执行”，批准本次 19 题、总预算上限 5 USD 的模型复核，见 [预算授权](budget_authorization_2026-10-08.json)。**实际已完成 19/19：15 同意、4 争议。** 原始 CLI 费用约 2.91752125 USD，保守入账 2.917528 USD；无失败、重试、未知费用，剩余 2.082472 USD。项目所有者随后按建议完成[三项裁决](adjudication_2026-10-08.md)，修改已进入 [v3](../../revision-2026-10-08-v3/README.md)；本目录继续保存裁决前输入和原始意见。调用状态与费用见 [总账本](budget.json)，有效结论见各批次 `run_*.json` / `verdicts_*.jsonl`。固定模型 `claude-opus-5`，请求 effort=high；CLI 回显模型标识，但不回显 effort。没有把用户的“同意”、起草理由、旧模型意见或检索块排名交给复核模型。模型可质疑每个证据单元及其共同必需性。

| 范围 | 批次 | 题数 | 使用提示 |
| --- | --- | ---: | --- |
| 主集 | CO | 3 | `main/review_prompt.md` |
| 主集 | EN | 6 | `main/review_prompt.md` |
| 主集 | PV | 7 | `main/review_prompt.md` |
| 探针 | MA | 3 | `probe/review_prompt.md`，保留探针 v2 的原提示 |

输入含完整 norm-v1 原页；全文 JSONL 由 `.gitignore` 排除，只保留可重建工具、哈希和提示。多证据采用 `multi-gold-review-v1`，同页正文去重，每个 gold 仍单独保留 key、span、页、来源及版本。旧单 gold 输入协议保持原样，避免破坏历史提示哈希重建。

## 可重建命令

在仓库根目录运行（只读原页、生成本地输入，无模型调用）：

```sh
venv/bin/python evals/main_set/tools/prepare_revision_review.py \
  evals/main_set/drafts/revision-2026-10-08-v2 \
  --confirmation evals/main_set/drafts/revision-2026-10-08-v2/human_confirmation_2026-10-08.json
```

工具先校验修订和确认事件的哈希，再应用已确认的语料标题修正，最后打包。若已有输入内容不同，拒绝覆盖，要求新复核包。调用前应重新核对 `preparation.json` 的输入/提示哈希。

后续调用使用 `run_review.py` 的 `--review-dir` 和 `--prompt-file`，固定模型与 effort，建议 `--chunk 1`；一题变更不使无关题被重复复核。`--max-call-cost-usd` 只向 CLI 传递单次预算参数，不能当作整批费用上限；总预算还须计入失败、无效输出及重试。

本次四批共用同一个 `--budget-ledger` 和 `--budget-authorization`。先预留后调用，返回后按实际费用向上取整到 0.000001 USD 入账；未知费用、未结束预留、CLI 超出预留或余额不足都会阻止下一次调用，不自动重试。第一题单次预留 0.25 USD；核对实际返回后，后续每题预留 1.25 USD，为较长推理留出空间，调用完成即释放未使用额度，总上限仍为 5 USD。单次预留不是每题实际支出，也不是对供应商计费系统硬限额的证明。

CLI 当前通过 Claude 订阅登录，所报 USD 为 CLI 用量估算，不等同于新增信用卡扣款。原始 stdout/stderr 以 0600 权限保存在忽略目录 `call_artifacts/`；追踪文件只留必要身份、哈希、意见、Token 与费用。输入 Token 分别记录普通输入、缓存读取和缓存创建；合计包含三者。

## 完成后的处理

1. 保存 CLI 实际返回的模型标识、原始意见、调用输入、时间与费用。未执行、模型不匹配或无效输出不得登记成完成。
2. 将争议逐题提交用户，附原页依据和具体修改建议；接受修改后形成新输入并重新复核受影响题。
3. 先冻结三条 `pc-` 所在的探针新版本，再导入新的主集版本；本准备步骤不冻结数据集。
4. 模型复核完成也不填第二人工身份；保持 provisional 和第二人工 pending。正式评分与新盲测仍是阶段 1 的待办。
