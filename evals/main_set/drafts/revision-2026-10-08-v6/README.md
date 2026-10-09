# EVAL-11 修订草案 v6

状态：**项目所有者已确认；两条差量复核均 agree；probe v4 与 `main-v5-provisional` 已冻结。** v5 的付费复核执行 4 次后停止，v6 仅对真正变化的两条输入重新调用。

## 建议

1. `ms-0197/ms-0198`：撤回 v5 修订，保留 main-v4 原 gold 和 `unmappable` 状态。完整“初步评价 + 12–24 个月”事实跨 `chunker-v2` 边界，留待独立 chunker 实验。
2. `ms-0440/ms-0441`：沿用 v5 的 5 个共同必需 gold；两条独立复核均 `agree`。
3. `pc-0070/pc-0102`：采用 reviewer 建议的单一 gold。evidence span 保留完整 1.5.1 条款，key 只取六类记录列表，映射到一个现有 chunk。

结果是 4 个原失败 gold 被安全修复，2 个 GVP gold 继续作为 miss 留在分母。冻结数据尚未改写。

项目所有者已于 2026-10-08 回复 `确认 EVAL-11 v6 建议`，确认文件绑定 manifest、proposals 与 corpus edits 的精确哈希。`ms-0440/ms-0441` 的输入、提示和 verdict 哈希与 v5 完全一致，两个 agree 已按哈希复用。项目所有者随后授权 v6 差量复核上限 0.65 USD；`pc-0070/pc-0102` 均 agree，实际费用 0.290727 USD。最终主集映射为 580 mapped、2 unmappable，两个保留 miss 没有从分母删除。
