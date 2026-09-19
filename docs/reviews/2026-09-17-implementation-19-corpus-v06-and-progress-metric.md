# 实现记录 19：候选清单 v0.6（PV/CO 八条签字）、原件补齐与进度百分比口径

日期：2026-09-17。范围：落实决策人"剩下的任务全部同意"中的语料部分（八条 PV/CO 签字、原件下载核验与页文本抽取），并按其要求固定"离总目标百分之多少"的汇报口径。未修改基线、SPEC、Schema、代码逻辑；未提交 Git。**状态：待 Codex 审核。**

## 1. 候选清单 v0.6

[DEC-011-candidates-v0.6.json](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.6.json) / [.md](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.6.md)：cand-0009、0010、0011、0012、0013、0014（PV）与 cand-0017、0018（CO）`reviewer_decision=eligible`，`reviewer_note` 记录许可依据（EMA 网站声明 / 美国政府公共领域 / ICH 公共许可 / TFDA 开放宣告）与入库前置动作；cand-0018 为 FDA 草案，version_label 标 draft。其余字段与 v0.5 逐字相同。Schema 校验与 v0.1～v0.6 跨版本一致性测试通过（8 项）。

已签字 `eligible` 共 18 条；探针集 v1 主体 16 份：MA 5、PV 8、CO 3，满足 SPEC 3.4 的每部门至少 3 份与至少 10 份。

## 2. 原件补齐

八份 PDF 按 `pdf_url` 下载，均为有效 PDF。候选清单此前只记录了页数、未记录这八份的 sha256，因此本次下载的哈希是首个持久记录（`SOURCES.index.json` 中 `matches_candidate_list_hash=false`、`candidate_list_recorded_hashes=[]` 如实标注）。页数与候选清单记录逐一相符，作为"同一文档"的间接证据：

| 候选 | sha256 前 12 位 | 字节 | 页数（清单记录） | 抽取告警 |
| --- | --- | ---: | ---: | ---: |
| cand-0009 GVP VI | f27a7f0d678b | 2,115,278 | 144（144） | 0 |
| cand-0010 GVP IX | 801755430dbf | 290,012 | 25（25） | 0 |
| cand-0011 FDA 申办方安全报告 | 7124849af041 | 534,674 | 43（43） | 0 |
| cand-0012 ICH E2A | 1c095d804192 | 150,346 | 12（12） | 0 |
| cand-0013 ICH E2F | 7912d4d0f2b5 | 342,411 | 35（35） | 0 |
| cand-0014 TFDA 通報表填寫指引 | f5f597affd02 | 891,371 | 19（19） | 0 |
| cand-0017 ICH E6(R3) | e6ce19e36ce7 | 833,486 | 86（86） | 0 |
| cand-0018 FDA 方案偏离草案 | 3b172d83fd53 | 281,421 | 13（13） | 0 |

`v1/sources/` 现有 18 份原件，`v1/pages/` 现有 18 个 source_hash 目录（既有 10 份不可变目录未被重写，`extraction.json` 一致）。两目录均在 `.gitignore`。

## 3. 进度百分比口径（决策人要求，自本记录起每个阶段汇报）

- 分子：[任务知识对照](../TASK_KNOWLEDGE_MAP.md) 中 79 个 P0 任务行的状态加权和，已实现计 1、部分计 0.5、阻塞与待做计 0。
- 分母：79（P0）；另报按 99 个基线复选项计的数值（P1/P2 与最终验收 9 项均为 0）。
- 状态只依据实现记录中的证据变更；基线第 8 节的勾选保持 0，直到某项按第 9 节验收标准整项通过。
- 这是进度启发式，不是完成度承诺：各项工作量不等，最终验收是第 11 节九条门禁的二元结果。
- 机械一致性：`tests/unit/docs/test_baseline_roadmap_consistency.py` 重算该百分比并与路线图中的数字比对，两者不一致即测试失败。

本记录时点：M0 10/11、M1 6.5/21、M2～M5 0/47，**P0 加权进度 20.9%（16.5/79）**，按 99 项计 16.7%。

## 4. 验证

```text
tests/unit/evals/test_candidate_lists.py -> 8 passed（v0.1～v0.6）
下载 8/8 为有效 PDF；页数与清单记录 8/8 相符；抽取告警均为 0
env -u PYTHONPATH make check -> 见本轮汇报（含新增进度一致性测试）
```

## 5. 自审（基线 §9）

1. 需求：只做签字登记、原件获取与汇报口径；未改契约、未建表、未标注。
2. 逻辑：哈希无先例即如实标注，不伪造"一致"。
3. 安全：原件与页文本在忽略目录；无密钥。
4. 契约：候选清单符合 Schema；版本追加不覆盖。
5. 测试：清单测试与进度一致性测试。
6. 可观测：无。
7. 简洁性：进度计算复用知识对照的既有状态列，不新增数据源。
8. 验证：见第 4 节。
9. Checklist：基线勾选保持 0。
