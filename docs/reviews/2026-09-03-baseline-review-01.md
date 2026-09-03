# 第一轮基线审核记录（2026-09-03）

| 项 | 内容 |
| --- | --- |
| 审核对象 | `docs/ENGINEERING_BASELINE.md` v0.1、`README.md` |
| 对照来源 | [MedOps Copilot 项目设计文档 v0.1](../source/MedOps_Copilot_项目设计文档_v0.1.pdf)，SHA-256 `2c72fb7fe6fbf4995d49ad71970c508303805885e7742c7cf6864cad23710f42`，309,989 字节，8 页；校验值见 [SHA256SUMS](../source/SHA256SUMS) |
| 审核人 | Claude（Fable 5.1） |
| 决策人 | Qihan Zhu |
| 结论 | 审核结论成立；9 项技术问题全部接受；8 项事项已拍板；基线升为 v0.2 |
| 仓库状态 | 审核时无代码、migration 或依赖文件，只有 README 与基线；本轮结束仍未提交 |

## 1. v0.1 机械核对结果

| 检查项 | 结果 |
| --- | --- |
| 不变量数量 / ID 唯一 | 29 / 无重复 |
| checklist 数量 / 已勾选 | 90 / 0 |
| 待决策项 | 9（DEC-001 至 DEC-009） |
| 设计文档 F1–F6、非功能指标、4.1–4.6 约束、里程碑映射 | 全部有映射 |
| Skill 风险级别与设计一致 | 一致 |
| 设计 PDF 可追溯 | 否（仅按文件名引用，文件不在仓库） |

## 2. 技术问题与处置

| # | 问题 | 决策后处置 | v0.2 落点 |
| --- | --- | --- | --- |
| 1 | `operation_key` 只含 `policy_version`，与 5.10 单独传播的 `retrieval_version` 不一致；只改检索参数的回放会命中同一 key 并复用旧结果 | key 纳入 `policy_version`、`retrieval_version`、`skill_version_set`、模型配置版本；回放使用独立 `replay_run_id` | 3.2，M2 checklist |
| 2 | `hash(a + b + c)` 无分隔、无规范化，存在歧义 | `SHA-256(operation_scope \x1f run_id \x1f node_name \x1f canonical_json(...))`，canonical_json 为 UTF-8、键排序、稳定数字/空值表示 | 3.2，M0 checklist |
| 3 | `source_hash` 校验只是 JOIN，送入模型的 chunk 正文未校验 | 三级哈希：`source_hash`、`chunk_content_hash`、`evidence_text_hash + offsets`；Verifier 重算比对；`evidence_log` 存 expected/observed；定期从不可变源重新解析或校验 extraction manifest | 3.3，4.2，M1/M2 checklist |
| 4 | 3.4 过滤引用了 `integrity_status`、`parse_quality`，但没有落到表上；`effective_from` 空值语义未定义 | `source_objects.integrity_status`、`documents.parse_quality`、`documents.source_object_id`、`documents.active_ingestion_job_id`；active 文档 `effective_from` 非空；`effective_to IS NULL` 表示长期有效 | 3.4，4.2，M1 checklist |
| 5 | 未提及中文分词；PostgreSQL 默认 parser 不切中文 | M1 增加 tokenizer 选择、词典版本与专项评测；DEC-001 判据扩展为中文药名、剂量单位、否定词、时间窗、方案编号、中英混排 | 3.6，M1 checklist，DEC-001 |
| 6 | pgvector 在 ACL/状态/生效时间过滤后候选不足，受限部门召回下降 | 过滤进入数据库查询与 RLS；候选不足时自适应 over-fetch 或 iterative scan；Recall 按 MA/PV/CO 分别报告 | 3.7，INV-AUTH-02，M1 checklist |
| 7 | 推荐 RLS 但缺运行前提（连接池身份注入、owner/superuser 旁路、FORCE RLS） | 写明 8 条运行条件并要求集成测试覆盖连接池复用与跨部门隔离 | 3.7，M1 checklist |
| 8 | 设计 4.4 的整次问答 Token 硬上限丢失；设计 4.3 的 Prompt 来源约束未体现 | 新增 `INV-HAR-08` 整条 Trace Token/成本预算，超限先裁剪低价值 Evidence，仍不足则升级；`INV-HAR-05` 补充 seed/fallback Prompt 与生产来源规则 | 2.4，M2 checklist |
| 9 | “不可逆标识”若为无盐哈希可被字典还原；Idempotency-Key 缺作用域、请求哈希、冲突语义、TTL | surrogate ID 或带密钥 HMAC-SHA-256 并支持轮换；Idempotency scope 为 `principal + route + key`，存 canonical request hash，同 key 不同 payload 返回 422，TTL 不少于 24 小时且不短于任务生命周期 | INV-OBS-02，3.2，M3 checklist |
| 附 | 设计 schema 固定 `vector(1024)`，在 DEC-002 前锁定模型 | DEC-002 完成前不建固定维度 migration；ADR 后生成确定性 migration 并记录模型、维度、归一化、版本；维度切换用新列/新索引与后台重建 | 3.8，DEC-002，M1 checklist |

