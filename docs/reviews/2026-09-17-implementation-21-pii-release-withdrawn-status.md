# 实现记录 21：四份 PII 误报文档放行入库、迁移 0004 `withdrawn` 终态、`effective_from` 口径

日期：2026-09-17。范围：落实决策人对[实现记录 20 第 4 节](2026-09-17-implementation-20-chunker-and-ingestion.md)三项的批复（"三条都同意"）。未修改基线、SPEC、Schema 规则；未提交 Git。**状态：待 Codex 审核。**

## 1. 决定一：四份 PII 命中文档放行

- corpus.json v1 重新生成为 16 份（MA 5、PV 8、CO 3）。四份的 `pii_scan.method` 写明：`pii-rules-v1` 命中处经决策人 2026-09-17 复核为机构联系邮箱或指南数据要素名称、非个人数据，入库以审计留痕；`notes` 同步标注。规则集不改。
- 以 `--accept-pii <key>=<理由>` 入库，理由原文："决策人 2026-09-17 复核：命中为机构联系邮箱或指南数据要素名称，非个人数据"。每份写一条 `pii_review_override` 审计，`details.hits` 保存命中原文。
- 第一次通过 `make load-corpus ARGS=...` 传带空格的理由被 shell 拆分导致 argparse 报错、零写入；改为直接调用 CLI 并加引号后成功。Makefile 的 `ARGS` 只适合无空格参数，已在本记录注明。

| document_key | 部门 | chunk 数 | pii 命中（已复核） |
| --- | --- | ---: | ---: |
| ema-gvp-module-vi-rev2 | PV | 881 | 4 |
| ema-gvp-module-ix-rev1 | PV | 153 | 4 |
| fda-sponsor-safety-reporting-2025 | PV | 298 | 4 |
| fda-protocol-deviations-draft-2024 | CO | 84 | 3 |

本机事实平面现为 16 份草稿文档、2,661 个 chunk、16 条 `ingest` 与 4 条 `pii_review_override` 审计。

## 2. 决定二：`withdrawn` 终态（迁移 0004）

- `doc_status` 增加 `withdrawn`。新增枚举值不能在同一事务内被约束表达式引用，因此 `ALTER TYPE ... ADD VALUE` 放在 Alembic 的 `autocommit_block()` 中执行，其余语句在事务内。
- 状态机改为 draft → active → archived，另加 draft → withdrawn；withdrawn 为终态且只读（任何列的 UPDATE 都拒绝）；仍需 `SET LOCAL medops.actor`，审计触发器照常写入 from/to/actor/reason；不可物理删除（删除守卫仍只放行 draft）。
- 约束 `documents_non_draft_has_effective_from` 放宽为 `status in ('draft','withdrawn') or effective_from is not null`。
- RLS 策略 `documents_dept_read` 改为 `status in ('active','archived')`，withdrawn 与 draft 一样对 app/readonly 不可见。
- 降级：恢复旧守卫、旧策略、旧约束；PostgreSQL 无法删除枚举值，标签保留，存在 withdrawn 行时拒绝降级；完整往返仍干净，因为 0001 降级会删除整个类型。
- 领域契约与 MCP：`DocStatus` 增加 `withdrawn`；`Evidence` 拒绝 draft 与 withdrawn；MCP `_visible` 对两者一律不暴露；导出 Schema 随之更新（`make schemas`，漂移检查通过）。设计文档的三态在此成为四态，依据是决策人 2026-09-17 的选择（方案 A）。

## 3. 决定三：`effective_from` 取值口径

已写入路线图 M1-11 行，M1-11 发布流实现时执行：说明书取文内修订日期，其次 TFDA 许可证异动日期，再次 PDF 元数据日期，并在备注写明取自哪一层；指南取文内发布或生效日期。本轮未激活任何文档。

## 4. 验证

```text
tests/integration/test_withdrawn.py -> 4 passed：枚举顺序；无 actor 拒绝、draft→withdrawn 写审计（含 reason）、
  withdrawn 后任何状态变更与任何列修改均拒绝、不可删除、active/archived 不能 withdrawn；draft→active 仍正常；
  withdrawn 文档及其 chunk 对 app/readonly 不可见、admin 可见
tests/unit/domain、tests/unit/mcp -> withdrawn 不能作证据、不能暴露（2 项新增断言）
tests/integration -> 64 passed（含往返测试：head 0004）
env -u PYTHONPATH make check -> ruff 通过；format-check 101 文件；mypy 46 文件；pytest 362 passed（298 单元 + 64 集成）；schemas 无漂移
本机开发库：先按旧 0004 升级，修正后 downgrade 0003 再 upgrade head，约束定义已为放宽版；16 份文档、2,661 个 chunk 保留
```

## 5. 未完成

- M1-11 发布流（激活、归档、同事务 outbox）未实现，`effective_from` 口径待其落地。
- 探针集 v1 的 manifest.json、review_prompt.md、samples.jsonl 尚未起草；下一轮开始样本起草供决策人确认。

## 6. Codex 审核焦点

- 0004 的 `autocommit_block()` 用法：若 ADD VALUE 之后的语句失败，枚举值已提交而其余回滚，重跑是否幂等（`if not exists`、`drop policy if exists`、`create or replace` 均幂等，约束 drop/add 在事务内）。
- withdrawn 只读守卫用 `row(new.*) is distinct from row(old.*)` 判断，是否会误伤纯 `status_changed_at` 之类由触发器自身写入的列（该守卫在状态未变且任何列变化时触发，符合"终态只读"）。
- PII 覆盖理由是否应该要求引用复核记录编号而不是自由文本。

## 7. 自审（基线 §9）

1. 需求：只落实三项批复；未新增门禁、未改规则集。
2. 逻辑：终态只读与不可见有正反测试；约束放宽只针对 draft/withdrawn。
3. 安全：覆盖必须留痕且理由入审计；withdrawn 对业务角色不可见。
4. 契约：DocStatus、Evidence、MCP 可见性、导出 Schema 同步。
5. 测试：单元与集成均覆盖，往返测试通过。
6. 可观测：审计含 reason 与命中原文。
7. 简洁性：一个迁移、枚举一处、三行契约改动。
8. 验证：见第 4 节；未验证项：远端 CI。
9. Checklist：基线勾选保持 0；P0 加权进度不变 22.8%。
