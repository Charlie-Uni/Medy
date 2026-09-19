# 第六轮记录：语料来源与许可准入（DEC-011）与候选清单 v0.1（2026-09-09）

| 项 | 内容 |
| --- | --- |
| 触发 | 决策人对来源范围、许可标准、PV 补足的三项决定 |
| 执行 | Claude（Fable 5.1）；候选检索由三个后台代理（MA/PV/CO）完成，主会话抽查 |
| 决策人 | Qihan Zhu |
| 结论 | 政策已落地为 ADR-0003 与 DEC-011；候选清单 v0.1 共 25 条，其中预判 eligible 10 条，但没有任何简体中文文档达到 eligible，探针集 v1 的语料最低要求尚未满足，需要决策人对 6 个问题拍板 |

## 1. 编号更正

此前对话与第五轮记录把“公开语料清单与许可确认”称为 DEC-005，属于误标：基线中 DEC-005 一直是“初始医学术语来源”。本轮新增 DEC-011 承载语料来源与许可准入政策，DEC-005 保持原义。第五轮记录中的 DEC-005 表述属历史记录，不作改动，以本记录为准。

## 2. 政策落地（基线 v0.6）

| 决策 | 落点 |
| --- | --- |
| 权威来源白名单 + 逐文档许可门禁；排除聚合站、转载站、网盘 | ADR-0003 §1；SPEC 3.1 |
| 四级许可状态；政府公开信息本身不足以通过；只有 eligible 进入探针集 v1 | ADR-0003 §2；SPEC 3.2；`corpus.schema.json` 的 `license_status` 固定 eligible |
| `license_or_terms` 结构化：名称/摘要、允许范围、署名、第三方内容检查、核验日期与签字者 | `corpus.schema.json`；SPEC 3.4 |
| 候选清单结构，允许四种状态，`reviewer_decision` 由决策人填写 | `candidate.schema.json`；SPEC 3.3 |
| PV 归入规则：内容范围、真实 doc_type、owner_dept 含义、notes 理由、至少 3 份独立文件 | ADR-0003 §3；SPEC 3.5；Schema 对 PV 文档强制 notes |
| 新增 `language` 字段（zh-Hans/zh-Hant/en/mixed），zh-Hant 须标注脚本变体并按语言切片报告 | `corpus.schema.json`；SPEC 3.4（基线新增，因候选中出现繁体来源） |
| 语料最低 10 份、每部门 3 份写入 Schema `minimums` 与 PR-04 | `manifest.schema.json`；SPEC 第 10 节 |
| DEC-011 行、M1 首项与 M5 文档项引用 ADR-0003 | 基线 v0.6 |

## 3. 候选清单 v0.1

文件：`evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.1.json`（通过 candidate.schema.json 校验）与同名 `.md`（供审核）。

| 部门 | eligible | research_only | needs_review | rejected | 合计 |
| --- | --- | --- | --- | --- | --- |
| MA | 2（DailyMed 英文说明书） | 0 | 6（台湾 FDA 繁体仿單） | 0 | 8 |
| PV | 6（EMA GVP VI/IX、FDA、ICH E2A/E2F、台湾 FDA 通报指引） | 1（香港衞生署） | 1（上海药物警戒管理办法） | 0 | 8 |
| CO | 2（ICH E6(R3)、FDA 方案偏离指南草案） | 0 | 4（VCU SOP、NIAID 方案 NCT06461026、NMPA GCP 2026、上海实施方案） | 3（ACCORD SOP、两份带保密声明的方案） | 9 |
| 合计 | 10 | 1 | 11 | 3 | 25 |

预判 eligible 的语言分布：en 9、zh-Hant 1、zh-Hans 0。对照最低要求（10 份且每部门 3 份、`drug_name_zh` 切片需要中文说明书）：MA 与 CO 各只有 2 份 eligible，且没有任何简体中文文档达到 eligible。探针集 v1 语料在现状下不能冻结。

## 4. 主会话抽查

