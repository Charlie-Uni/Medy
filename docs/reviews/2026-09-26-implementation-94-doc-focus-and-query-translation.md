# 实现记录 94：文档定位（doc_focus）与查询翻译（query_translation）两个可发布的检索参数，全子集复测，检索候选合并评测

日期：2026-09-26。承接记录 93 §D 与决策人「按照你建议的来」：先做 P0 内的文档定位，跨语言检索以查询翻译从 P2 提前，生成阶段修正的对照方式接受「仅被测组件版本不同」的 baseline 复用，余额约 16 美元。

## 1. 文档定位 `doc_focus`（记录 93 §C.1）

问题点名了语料中的文档或产品时（拔痛酸錠、ICH E6(R3)、GVP Module IX Addendum I、藥品不良反應通報表填寫指引），该文档自己的分块才是可接受的证据；语料里又有大量「双胞胎」文本（同成分他牌仿單、ICH 原版与 FDA 转载、姊妹指南的共用段落），全库相似度检索会引到双胞胎，跨语言时则什么都找不到。

- `medops.retrieval.doc_focus`（规则版本 `docfocus-v1`）：从连接可见的 active 文档标题推导键——仿單取品名（跳过厂商引号，止于剂型或数字）、ICH 取编号（含修订号）、GVP 取 Module / Annex / P. 编号、中文指引取标题主干（≥ 6 字）；英文 FDA 指南标题 v1 不匹配。问题里出现键即命中；命中超过 3 份视为泛指，不定位。
- 检索端口：对每份定位文档，词法与向量通道各自在该文档内取前 20（`FOCUS_K`，与融合上限相同），作为额外名次表（`focus1:lexical` / `focus1:vector`）参与二级 RRF；不删除任何全库候选，重排照旧用用户原句。定位检索失败（如向量索引在过滤下扫描饥饿）只跳过，不影响全库结果。
- 词法与向量检索器新增可选 `doc_ids` 过滤（生产用的 `pg_simple_fts` 与 `pg_vector` 的 SQL 各加一条谓词；两个实验候选与离线参考实现收到过滤即报 NotImplemented）。
- 作为 `retrieval_params/hybrid` 的布尔键发布；开启时 `rewrite_params.doc_focus = docfocus-v1` 进入 `retrieval_version`，关闭时哈希不变。
- 测试：`test_doc_focus.py`（真实标题的键、问题匹配、歧义不定位）、`test_policy_loader.py`、`test_production.py`、SQL 谓词测试。

冒烟（5 题）：rp-0053（拔痛酸）与 rp-0533（胃所樂）的 gold 从「不在前 20」变为前 8 第 3 / 第 2 名；三道跨语言题（GVP Annex I 职业暴露、GVP Module XV 安全公告、ICH E6(R3) 施压）仍未命中——文档内向量前 20 也没把 gold 排进去，需要翻译。

## 2. 查询翻译 `query_translation`（记录 93 §D.1 方案 a，P2 提前）

- `medops.retrieval.query_translation.QueryTranslator`：仅当问题含中文时调用一次（默认 gpt-6-luna，白名单 gpt-6-luna / gpt-6-sol；输出 ≤ 240 token，超时 8 秒，JSON 结构化输出），系统提示要求逐字保留药名、编号、数字、单位与否定，不回答不补充。任何故障、预算截停、截断、空输出、超长或仍含中文都返回 None，检索按原样进行（失败开放，span 记录原因）。
- 译文只作为一条额外检索查询参与融合，永远不成为证据、不进入 answer 节点；所有候选仍按用户原句重排与校验。
- 计量：API 里翻译走与请求相同的 `MeteredGateway`，token 与费用记在 Trace 上；评测平面同理计入臂费用。
- 版本：`rewrite_params.query_translation = qt-v1:<model>` 进 `retrieval_version`；`model_config_version` 加 `;qt=<model>`。MCP 搜索工具没有模型网关，不做翻译（其审计版本已知仍记常量，记录 85 遗留）。
- 测试：`test_query_translation.py`（英文问题不调用、译文成为查询、五类故障失败开放、白名单），loader 与版本输入测试。

## 3. 复测与评测

（待填：全子集 200 题复测 `2026-09-26-recall-diag-v4-bundle`（词表 + multi_query + doc_focus）与翻译复测；候选文件；门禁结果与费用。）

## 4. §9 自审

- 两个参数默认关闭，关闭时行为与 `retrieval_version` 与今天完全一致；记录 90 的 baseline 臂仍可复用。
- 翻译只影响「找哪些块」，不影响「答什么、引什么」；引用核验、安全检查、拒答规则全部不变。
- 文档定位的键规则是确定性的、可从标题复现的，且随连接可见性受部门限制；不会让用户定位到自己无权读的文档。