## 3. 决策事项

| # | 事项 | 决策 | v0.2 落点 |
| --- | --- | --- | --- |
| 1 | BM25 是否为 P0 硬门禁 | 不强制 BM25 公式，强制精确词法召回达标；首选 PostgreSQL FTS + 中文 tokenizer；代码与对外描述不得把 FTS 写成 BM25；真 BM25 及其许可证作为 P1 ADR | 3.1，7.1，M1/P1 checklist，DEC-001 |
| 2 | 非 PDF 来源内容的归属 | `300-500` 份文档来自项目描述，保留 P0；`INV-SAF-05`、Idempotency-Key 保留 P0 并标记“基线新增”；非 root 镜像、固定依赖、健康检查、worker 重启不丢任务保留 P0；SBOM、镜像扫描、完整备份恢复演练、五类故障演练降为 P1；P0 只保留模型超时、worker 重启、队列重复消费故障测试 | 0，2.1，3.2，5.12，7.1，M3/M5/P1 checklist |
| 3 | Recall@5 口径 | 严格宏平均 Recall；冗余/等价 Evidence 不重复计入 required gold；另报 Hit@5，不得称为 Recall@5 | 5.9，M1 checklist，第 11 节 |
| 4 | Loop 门禁统计有效性 | 保留点估计硬门禁；至少 200 条唯一 Trace，含随机性流程独立运行 3 次，paired comparison，bootstrap 95% CI 必报但不作硬门禁；样本少于 30 的切片标记“样本不足”；安全指标取三次最差值 | 5.8，M4 checklist |
| 5 | `source_hash` 去重范围 | `source_objects.source_hash` 全局唯一；多 document/family 可显式引用同一 source object，需管理员确认并审计；ACL 绑定 document/version，原文读取必须经授权 document 关系 | 3.3，M1 checklist |
| 6 | MCP 传输与鉴权 | 生产 Streamable HTTP + OIDC/OAuth bearer token，校验 issuer/audience/expiry/signature；stdio 仅本地开发与测试，不连生产文档库或只用固定低权限服务身份；`dept/scopes` 不接受参数声明 | INV-AUTH-04，5.7，M3 checklist |
| 7 | 身份提供方 | 新增 DEC-010；架构保持 OIDC 兼容；`sub` 识别用户，部门/权限由服务端映射，group claim 经 allowlist；开发环境用测试签发密钥与合成身份 | INV-AUTH-01，5.7，DEC-010 |
| 8 | 设计 PDF 入库 | 存为 `docs/source/MedOps_Copilot_项目设计文档_v0.1.pdf` 与 `docs/source/SHA256SUMS`；后续版本新增文件不覆盖；基线改用仓库相对链接 | 基线头部，`docs/source/` |

## 4. 本轮修改清单

- `docs/ENGINEERING_BASELINE.md`：v0.1 升为 v0.2，34 处替换，涉及头部、第 0 节、2.1–2.5、3.1–3.8、4.2、5.7、5.8、5.9、5.12、7.1、M0–M5 与 P1 checklist、DEC 表、第 11 节。
- `docs/source/MedOps_Copilot_项目设计文档_v0.1.pdf`：从源文件复制，字节数与 SHA-256 与决策中给出的值一致。
- `docs/source/SHA256SUMS`：`shasum -a 256 -c` 通过。
- `docs/reviews/2026-09-03-baseline-review-01.md`：本文件。
- `README.md`：未改动。

## 5. v0.2 复核结果

| 检查项 | 结果 |
| --- | --- |
| 不变量数量 / ID 唯一 | 30 / 无重复（新增 `INV-HAR-08`） |
| checklist 数量 / 已勾选 | 95 / 0（M0 +1、M1 +1、M2 +1、P1 +2） |
| 待决策项 | 10（新增 DEC-010；DEC-001、DEC-002 已改写） |
| 代码围栏 | 14 个围栏行，配对 |
| 相对链接 | `source/` 两处与 `reviews/` 一处均可解析 |
| PDF 校验 | `shasum -a 256 -c SHA256SUMS` 输出 OK |
| 目标值与实测值 | 全部仍为目标值，无实测占位 |

## 6. 遗留事项

以下事项的处置见 [第二轮审核记录](2026-09-03-baseline-review-02.md)。

- 并发重复 `Idempotency-Key` 请求返回原 task 还是 `409`，M3 在 OpenAPI 中固定为其一。
- DEC-010 的 ADR 待写入 `docs/adr/`。
- 项目描述文本未入库；若需追溯，建议另存为 `docs/source/` 下的文本文件并登记校验值。
- 本轮所有改动均未提交到 Git。
