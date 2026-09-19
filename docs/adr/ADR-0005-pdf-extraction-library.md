# ADR-0005：探针集页文本抽取库选型

- 日期：2026-09-12
- 状态：已批准
- 决策来源：实现记录 11 第 4 节第 5 项提出“M1 正式抽取需要选定 PDF 抽取库并进入锁文件”，项目负责人于 2026-09-12 回复“全部批准”。

## 决策

1. 探针集来源 PDF 的页文本抽取使用 `pypdf`（BSD-3-Clause，纯 Python，无系统依赖），锁定于 `requirements.lock`（本次为 6.18.1，带 SHA-256）。
2. 抽取入口固定为 [extract.py](../../src/medops/evals/probe/extract.py)：`extractor=pypdf`、`extractor_version` 取安装版本、`params={"extraction_mode": "plain"}`、`params_hash` 按基线 3.2 的 canonical JSON 计算；输出 `<pages_dir>/<source_hash>/<page>.txt` 与 `extraction.json`，与校验器 `PageTextProvider` 的读取约定一致。页文本不做规范化，norm-v1 由校验器施加。
3. 输出目录按 `source_hash` 不可变：重复运行必须逐字节复现，内容不同或出现多余文件即报错，不覆盖。

## 批准边界

- 只覆盖探针集与评测语料的离线抽取；生产 ingestion 的解析器、OCR、版面分析与表格抽取不在本决策内，需要时另开 ADR。
- 无文本层的扫描件不做 OCR；此类页按 SPEC §4 不得作为 gold 来源。
- 抽取参数变更即新的 `extraction_version`，已标注样本按 SPEC §6 重新定位或升版。
- 不包含 Git 提交、推送或部署授权。
