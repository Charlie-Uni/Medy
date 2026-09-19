# 续接记录 24：承接人工确认与探针正式复核

日期：2026-09-19。任务：依据用户交接继续 M1-01，保留原始人工编辑，修复 CO 重建，落实已批准的标注规则，运行独立复核并记录真实结果。P0 任务权重仍为 22.8%，未宣称探针已冻结。

## 1. 交接状态

- 用户已在交接中回复“全部确认”，批准 P1/P2/P3、MA 试跑处理建议和 high 正式复核。原始依据与本轮补充确认见[人工确认记录](../../evals/probe/precise_clause/drafts/v1/review/owner_confirmations_2026-09-19.md)。
- PV 的人工编辑已重建；CO specs 已吸收编辑，但 pc-0064 的显式 span 因原文句号前有空格而无法重建。本轮从 norm-v1 页文本定位完整原句，仅对齐句号前空格，成功重建 CO 16 条。
- PV/CO 原始人工表分别含 29/16 条 OK，不能继续报告为“尚未保存或尚未人工确认”。新变更、独立复核与争议裁决仍单独记录。
- 接手时 MA high 复核仍在后台运行，但使用旧提示：未同步已批准的 P1/P2，MA 展开词与基线也不一致。停止旧进程并归档 14 条已完成结果及原提示到 `review/superseded_2026-09-19_high_old_policy/`，不进入正式 manifest。none 试跑仍独立保留。

## 2. 本轮修正

1. 同步 SPEC 与 review_prompt 的 P1/P2/P3 语义，保持样本数量和实验阈值不变；MA 展开为医学事务。提示输入字段改为与实际 reviewer pack 一致。
2. 重新生成 MA/PV/CO 的逐条复核包；三个批次各自逐条调用，使用相同提示与 `gpt-6-astra / high`。复核只依据提供的页文本，不请求外部医学资料。
3. 驱动记录每条输入哈希、实际组合提示哈希与观察到的模型/强度。仅当新旧输入、提示与参数一致才允许 `--only` 续跑；空过滤和不存在的 ID 拒绝执行。
4. 装配工具验证当前样本/页文本重建出的输入与复核绑定一致，要求全覆盖且实际 high；旧提示结果、修改后未重审的结果和半批结果均拒绝装配。复核包暂只支持单 gold，多 gold 明确报错，避免静默遗漏。
5. 归档输入包含派生页文本，新增对应 Git 忽略路径。

正式提示 SHA-256：`f4a3804e969b23ec9ab467406937e62f0b9e30933d6a680d4b00ee59b2631c38`。与旧口径提示不同，旧结果不能混用。

## 3. 当前草稿分布

75 条；MA 30、PV 29、CO 16；16 份主体文档，每份最多 6 条。切片：dose_unit 19、drug_name_zh 18、negation 32、time_window 21、mixed_zh_en 52、protocol_id 9；gold 文档简体中文 10 条。数量门槛满足，语义正确性以逐条复核与裁决为准。

## 4. 验证与剩余工作

- 新增复核工具回归：9 passed，覆盖内容变化、提示/强度变化、部分复核、实际强度不符、结论自相矛盾与多 gold 静默遗漏。
- `env -u DEBUG -u PYTHONPATH make check`：371 passed（307 单元 + 64 集成）；ruff、102 文件格式检查、mypy 46 文件、仓库外导入与 Schema 漂移检查通过。文档与复核工具定向检查合计 19 passed；`git diff --check` 通过。
- 当前 75 条草稿机械核对结果保存于 `review/mechanical_audit_2026-09-19.json`，包含各批输入文件哈希；缺少 review 的预期缺口单独排除，不冒充正式 v1 全规则验证。重建 pack 与运行中复核输入逐字一致。
- 正式复核 75/75 完成：MA 17 agree / 13 dispute；PV 10 / 19；CO 1 / 15；总计 28 agree / 47 dispute。全部实际执行均为 gpt-6-astra / high，CLI 0.154.0-alpha.6.2；报告 Token 总和 387,725。
- 75 条复核与当前输入、提示及实际参数的绑定检查通过，证据保存于 `review/formal_review_audit.json`。模型别名与 CLI 版本有真实记录，后端不可变模型快照版本未在元数据中暴露。
- [逐条结果](../../evals/probe/precise_clause/drafts/v1/review/formal_review_status.md)和[具体修订提案](../../evals/probe/precise_clause/drafts/v1/review/proposed_changes.md)已生成。提案含 36 处锚点、22 处标签、1 处 language、2 处 query、2 处 span 变化，字段可在同一条重复计数；候选 Schema/定位/长度/query 唯一性/数量检查无错误。尚未覆盖当前样本。
- pc-0026/0027 的 span 扩展争议与已批准的试跑处理相同，沿用既有裁决；pc-0027 不改样本。pc-0038 年度文档更新是否补 dose_unit 已单独请求人工裁决；其余 45 条具体新修订已呈交人工，不把未回复当作批准。
- pc-0053/0071 的 LLM 原建议超过 200 字符，本轮提案改为更短的连续原文；pc-0050 移除不在现有定义内的法规条款编号标签，恢复 PV 原始人工编辑选择，候选仍满足 protocol_id 数量门槛。
- 待完成：争议裁决及必要重审、真实 model_version 记录、装配与正式 draft/frozen 校验、冻结哈希与 ADR 回填。本轮不把 CLI 版本当成模型快照版本。
