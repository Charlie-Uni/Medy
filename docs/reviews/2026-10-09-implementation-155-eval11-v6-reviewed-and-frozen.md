# 记录 155：EVAL-11 v6 差量复核与后继数据冻结

日期：2026-10-09。状态：**EVAL-11 完成；probe v4 与 `main-v5-provisional` 已冻结；新正式系统运行尚未执行。**

## 1. 授权与费用

项目所有者授权：“EVAL-11 v6 复核，最多 0.65 USD”。授权绑定 v6 revision、人工确认、preparation、两个 batch 输入和提示的精确哈希：

- 模型：`claude-opus-5`；requested effort：high；
- 仅 `pc-0070`、`pc-0102`；每条一次，最多两次；
- 单次 CLI 阈值 0.30 USD；总账本上限 0.65 USD；
- 无自动重试；失败、无效 verdict、未知费用或越界立即停止；
- authorization SHA-256：`12497c2bb4b5989d10effbf141c3d9689c8768f018cbf7e3227998dd7962ae4f`。

| 次序 | 样本 | 结论 | 账本费用 |
| ---: | --- | --- | ---: |
| 1 | `pc-0070` | agree | 0.110879 USD |
| 2 | `pc-0102` | agree | 0.179848 USD |
| 合计 | 2 次 | 2 agree / 0 dispute | **0.290727 USD** |

两次调用均成功且格式有效，无失败、重试、未知费用、未结算 reservation 或单次越界。未使用授权余额为 0.359273 USD。CLI capture 权限均为 0600，文件保持 Git 忽略；run、verdict、输入、实际 prompt、session、模型和费用账本均可重建。机器结果见 `revision-2026-10-08-v6/review/outcome_2026-10-09.json`。

`ms-0440/ms-0441` 没有重复调用：它们在 v6 的完整输入、提示、模型、effort 与 v5 两条 agree 的哈希完全一致，复用证据见 `review/reused_agree_verdicts.json`。这仍是独立 LLM 复核，不是第二独立人工。

## 2. 冻结结果

### Probe v4

- 路径：`evals/probe/precise_clause/v4`；
- 107 条样本；
- dataset hash：`1427274ecd04ab6193e572ad1633cfa3bd897520315af52c40fd93e792492286`；
- 相对 v3 仅修订 `pc-0070/pc-0102`；
- 新旧复核提示按逐调用哈希保留，四批 run/verdict 均可重建；
- 冻结校验 0 error、0 warning。

### Main v5 provisional

- 路径：`evals/main_set/main-v5-provisional`；
- 615 条样本：554 有答案、61 无答案、52 冲突、200 派生、107 原样导入 probe v4；
- dataset hash：`23bf8530d63f6605b10fb2b1f9d7b3cf5cb805f5d3b20caa16f2fa2e7e5842b0`；
- 582 个 gold 单元：580 mapped、2 unmappable；
- 映射 SHA-256：`9189e9e20f38203a59d7d7cd7640dc2521ff6103dbde16f35590f4c331800d39`；
- 12 条样本含 2–5 个共同必需 gold；
- `ms-0197-g1/ms-0198-g1` 继续作为真实 miss 留在分母。

冻结状态只表示内容和复核证据固定。主集仍为 provisional，因为第二独立人工未完成；现有题已参与开发，也不能充当未见盲测集。

## 3. 组装期间发现的问题与修复

| 现场错误 | 原因 | 处理 |
| --- | --- | --- |
| probe 后继组装器只读取 `run_MA.json` | 旧实现只服务上一次三条 MA 修订；本轮样本属于 CO/EN | 改为接收多个 `--supplemental-run`，按 run 中真实 batch 合并，并要求 latest 覆盖恰好等于变化样本 |
| probe 组装器要求新旧提示相同 | 本轮使用支持证据组的新版提示，历史 105 条仍绑定旧提示 | 增加逐调用 prompt hash 和哈希命名的历史提示归档；schema 与 validator 同步支持 |
| `probe-v4-provisional` 不符合 schema | probe 版本规范是 `vN`；provisional 是主集的复核状态命名 | 未冻结草案删除后按规范重建为 `v4` |
| `pc-0070: actual prompt hash differs` | 新 preparation 将 `evidence_span` 序列化为 coordinate-first 字段顺序；内容相同但实际 prompt 字节不同 | 将第三种确定性字段顺序加入 prompt 重建候选，仍校验内容与规范对象哈希 |
| `pc-0102` reviewer input hash 不同 | 后期 packer 为英文孪生附加了冻结样本中的 `notes` 与 `parent_query`，早期 probe runner 未附加 | validator 只接受从冻结样本和父题确定性重建的两种 wire shape；不接受任意额外字段 |
| main 组装器拒绝 mixed prompt history | 顶层 run hash 是当前默认提示，历史 chunk 已正确记录旧提示 | 允许每个 chunk 使用自己的有效 SHA-256，并由最终 provenance 校验对应提示内容和实际 prompt |
| EN 覆盖被 `ms-0198` 的旧草案哈希污染 | v5 `run_EN` 顶层保存整批输入，但 latest/verdict 只包含实际调用的 `ms-0441` | 合并 supplemental run 时只导入 latest verdict 覆盖的输入哈希，不把未调用项当成意见 |
| 历史混合输入不在冻结目录 | 为控制冻结体积，旧输入包仍在原始 review 目录 | 通过显式 `--archive-root` 找回并按实际 prompt hash 复制；缺失时继续失败关闭 |
| 主集导入元数据只有单个 probe prompt hash | probe v4 的样本合法保留两代提示绑定 | 新增 `prompt_hashes` 集合；PR-09/PR-16 同时核对当前 probe 提示、reviewer ID、逐样本提示集合和样本 canonical 字节 |

所有首次失败都发生在 draft 校验或组装阶段，没有写出 `SHA256SUMS`，因此没有伪冻结版本。没有为通过检查修改 gold 语义、门禁阈值或失败分母。

## 4. 验证

- 两条新 run/verdict：实际 prompt 可重建、latest binding 一致、capture SHA-256 一致、权限 0600；
- 复核预算：2 次 accounted、2 次 validated reply、0 unresolved；
- probe v4 冻结校验：107 条，0 error、0 warning；
- main v5 draft 与冻结校验：615 条，全部页锚点、review provenance、import byte identity 与 schema 通过；
- successor mapping：580 mapped、2 unmappable，gold 覆盖恰好为 582；
- 定向回归：probe/provenance/main validator 相关测试通过；
- `env -u DEBUG make check`：**1641 passed、70 skipped、1 warning**；ruff、430 个维护文件格式、186 个源文件 mypy、评测审计和 schema 漂移全部通过；
- 评测审计的剩余警告已收敛为：2 个 unmappable、历史 replay 使用旧安全集、第二人工 pending、无未见盲测；唯一 pytest warning 仍是测试用短 HMAC key。

## 5. 后续边界

EVAL-11 已结束。新数据版本尚无正式检索、回答或安全成绩，历史 main-v3/main-v4 数字不能迁移。下一步可无费用推进证据类型与指定来源规则实现；EVAL-12、EVAL-22 等任何模型运行仍需逐次授权。
