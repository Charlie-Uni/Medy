# 记录 153：EVAL-11 付费复核、停止决策与 v6 草案

日期：2026-10-08。状态：**授权复核已安全停止；v6 草案自审通过，等待项目所有者裁决。**

## 1. 授权与实际执行

项目所有者授权：“授权 EVAL-11 复核，最多 1.95 USD”。执行边界固定为 `claude-opus-5`、high effort、每次 1 条、最多 6 次、单次 CLI 阈值 0.30 USD、不自动重试。授权文件 SHA-256 为 `29867e55fc3fcc1de6d9ba2e546cb24d5ccf530befe981bba391f0b59f08694a`。

| 次序 | 样本 | 结论 | 账本费用 |
| ---: | --- | --- | ---: |
| 1 | `ms-0197` | dispute | 0.074861 USD |
| 2 | `ms-0440` | agree | 0.270936 USD |
| 3 | `ms-0441` | agree | 0.162092 USD |
| 4 | `pc-0070` | dispute | 0.071173 USD |
| 合计 | 4 次 | 2 agree / 2 dispute | **0.579062 USD** |

全部 4 次都返回格式有效的 verdict；无 CLI 失败、无无效回复、无未知费用、无自动重试、无单次越界。剩余授权余额为 1.370938 USD。

`ms-0198` 和 `pc-0102` 未调用：它们分别是两个已争议父题的英文孪生，gold 输入缺陷相同。继续调用只会为已知问题重复付费。机器结果见 `revision-2026-10-08-v5/review/outcome_2026-10-08.json`。

## 2. 两项有效争议

### `ms-0197/ms-0198`

`chunker-v2` 在同一句的 `e.g.` 后切开了“initial evaluation of RMM”和 `within 12-24 months`。v5 把两侧强制写成两个 gold，但各自 evidence span 都不是完整条款；这是物理边界切分，不能据此声称两个语义证据单元。

完整“初步评价 + 12–24 个月”的对象与约束本身跨 chunk。若坚持现行 P1“key 同时保留对象与约束”，没有任何单一 `chunker-v2` chunk 可以完整覆盖它。因此 v6 建议撤回 v5 修订，保留 main-v4 的原 gold 和两个 `unmappable` miss。后续可在独立 chunker 重叠/边界实验中处理，不能在当前数据修订中伪造成功映射。

### `pc-0070/pc-0102`

v5 把 ICH E6(R3) 1.5.1 的同一句按 chunk 边界切为“保留义务导语”和“记录列表”，前者冗余，两个短 span 都不是完整条款。reviewer 建议有效：

- evidence span 使用完整 1.5.1 句 `[818,1147)`；
- key 使用页内唯一的六类记录列表 `[873,1019)`；
- 单一 gold 映射到 `7f268133-cfc5-47f1-857d-a138c0a04bcc`。

问题只问“列举了哪些例子”，列表 key 足以锁定答案；完整 span 保留 IRB/IEC 主语、适用要求和监管机关调阅条件。

## 3. 无争议修订

`ms-0440/ms-0441` 的 5 个共同必需 gold 均获 `agree`。它们覆盖适用条件和四类通常建议的相互作用研究，实际要求命中 3 个连续 chunk。两条 reviewer input、prompt 和 proposal 在 v6 中逐字保持一致，可复用本轮两个有效 verdict。

## 4. 付费 runner 缺陷

准备只运行 `ms-0441` 时发现：主集 runner 在首次创建 run 且传入 `--only` 时，验证了选项，却仍把整批 `set(all_ids)` 交给 `start_targeted_review`。这会误调用已暂停的 `ms-0198`。

修复：新增 `selected_ids()`，在生成任何 run 记录或模型调用前统一解析完整/定向选择；新 run 使用解析后的集合。增加回归测试覆盖首次定向、完整批次和未知 ID。修复后 31 项预算与选择测试通过，随后实际 `run_EN.json` 仅包含 `ms-0441` 的调用。

## 5. v6 草案

新草案位于 [revision-2026-10-08-v6](../../../evals/main_set/drafts/revision-2026-10-08-v6/README.md)：

- 基于冻结的 `main-v4-provisional`，不修改 v5 历史；
- 仅包含 `ms-0440/ms-0441` 和 `pc-0070/pc-0102` 四条修订；
- 12 个建议 gold 全部 mapped；
- `ms-0197-g1/ms-0198-g1` 明示保留为 unmappable；
- 投影后仍为 615 条，全部部门、来源语言、切片和文档上限配额满足；
- manifest SHA-256：`9eba65082184d9f9311287ed6af4309d616a08566e40ee83de936eb2609b5c3c`；
- proposals SHA-256：`f2b77ed5f2c647c06da5b8fefcff86129cf41f85ab879d8197cc87e057da80ed`。

页级机器审计 `checks_passed=true`、12/12 mapped、`quota_shortfalls={}`，见 [v6 审计 JSON](2026-10-08-implementation-153-eval11-v6-draft-audit.json)。

## 6. 当前人工门

建议项目所有者一次确认三点：

1. 两个 GVP gold 在 `chunker-v2` 下继续作为 miss 留在召回分母；
2. ICH E7 两题沿用已获 agree 的五组修订；
3. ICH E6(R3) 两题使用完整条款 span 加单一列表 key。

确认后，只需对两条新 `pc-*` reviewer input 重新做独立模型复核；本轮 ICH E7 的两个 agree 可以按精确输入哈希复用。第二独立人工仍未完成。

## 7. 自审与全量门禁

- 4 个 run/verdict 组合均可逐字重建实际 prompt，latest binding 与当前输入 hash 一致；允许不完整覆盖的 EN run 只包含明确选择的 `ms-0441`。
- 4 个 CLI capture 均存在、SHA-256 与账本元数据一致，文件权限为 0600；预算无未结算 reservation。
- v6 `annotation_revision --with-pages`：通过；4 proposals、12/12 mapped、无配额缺口。
- runner 定向选择与预算测试：31 passed。
- 首次直接 `make check` 得到 8 failed、1364 passed、336 skipped；8 项均由宿主继承的 `DEBUG=release` 被项目布尔配置读取导致。仓库历史规定用 `env -u DEBUG` 隔离该宿主变量，本轮没有放松 Settings 校验或改写 `.env`。
- 最终 `env -u DEBUG make check`：**1638 passed、70 skipped、1 warning**；ruff、430 个维护文件格式、186 个源文件 mypy、评测审计和 Schema 漂移全部通过。唯一警告仍为测试用短 HMAC key。
