# 实现记录 43：M1-09 收口——DOCX 入库、结构性恶意文件门禁与 clamd 钩子（ADR-0009）

日期：2026-09-20。承接记录 41 阶段 3。M1-09 剩余三项（DOCX、恶意文件扫描、同源管理员确认）中，管理员确认已在记录 40 完成；本轮按 [ADR-0009](../adr/ADR-0009-docx-and-malicious-file-policy.md) 完成 DOCX 与恶意文件两项。

## 1. 编码前记录

- 格式判定只看文件签名（PDF 魔数；ZIP 魔数 + `[Content_Types].xml` + `word/document.xml`），不看扩展名；大小上限、声明字节数与哈希比对沿用。
- 结构性门禁（必选、进程内、写入前）：PDF 同时扫描原始字节中的名字（解码 `#xx` 转义）与 pypdf 解析后的对象图（目录、Names 树、页、注释、AcroForm），命中 JavaScript/JS、OpenAction、AA、Launch、EmbeddedFile(s)、RichMedia、XFA、SubmitForm、ImportData、Encrypt 即拒绝，解析失败亦拒绝（失败关闭）；`/URI` 与形似名（如 `/AAPL:Keywords`）放行。DOCX：ZIP 炸弹上限（条目 ≤2,000、解压总量 ≤200 MB、压缩比 ≤100、路径穿越、加密条目）先于任何部件读取；宏（`vbaProject.bin`/macroEnabled 内容类型）、OLE/ActiveX 部件、非超链接的外部关系与附加模板、`DDE/DDEAUTO/INCLUDE*/IMPORT/LINK` 字段码、`altChunk`、`w:object` 均拒绝；XML 用 `defusedxml` 解析，实体攻击作为不可解析拒绝。
- 反病毒：`clamd` INSTREAM 协议自行实现（无客户端依赖；4 字节长度前缀分块、零长终止、NUL 结尾回复），固定超时；未配置时记 `av_scan: skipped`（dev/test），`APP_ENV=prod` 未配置 `CLAMD_ADDRESS` 即配置校验失败；已配置但不可用时拒绝入库（失败关闭）；命中即拒绝并写明签名。
- DOCX 解析：标准库 `zipfile` + `defusedxml`；段落（含表格单元格按行以 " | " 连接）、修订按"接受全部"（保留 `w:ins`、丢弃 `w:del`）；标题由样式 id/名称（`Heading N`、`heading N`、`標題 N`、`标题 N`）或大纲级别识别；顶级标题切分章节，首个标题前的正文为第 1 节；`chunks.page`/`chunk_spans.page` 对 DOCX 存章节序号，`chunks.section` 存标题路径，字符区间相对该节规范化文本；无标题 → `low_trust`，不可由复核人放行。
- 审计：`ingest` details 新增 `format`、`structural_scan`、`av_scan{status, scanner, signature}`、`sections`；`source_objects.mime` 区分 PDF/DOCX；`ingestion_jobs.parser_version = "docx-ooxml docx-ooxml-v1"`、`extraction_params_hash` 为 DOCX 解析参数的 canonical 哈希。

## 2. 实现

- [filecheck.py](../../src/medops/ingestion/filecheck.py)（`sniff`、`scan`、`scan_pdf`、`scan_docx`、`zip_limits`）、[docx.py](../../src/medops/ingestion/docx.py)（`extract_sections`、`Section`、`PARAMS_HASH`）、[av.py](../../src/medops/ingestion/av.py)（`Scanner` 协议、`NoScanner`、`ClamdScanner`、`ScanUnavailable`）。
- [pipeline.py](../../src/medops/ingestion/pipeline.py)：`validate_file` → `check_malicious_content` → 按格式抽取；`ingest_document(..., scanner=)`；DOCX 章节标签回填到 chunk。[load.py](../../src/medops/ingestion/load.py)：`<hash>.pdf` 或 `<hash>.docx`，`CLAMD_ADDRESS` 配置时自动启用 clamd，`--no-av` 显式跳过（审计记 skipped）。
- 配置：`Settings.clamd_address`（格式校验、空即未设、prod 必填）、`Settings.model_cache_dir`；`.env.example` 同步。依赖：`defusedxml==0.7.1`（PSF）进入 `requirements.lock`。

## 3. 测试

- 单元 [test_filecheck.py](../../tests/unit/ingestion/test_filecheck.py)（14）：签名嗅探不信任文件名；干净 PDF/DOCX 放行；8 种 PDF 主动内容（含十六进制转义名）命中；形似名与 URI 放行；加密/不可解析拒绝；DOCX 宏、OLE、ActiveX、外部模板/OLE 关系拒绝，外部超链接放行；DDEAUTO/INCLUDETEXT/LINK 字段拒绝而 PAGE 放行；压缩比、路径穿越、条目数、损坏 ZIP；XXE 实体攻击报为不可解析而非展开。
- 单元 [test_docx_extract.py](../../tests/unit/ingestion/test_docx_extract.py)（4）：顶级章节与嵌套路径、表格行、修订接受、样式名/大纲级别/中文样式名标题、无标题警告、空文档与损坏包拒绝。
- 单元 [test_av_clamd.py](../../tests/unit/ingestion/test_av_clamd.py)（3，本地假 clamd 服务器）：跨 64 KiB 边界的分块逐字节到达、clean/FOUND 判定与签名、不可达与畸形回复抛 `ScanUnavailable`、地址格式校验、`NoScanner` 记 skipped。
- 集成 [test_ingestion.py](../../tests/integration/test_ingestion.py) 新增 5：DOCX 入库后 `page` 为章节序号、`section` 为标题路径、表格文本入 chunk、字符区间相对章节文本逐条成立、MIME/解析器版本/参数哈希、审计 details；无标题 DOCX 为 low_trust 且复核放行无效；宏 DOCX、DDE DOCX、含 JavaScript 的 PDF、纯文本文件均在任何写入前拒绝；注入的感染/不可用/干净扫描器分别拒绝、拒绝、放行并记录；loader 解析 `.docx`。配置测试：prod 无 `CLAMD_ADDRESS` 拒绝、格式校验、空值即未设。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0，**836 passed**（614 单元 + 222 集成；含本轮同时完成的向量阶段测试，见记录 42）。

## 4. 自审（基线 §9）

1. 需求：基线 5.1 "支持数字 PDF 和 DOCX""校验文件签名/MIME、大小上限、恶意文件"三项均落地；INV-DATA-05 对无章节 DOCX 生效；INV-DATA-06 引用字段对 DOCX 有明确语义。
2. 逻辑：门禁全部在写入前；ZIP 上限先于部件读取；解析失败即拒绝。
3. 安全：`defusedxml`；不信任扩展名；clamd 不可用时不放行；prod 强制扫描；拒绝信息只含规则名。
4. 契约：`ingest_document` 新增可选 `scanner`；`validate_pdf` 保留为 `validate_file` 的 PDF 专用包装。
5. 测试：新增 21 单元 + 5 集成 + 配置测试扩展。
6. 可观测：审计 details 记录格式、结构扫描与 AV 判定。
7. 简洁性：三个模块各一职责；无新框架。
8. 验证：数字来自 pytest 输出。
9. Checklist：M1-09 部分 → 已实现（ClamAV 部署随 M3 部署基线）。

## 5. 剩余

ClamAV 容器与病毒库更新（M3 部署基线）；DOCX 页眉/页脚/脚注不入库（ADR-0009 批准边界）。
