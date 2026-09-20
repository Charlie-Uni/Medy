# 实现记录 41：决策人授权下的四项决定（DEC-002、DEC-005、DOCX/恶意文件、候选 C 许可证）

日期：2026-09-20。记录 40 末尾列出四项等待决策人的事项，决策人回复："我需要的是结果 你来决定"。本记录登记实施方据此作出的决定、理由与可逆性；决策人可随时否决，否决即按其指示回退。

## 1. 决定一览

| 事项 | 决定 | 登记 | 可逆性 |
| --- | --- | --- | --- |
| DEC-002 Embedding/Reranker | `BAAI/bge-m3` 稠密 1024 维、L2 归一化、余弦；`BAAI/bge-reranker-v2-m3`；修订与许可证固定（MIT / Apache-2.0）；仅本地推理；HNSW + iterative scan + 精确计数 | [ADR-0007](../adr/ADR-0007-embedding-and-reranker-selection.md) | 新列/新索引重建，`embedding_version` 换版 |
| DEC-005 术语表来源 | TFDA 藥品許可證開放資料（政府資料開放授權）+ 语料内定义缩写（逐条页文本核对）；DrugBank Open Data（CC0）待决策人下载；排除 MedDRA、WHO INN、药典、NMPA 抓取 | [ADR-0008](../adr/ADR-0008-medical-glossary-sources.md) | 术语表文件版本化，可回退 |
| DOCX 与恶意文件 | 标准库 + `defusedxml` 解析 OOXML；`page` 对 DOCX 为顶级章节序号、无标题即 low_trust；结构性恶意内容门禁（PDF 动作/脚本/嵌入文件、DOCX 宏/OLE/外部关系/DDE、ZIP 炸弹）必选；ClamAV clamd 可选、prod 必配 | [ADR-0009](../adr/ADR-0009-docx-and-malicious-file-policy.md) | 解析器版本化；策略可放宽需另行修订 |
| 候选 C 许可证 | 排除出生产候选（`excluded_by_decision`）；保留为实验对照 | [ADR-0002 修订 4](../adr/ADR-0002-lexical-retrieval-selection.md) | 取得书面许可结论且端到端门禁不过时可重新纳入 |

## 2. 理由摘要

- **bge-m3**：DEC-001 三次运行证明跨语言（中文提问、英文条款）只能由向量阶段承担；bge-m3 是多语言稠密模型，中英文与跨语言检索表现公认，MIT 许可，可在 CPU/MPS 本地运行，满足"页文本不出境"的保守出境策略；1024 维在 pgvector HNSW 上的存储与延迟可控。不选外部 API（出境与版本漂移）、不选仅中文或非商业许可模型（jina v3 为 CC-BY-NC）。
- **术语表**：语料以台湾仿单（繁体商品名）与 ICH/GVP/FDA 英文指南为主；TFDA 开放数据直接给出繁体品名到英文品名/成分的映射且许可清晰；缩写以语料自身定义为准，逐条可核对。
- **DOCX/恶意文件**：DOCX 无页概念，用章节序号作定位单元并显式渲染为"第 N 节"，比伪造页码诚实；结构性门禁不依赖外部服务即可拦截最常见的文档攻击面，反病毒扫描按环境要求。
- **C**：技术上最优（88.0%）但许可证策略风险与运维耦合最高；在决策人授权下取保守结论，且已有可逆路径。

## 3. 本记录之后的实施顺序

1. 阶段 2：M1-16 向量阶段（迁移 0006、embedding 提供者、pgvector 适配器 + RLS + iterative scan + 精确计数、索引构建、探针 v2 向量通道运行）。
2. 阶段 3：M1-09 收口（DOCX 解析、结构性恶意文件门禁、clamd 钩子）。
3. 阶段 4：DEC-005 术语表构建工具与初始术语表。
4. 阶段 5：M1-17 融合与端到端运行，DEC-001 最终判定（A2/B2 + 向量）。

每阶段仍按 §9 自审 + 全量门禁后提交，并报告加权进度。

## 4. 依据

ADR-0002 修订 3、记录 35–40、[licence dossier](2026-09-20-licence-dossier-pg-search.md)、基线 3.6/3.7/3.8/5.1/5.2、探针 v2 冻结集。
