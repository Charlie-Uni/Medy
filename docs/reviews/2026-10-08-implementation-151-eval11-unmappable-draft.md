# 记录 151：EVAL-11 unmappable gold 修订草案

日期：2026-10-08。状态：**草案自审通过，等待项目所有者裁决；未调用模型，未改写冻结数据。**

## 1. 问题定位

`main-v4-provisional` 的 574 个 gold 单元中有 6 个 `unmappable`。它们并非缺少原文或索引，而是 3 组中英文孪生题的单一 `key_text` 跨越 `chunker-v2` 的物理边界：

| 语义案例 | 样本 | 跨块情况 |
| --- | --- | --- |
| GVP Module XVI 评价时间点 | `ms-0197`、`ms-0198` | “initial evaluation”位于前块，`12-24 months` 与“within 4 years”位于后块 |
| ICH E7 药物相互作用研究 | `ms-0440`、`ms-0441` | 适用条件与四类通常建议研究分布在 3 个连续块 |
| ICH E6(R3) IRB/IEC 记录 | `pc-0070`、`pc-0102` | 保留义务的主语位于前块，完整示例列表位于后块 |

现行 `gold-groups-v1` 规定：不同 gold 组共同必需；同一组内多个 chunk ID 是可替代证据，命中任一即可。因此不能把跨界片段简单塞入同一组的多个 chunk ID，那会把“共同必需”错误改成“任选其一”。

## 2. 建议修订

- `ms-0197/ms-0198`：每题由 1 个跨界 gold 改为 2 个共同必需 gold，分别覆盖初步评价上下文及 `12-24 months`/`within 4 years` 时间点。
- `ms-0440/ms-0441`：每题改为 5 个共同必需 gold，分别覆盖适用条件、digoxin/口服抗凝、肝酶诱导或抑制、CYP450 抑制剂、其他预期合用药。
- `pc-0070/pc-0102`：每题改为 2 个共同必需 gold，分别覆盖 IRB/IEC 的保留义务和六类记录示例。

共 6 条题目、18 个新 gold 单元；18/18 均由现有 `chunker-v2` chunk 完整覆盖。query、来源、版本和答案范围不变。`ms-0440/ms-0441` 仍要求 3 个连续 chunk，首组保留原 1542 字整体审阅上下文，因此 `long_context` 仍为真，主集最低配额没有变化。

草案位于 [revision-2026-10-08-v5](../../../evals/main_set/drafts/revision-2026-10-08-v5/README.md)，机器裁决清单位于 [unmappable_gold_worklist-v1.json](../../../evals/review/unmappable_gold_worklist-v1.json)。

## 3. 排除的做法

- 不删除 6 个失败项，也不在当前 v4 映射中手填成功状态。
- 不把一个 gold 的多个 chunk 错当成共同必需。
- 不把 key 缩成缺少主语或条件、无法与其他组共同支持完整答案的片段。
- 不在本项中升级全局 chunker；全局 chunker 变化会重建全部 chunk ID、索引和 gold 映射，应独立做消融与迁移评估。
- 不复用旧人工或模型意见；修订后的 reviewer input 已变化。

## 4. 来源与映射核验

草案从只读归档 `main-v1-provisional/chunks.snapshot.json` 取 3 份文档相关页的 chunk ID。对 3 份文档的全部本地页重新运行 `norm-v1 + chunker-v2`，归档 span 集合与新生成 span 集合逐项相等。随后检查每个建议 key：

1. 在归一化页内只出现一次；
2. 位于声明的 evidence span 内；
3. 由且仅由一个同来源、同版本、同页 chunk 完整覆盖；
4. 中英文孪生题除 `gold_id` 外证据完全一致；
5. 投影后的 615 条样本仍满足全部部门、语言、切片与文档上限配额。

机器审计：`checks_passed=true`、`page_validation=passed`、18 mapped、`quota_shortfalls={}`，见 [记录 151 JSON](2026-10-08-implementation-151-eval11-draft-audit.json)。

## 5. 本轮遇到并修复的错误

| 现场错误 | 原因 | 修复 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'jsonschema'` | 首次误用系统 Python；项目依赖安装在仓库 `venv/` | 改用 `venv/bin/python`；首次失败发生在导入阶段，未写入草案文件 |
| `error: 'action'` | 新 worklist 初版字段写成 `recommended_action`，而通用修订校验器读取 `action` | 改回既有 worklist 契约并重算 decision-source hash |
| `key_text ... is too long` | ICH E7 条件 key 为 247 字，超过 Schema 的 200 字上限 | 缩为 178 字的唯一条件锚点；完整 evidence span 仍保留结论 |
| `ms-0440-g1: key offset mismatch` | 缩短 key 后人工填写的起点少 2 个字符 | 从规范化页重新定位为 `[1534,1712)`，随后页级校验通过 |
| `slice/long_context: 18 < 20` | 初版把跨块题拆成短 span 后错误移除了两条 `long_context` | 保留原 1542 字整体审阅上下文；共同必需 key 仍分别映射 3 个块，最终配额无缺口 |

## 6. 验证与当前门

- `medops.evals.annotation_revision --with-pages`：通过；6 proposals、3 targets、3 linked twins、18/18 mapped。
- 当前主集、探针和正式映射均未改写；`main-v4-provisional` 的 6 个失败项在裁决前继续计入分母。
- 下一步需要项目所有者确认这 3 组建议。确认后才会生成绑定哈希的 human confirmation，并单独申请修订后独立 LLM 复核的调用次数与费用授权。
