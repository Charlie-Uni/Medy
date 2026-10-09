# 记录 147：三项人工裁决、v3 修订与定向 EVAL-08

日期：2026-10-08。OPT-12/13。状态：**原三项裁决已落实；定向复核 3/3 调用成功并在 0.75 USD 内结算；2 agree、1 个新 key_text 争议待人工裁决，因此数据阶段未通过。**

## 授权与范围

项目所有者原话：“**三项按建议裁决，允许 EVAL-08 最多 0.75 USD**”。本轮据此执行：

- `ms-0125` 保留当前 `char_end=2226`，不作无意义重复调用；
- `ms-0241` / `ms-0242` 把法规列举的三个示例拆成三个共同必需的语义 gold；后两个 gold 共享同一物理 chunk；standard-of-care 句只作可选背景；
- `ms-0280` 增加 `protocol_id`，query、gold 和已由封面核实的日期不变；
- 付费复核只含发生输入变化的 `ms-0241`、`ms-0242`、`ms-0280`，固定 `claude-opus-5`、请求 effort=high、每次一题、最多 3 次、每次 0.25 USD、总额 0.75 USD、无自动重试；任一未验证调用或未知费用会阻止后续消费。

没有把本轮模型复核登记为第二独立人工。没有冻结、发布或运行正式业务评测。

## v3 数据修订

新建 [`revision-2026-10-08-v3`](../../evals/main_set/drafts/revision-2026-10-08-v3/README.md)，保留 v2 和原始 19 次模型意见。v3 manifest SHA-256 为 `279c91a6ab2c7a667399419b51d97aeb27ea59972fe77716d75412550f46398d`，人工确认 SHA-256 为 `ee390f2e5b6df7f7dcbd4a6e86318bbe71a6f58860d605c984e8439b10075bfa`。

第一次零费用校验发现修改建议 JSON 中的两个新 gold 没有 schema 必填字段 `printed_page_label`。这是建议草案结构不完整，不是证据内容或偏移错误。补为 `null` 后重算 proposals、manifest 和人工确认哈希，再重新运行页级校验：

- 19 条 proposals、39 个 gold；39/39 mapped；
- 原页切片、半开区间、key 包含与页内唯一性全部通过；
- 三个语义 gold 映射为三个必需组，其中后两组合法共享 `dc317e2b-b2e7-49ab-b9e7-298ff69fb957`；
- 投影主集 615 条，`protocol_id=150`，配额短缺为空；
- `freeze_ready=false`，第二人工仍 pending。

完整 19 条复核包先由确认文件和 manifest 生成，再筛出专用 EVAL-08 输入。专用输入本身只有三题，从数据层避免 `--only` 用错时扩大付费范围。

## 费用保护补强

`ReviewBudget` 新增两个由授权 scope 驱动的机器约束：

1. `max_attempts` 达到后拒绝任何新预留；
2. `stop_on_nonvalidated_attempt=true` 时，任一已结算但非 `validated_reply` 的调用会阻止后续消费。

新增测试覆盖次数上限、失败后停止和非法次数配置。`.gitignore` 同时补上嵌套 review 包的 `call_artifacts/` 与账本锁文件，防止 `git add -A` 收入原始 CLI 输出。三个原始 capture 均为 0600，哈希写入 run 与审计；原始输入页包仍被忽略。

## 实际复核与费用

| 样本 | 批次 | 结果 | 争议字段 | CLI 估算 USD | Token（含缓存输入） |
| --- | --- | --- | --- | ---: | ---: |
| `ms-0242` | EN | agree | — | 0.18727250 | 12,246 |
| `ms-0241` | PV | dispute | `key_text` | 0.19692875 | 12,555 |
| `ms-0280` | PV | agree | — | 0.17169750 | 10,585 |
| 合计 |  | **2 agree / 1 dispute** |  | **0.55589875** | **35,386** |

逐次向上取整到微美元后的账本值为 **0.555900 USD**，余额显示 **0.194100 USD**。3 次尝试上限已经用完，因此该余额不能被本授权继续消费。失败、重试、未知费用和单次限额超出均为 0；3 个 session 唯一。CLI 不回显实际 effort，只能证明请求值为 high。

[逐调用审计 JSON](2026-10-08-implementation-147-review-audit.json)验证了授权绑定、manifest/确认/输入/提示哈希、重建的实际 prompt、run 与 verdict 镜像、原始回复、模型/session/费用、capture 哈希及权限。

## 新争议与建议

`ms-0241-g3` 当前 key 为：

> An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently

模型认为它遗漏了第三个示例成立所需的比较对象，即药物治疗组相对同期或历史对照组。建议把 `ms-0241-g3` 和英文孪生 `ms-0242-g3` 同步扩为：

> An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group

建议值在原页 `[1365,1561)` 唯一出现，仍完全位于现有 span `[1363,1731)`；query、span、证据组、chunk 映射均无需改变。`g2` 的 `not commonly associated` 是描述性属性，模型也没有把 slices 判为 issue；按现行 negation 口径不新增标签。

英文孪生 `ms-0242` 使用同一个当前 key，但另一独立会话给出 agree。这说明复核者判断不一致，不能把任一意见静默覆盖。完整待决定项见 [v3 后续裁决](../../evals/main_set/drafts/revision-2026-10-08-v3/review/followup_adjudication_2026-10-08.md)。若接受建议，中英文两条输入都变化，需要新的两次复核授权；现有三次调用授权已耗尽。

## 验证与自审

- 预算单元测试：20 passed；ruff lint 通过，格式化已修正。
- v3 `annotation_revision --with-pages`：通过，39/39 mapped。
- EVAL-08 审计：通过，但如实保留 1 个模型 dispute。
- `env -u DEBUG make check`：1635 passed、70 skipped、1 个沿用的测试短 HMAC key 警告；ruff、423 个文件格式、186 个源文件 mypy、四套评测输入审计和 Schema 漂移检查全部通过。评测审计继续如实报告 7 个 unmappable gold、旧历史回放、第二人工 pending、无未见盲测及 19 条修订仍为 draft。

| 自审项 | 结论 | 依据与限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | 三项按建议落实；只调用授权三题；未改验收阈值、正式分母或发布状态 |
| 正确性与失败 | 通过（工具与已裁决输入） | schema 漏字段在付费前被拦截并重验；次数/失败停止为机器约束；新语义争议未冒充通过 |
| 权限与追溯 | 通过 | 精确授权、输入和费用绑定；capture 0600 且递归忽略；第二人工仍明确为 pending |
| 验证 | 通过 | 页级、映射、逐调用哈希和定向测试通过；全量 1635 passed、70 skipped，lint、格式、mypy、评测审计与 Schema 均通过 |
| 状态与文档 | 通过 | v2 历史、v3 修订、模型意见、人工裁决和后续争议分层保存 |

**本轮裁决应用、调用控制和审计自审通过；标注内容仍因 `ms-0241/0242` 的新 key 决定而未完成，阶段 1 不通过。**