| 证据 | 结果 |
| --- | --- |
| FDA 网站政策（公共领域、可自由转载） | 与代理引文逐字一致 |
| EMA Legal Notice（商业与非商业复制、须署名、第三方除外） | 一致 |
| ICH Legal Mentions（站点 JSON 接口） | 一致；页面本身为客户端渲染 |
| 台湾 FDA 開放資料宣告（OGDL-1.0、無償非專屬、註明出處、例外声明） | 一致 |
| 台湾 mcp.fda.gov.tw 平台页脚（未經同意不得重製、引用） | 一致，限制性条款确实存在 |
| data.gov.tw 数据集 9117 授權方式 OGDL-1.0 | 一致；但抽查页面未直接显示 mcp.fda.gov.tw 链接，代理称索引在数据集 39，需决策人核实链接归属 |
| openFDA CC0 声明 | 一致；含 GMDN 第三方内容例外 |
| 上海药监 PDF 可达 | 可达，196 KB |
| ClinicalTrials.gov 条款页 | 客户端渲染，抓取只得应用外壳；代理引文取自站点 JS 包，需决策人在浏览器核实一次 |

## 5. 系统性发现

- 简体中文国家级来源全部未过规则 1：nmpa.gov.cn、nhc.gov.cn 返回 HTTP 412 反爬挑战，cde.org.cn 附件返回 HTTP 202 挑战壳，本地无头浏览器同样失败；NMPA 能下载的静态附件只有 .doc/.docx（说明书范本、GCP 2026 修订版），无产品说明书 PDF；上海药监是唯一可同时抓页面与文件的省级站点。
- 内地站点只有“版权所有”页脚：上海药监无条款页；北京药监法律声明允许非商业转载但禁止商业照搬；药品评价中心声明未经许可禁止转载，按政策为 rejected。
- ClinicalTrials.gov 方案几乎全部带保密标记，包括 NIH 主办方案；按规则 3 字面执行几乎会拒绝全部方案。
- 机构 SOP 普遍无许可：VCU 无条款页（needs_review），爱丁堡/ACCORD 条款限私人用途（rejected）。
- 台湾是唯一可规模索引的中文来源，但平台页脚与 OGDL-1.0 数据集授权冲突，六份仿單全部 needs_review，一个决策可整体翻转。
- 2020 版《药物临床试验质量管理规范》已于 2026-09-01 被 2026 年修订版替代；语料应使用 2026 版。
- 代理执行副作用：CO 代理为解密 ACCORD PDF 用 `pip3 --user` 在本机安装了 `cryptography` 包；抓取的 PDF 副本留在会话 scratchpad 与 tool-results 目录，未进入仓库。

## 6. 待决策

1. 台湾仿單：以 OGDL-1.0 数据集授权为准（六份转 eligible，须先核实 PDF 链接确在开放数据集内），还是以平台页脚为准（六份 rejected）。
2. NIH 作者、带遗留 CONFIDENTIAL 页眉且由 NIH 自行上传的方案（如 NCT04283461）：维持 rejected，还是作为政策例外进入 needs_review 并向 NIAID 求证。
3. DailyMed 说明书：接受“同一 SPL 数据经 openFDA 以 CC0 发布”作为 eligible 依据，还是要求许可附着于抓取的确切 URL（降为 needs_review 或改从 openFDA 获取）。
4. 格式规则：是否允许官方 .doc/.docx 附件（NMPA GCP 2026、GVP 2021 政府公报版）进入语料，需修改 spec-v1 的 PDF-only 规则并定义 DOCX 定位器。
5. 脚本变体：在无简体中文 eligible 说明书的情况下，探针集 v1 的 `drug_name_zh` 切片是否可用 zh-Hant 文档并按语言切片报告，还是等待简体来源授权。
6. ClinicalTrials.gov 条款引文：请在浏览器打开条款页核实后，在候选清单 `reviewer_note` 记录核实日期。

## 7. 机械核对

见文末由脚本写入的实测表。

| 检查项 | 实测 |
| --- | --- |
| 不变量 / 重复 ID | 30 / 0 |
| checklist / 已勾选 | 99 / 0 |
| DEC 行数 | 11（新增 DEC-011） |
| 代码围栏（基线 / SPEC） | 14 / 2 |
| Schema 元校验（6 个） | 通过 |
| 示例校验与反向测试 | manifest、corpus、3 条样本通过；corpus/candidate 反向测试 8/8 被拒绝 |
| 候选清单 Schema 校验 | 通过（25 条） |
| 相对链接缺失 | 0 |
| SPEC/ADR-0003 中残留 DEC-005 引用 | 0 |
| 来源 SHA256SUMS | MedOps_Copilot_项目设计文档_v0.1.pdf: OK PROJECT_DESCRIPTION_v0.1.md: OK  |
| git diff --check | 输出行数 0 |
