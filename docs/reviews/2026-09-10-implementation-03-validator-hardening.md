# 实现记录 03：校验器漏检修复与安装环境根因（2026-09-10）

按基线第 9 节交付格式。触发：决策人用临时合成集做反向测试，证明六类不合法数据仍能通过 frozen 校验，另有 CLI 在 `.venv` 下 `ModuleNotFoundError` 与记录措辞两个交付问题。

## 完成

| 问题 | 修正 | 回归测试 |
| --- | --- | --- |
| 文档索引与跨文件关系：重复 `source_hash` 被字典覆盖；重复 `document_key`、gold 版本错误、页码超过文档页数、corpus 与 manifest 版本不同均放行 | 建索引前检查 `source_hash`/`document_key` 唯一（PR-01）；`corpus.dataset_version` 必须等于 manifest（PR-01）；gold 的 `version_label` 必须等于文档、`page` 不得超过 `pages`（PR-04） | `test_duplicate_source_hash_is_rejected`、`test_duplicate_document_key_is_rejected`、`test_corpus_version_must_match_manifest`、`test_gold_version_label_and_page_range_are_checked` |
| PR-10：SHA256SUMS 同一路径先错后对仍放行 | 逐行按 `<64 hex>  <path>` 校验格式，拒绝重复路径、未知路径、乱序与缺末尾换行，先收集再比对，不再用字典覆盖 | `test_sha256sums_duplicate_path_and_malformed_line_are_rejected` |
| PR-12：映射 `extractor_version` 改成无关版本仍放行 | 比较映射与 manifest 的 `extractor`、`extractor_version`、`params_hash` 与 `normalization` | `test_mapping_extraction_and_normalization_must_match_manifest` |
| PR-05：draft 未提供页文本时错误偏移量、证据不含 key 也放行 | 不依赖页文本的检查（norm-v1 形式、包含关系、偏移长度）始终执行；仅缺页文本按模式降为警告 | `test_page_independent_anchoring_checks_run_in_draft_without_pages`、`test_missing_pages_is_only_a_warning_in_draft_but_error_in_frozen` |
| PR-08：query 等于另一条样本的 key 仍放行 | 与全集规范化 key_text 集合比较 | `test_query_equal_to_another_samples_key_text_is_rejected` |
| 输入处理：非 canonical、重复/乱序 ID 的 ACL 文件、缺末尾换行的 JSONL、非法 UTF-8 prompt 放行；JSONL 空行抛异常 | 严格 JSONL 装载：UTF-8 无 BOM、LF、末尾换行、无空行、逐行 canonical，解析失败返回带文件与行号的 PR-01 Finding；ACL 的 `probe_id` 唯一升序与 `derived_from_sample` 存在性（PR-02）；prompt 严格解码（PR-09）；manifest/corpus 解析失败返回 Finding | `test_jsonl_without_trailing_newline_and_blank_lines_report_findings_not_exceptions`、`test_non_canonical_jsonl_line_is_rejected`、`test_acl_probe_ids_and_references_are_checked`、`test_non_canonical_acl_probe_line_is_a_pr01_finding`、`test_invalid_utf8_prompt_and_corrupt_manifest_report_findings` |

SPEC 第 10 节的 PR-01、PR-02、PR-04、PR-05、PR-08、PR-10、PR-12 文字已同步到实现的检查范围；未新增规则编号。

## 安装环境根因

- 现象：`.venv/bin/python -m medops.evals.probe` 报 `ModuleNotFoundError: medops`，pytest 因 `pythonpath=src` 未暴露。
- 排查：`python -v` 显示 `Skipping hidden .pth file`；`ls -lO` 显示 `.venv` 内所有文件带 macOS `hidden` 标志；`chflags nohidden` 后数秒内标志被重新加上；`xattr` 显示 `~/Documents` 属于 iCloud Drive 文件提供者域。
- 结论：iCloud 会给点目录内的文件打 hidden 标志，CPython 3.11.16 起跳过隐藏 .pth，因此放在 `.venv/` 的 editable 安装在本机必然失效；非点目录不受影响。
- 处置：虚拟环境改为 `venv/`（`.gitignore` 已加）；Makefile 记录原因，`install` 后自动执行 `install-check`（在 `/tmp` 下导入包），`check` 也先跑 `install-check`；CI 增加同样的仓库外导入检查。本会话创建的 `.venv` 已删除。
- 实现记录 02 的“已提交仓库”改为“已创建、未提交”，并标注其中的 `.venv` 命令后来被证实不可用。

## 验证

```text
make check
  install-check           -> medops importable outside the repo
  ruff check src tests    -> All checks passed!
  mypy                    -> Success: no issues found in 15 source files
  pytest -q               -> 61 passed in 1.64s
env -u PYTHONPATH venv/bin/python -m medops.evals.probe /tmp/probe-draft --mode draft
  -> PASS (draft); errors=0 warnings=17
```

## 未完成

- 校验器仍未对真实数据集运行；探针集 v1 的三项语料门禁未变。
- 未勾选任何 checklist。

## 风险

- 严格 JSONL 规则意味着任何手工编辑样本文件都必须经 canonical 重写，工具链需提供重写命令（随后续标注工具实现）。
- 无新增已知安全风险。
