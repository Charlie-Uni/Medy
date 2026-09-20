# ADR-0009：入库文件格式（DOCX）与恶意文件策略

- 日期：2026-09-20
- 状态：已决（决策人 2026-09-20 授权实施方决定；可随时否决）
- 决策来源：[实现记录 41](../reviews/2026-09-20-implementation-41-delegated-decisions.md)；基线 5.1（"支持数字 PDF 和 DOCX""校验文件签名/MIME、大小上限、恶意文件和重复哈希"）、INV-DATA-05、INV-DATA-06、路线图 M1-09

## 决策

1. **DOCX 解析**：使用标准库 `zipfile` 读取 OOXML 包，`defusedxml`（PSF 许可）解析 XML；不引入 python-docx。理由：完全控制来源偏移与安全检查，减少依赖面。文本单元为段落（`w:p`，含表格单元格），标题由段落样式（`Heading N` / `標題 N` / `heading N`，或大纲级别）识别。
2. **DOCX 的页与章节语义**：DOCX 没有固定页。`chunks.page` 与 `chunk_spans.page` 对 DOCX 文档存放 **1 起的顶级章节序号**（第一个标题之前的正文为第 1 节），`chunks.section` 存放标题路径；`chunk_spans` 的字符区间相对该节的规范化文本。引用渲染时按 `source_objects.mime` 区分："第 N 页" 对 PDF、"第 N 节" 对 DOCX（INV-DATA-06 的 `page` 字段语义扩展为"来源定位单元"）。没有任何标题的 DOCX 无可靠章节，解析质量记为 `low_trust`（INV-DATA-05），不能激活。
3. **恶意文件策略（结构性门禁，进程内、必选）**：
   - PDF：出现 `/JavaScript`、`/JS`、`/OpenAction`、`/AA`、`/Launch`、`/EmbeddedFile`、`/RichMedia`、`/XFA`、`/SubmitForm`、`/ImportData` 任一即拒绝；`/URI` 链接允许。加密 PDF 拒绝。
   - DOCX：存在 `vbaProject.bin` 或 macroEnabled 内容类型、OLE/ActiveX 部件（`oleObject*`、`activeX*`）、非超链接的外部关系（`TargetMode="External"` 且类型非 hyperlink/image）、`DDE`/`DDEAUTO`/`INCLUDE*` 字段、附加远程模板 即拒绝；ZIP 炸弹防护：条目数 ≤ 2,000、解压总量 ≤ 200 MB、单条压缩比 ≤ 100、路径穿越拒绝。
   - 拒绝写应用日志（脱敏：只含规则名与来源哈希前缀），不写 `documents`。
4. **反病毒扫描（外部、按环境）**：可选 ClamAV `clamd` INSTREAM 扫描（TCP 或 Unix socket，`CLAMD_ADDRESS` 配置，超时固定）；`APP_ENV=prod` 必须配置，否则配置校验失败；dev/test 未配置时跳过并在入库审计 details 记 `av_scan: skipped`。不引入 clamd 客户端依赖，协议由本项目实现（INSTREAM 长度前缀分块）。
5. **文件大小与签名**：沿用现有 PDF 魔数与大小上限；DOCX 以 ZIP 签名 + `[Content_Types].xml` 含 `word/document.xml` 主部件判定，MIME 固定为 `application/vnd.openxmlformats-officedocument.wordprocessingml.document`。

## 批准边界

- 不做 OCR、不做版面分析；`.doc`（二进制 Word）、`.rtf`、`.odt` 不支持。
- 追踪修订（`w:ins`/`w:del`）按"接受全部修订"读取；批注忽略；此规则写入解析器版本。
- ClamAV 的部署（容器与病毒库更新）属 M3 部署基线。
