# EVAL-33：历史来源种子清单与首个字段读取器

- 日期：2026-10-15；版本：v0.2；实现/自审：Codex，不是第二独立人工。
- 范围：已有公开历史文件的元数据种子目录、固定主集/探针 Schema 的 JSONL 私有读取原语及公开合成验证。**真实历史正文扫描次数为0，新盲测题为0，资格仍unknown。**
- 依据：[检查方法](EVALUATION_SCREENING.md)、[隔离契约](EVALUATION_ISOLATION.md)、[保管提案](EVALUATION_CUSTODY.md)；工程证据见[记录204](../reviews/2026-10-15-implementation-204-history-source-catalog-and-sample-reader.md)。EVAL-33仍IN_PROGRESS。

## 1. 目录来源及为什么没有直接扫描全部内容

[history-source-seeds-v1.json](../../evals/holdout/protocols/history-source-seeds-v1.json)列16个已经冻结的历史文件：主集v1～v5各1、探针v1～v4各1、回放v1～v3各2、安全v2的1个。路径与SHA来自已有文件清单和SHA256SUMS，**仅核对元数据，不重新读取样本正文**。每条actual_format_validated=false、body_scan_state=not_selected；9条主集/探针可尝试本轮读取器，尚未证明其全部历史版本符合现在固定的Schema。

这是一份带缺口的盘点起点，example_only=true、approved_scan_plan=false。它不等于保管人批准的HistoryPlan，也不证明只有这些历史。开发/修订/裁决、检索优化运行、生成/裁判输入、加密执行材料、会话日志、人工笔记、未跟踪/外部/删除内容仍在unresolved_categories。

**Claude/Codex日志：本轮没有读取任何会话日志，没有确定真实导出文件路径。** 后续由所有者/保管人指定原文件或受控导出，核对真实可见角色、时间、字段、完整性与授权。仓库实现记录不是原始会话，不能伪称模型历史原话；无法取到日志时保留unknown。

## 2. 支持什么格式和字段

代码：[history_reader.py](../../src/medops/evals/isolation/history_reader.py)。具体读取器main-probe-samples-v1是dataset-fields-v1下的窄实现，**不是这四类适配器全部完成**。

| 格式 | 本轮状态 |
| --- | --- |
| 主集/探针samples.jsonl | 固定两个现有Schema的完整验证和字段投影已实现，仅以公开合成文件运行 |
| 安全集/回放samples或items | 格式不同，未支持；不得套入主集读取器后标checked |
| 检索/优化行文件 | retrieval-fields-v1仍无实现 |
| Ask/Skill/MCP受限材料 | execution-fields-v1仍无实现，解密/授权/实际身份另需接线 |
| Claude/Codex导出或笔记 | conversation-fields-v1仍无实现，来源及实际Schema尚未确定 |

复用已有jsonschema依赖和原JSON Schema，SHA分别为主集431f8cff…c32be、探针3bc57fb1…5e04f。传入Schema须同时匹配调用方预期摘要与代码准入摘要；即使任意Schema自带正确hash，也不能准入。未复制维护第二份大Schema，未修改冻结Schema或原样本。新Schema版本须明确准入，不自动放宽旧规则。

读取器只接受计划层次**恰好query/gold/source**。文件本身含其他审核/注释字段，因此上游读取授权必须覆盖整份文件；该计划层次是本轮检查/投影范围，不能用来声称读取了其余层次的全部历史。

| 私有投影 | 白名单字段及含义 |
| --- | --- |
| 题目 | sample_id、query、derived_from；后者为已有孪生关系，不自动建立语义家族 |
| gold/来源 | gold_id、source_hash、version_label、page、printed_page_label、section、key_text、evidence_span.text/char_start/char_end |
| 无答案核查 | scope_document_key、topic、absence_check、document_pages；无gold仍可保留限定来源与缺失核查材料 |
| 版本冲突 | family_document_keys、current_document_key、clause_topic、synthetic；原声明关系不是独立核实的family_id |
| 不投影字段 | notes、review身份/状态/说明、drafted_by、其他未选择元数据；按整行Schema验证，不声称已完成原裁判判词的暴露核查 |

实际文字结果仅返回给可信保管调用方。它不是公开摘要，不能打印到开发日志、Langfuse、候选生成输入或公开仓库。receipt可用于计划范围覆盖核对，但**不能单独证明检查了全部历史或实际访问者身份**。

## 3. 读取、资源、停止和失败契约

1. **先授权与审计、再打开文件**：上游可信流程固定来源ID、计划/Schema/限额摘要与读取身份；拒绝模型路径。当前函数不实现鉴权、路径解析、预先审计和回执签发，尚未作为真实扫描服务暴露。
2. 接收已打开的POSIX普通文件描述符，不接路径；要求文件属当前OS身份、无group/other权限。保管方须在受控目录安全打开或制作0600副本，再校验原字节摘要。文件权限不是角色鉴权，也不能隔离持有管理员权限的开发者。
3. 使用pread从偏移0读取，不移动调用方offset、不关闭原fd、不写文件；路径之后替换不会换成另一个fd。上游仍须处理父目录/软链接安全；本函数未提供路径沙箱。
4. 大小检查在读取前，分块读取总量不超过显式上限+1；整份实际SHA符合登记值才进入行解析。读取前后与返回前核对device/inode/size/mtime/ctime，修改时失败。摘要绑定读取到的字节，不保证文件永远不变。
5. 仅LF作为JSONL分隔符；兼容CRLF、无尾换行、ASCII空白行，保留字符串里的Unicode行分隔符。逐行定位且先检查长度，避免split整文件分配大量行对象；UTF-8严格解码、嵌套重复JSON键拒绝。
6. 所有非空行均须符合固定Schema；缺字段、额外字段、类型不符、重复sample_id/gold_id、gold所属题不符、区间长度或key不在span均失败。区间与文本自洽不等于实际PDF/医学标注正确；本轮不重新核对原件。
7. 显式max_file_bytes≤32MiB、max_line_bytes≤256KiB、max_records≤10,000、max_projected_chars≤20,000,000；最后一项计算每条私有投影JSON的Unicode字符数之和，包含字段名/结构。没有正式默认值，限额内容摘要绑定结果；测试值仅演练。超限不截断后报完整。
8. 调用方提供绝对monotonic截止时间与取消回调；读取块、每行及返回前检查。取消、过期、回调异常/非bool返回固定history_interrupted。**合作式检查不能强杀阻塞的文件系统调用**，真实部署须选择受控本地存储或另设进程监督。
9. 仅全文件成功后返回PrivateHistoryScan和checked回执，任何失败都无部分记录/成功回执出口。错误固定为invalid_metadata/invalid_payload/binding_mismatch/history_limit/history_interrupted/history_io/history_unsupported；不回显路径、行正文或底层异常。原始异常context被抑制，可信调用方不得额外记录locals。

空文件经过完整摘要校验可以checked且record_count=0，仍qualification=unknown；不存在/未选/未支持文件由未来runner登记未完成回执，当前函数不把异常自动转换成成功或无暴露。split分片覆盖、真扫描与ExposureEvent联动仍待实现。

## 4. 公开合成演练

```sh
env -u DEBUG PYTHONPATH=src venv/bin/python -m pytest -q tests/unit/evals/test_isolation_history_reader.py
```

只创建公开假题文件及临时fd，测试已有公开Schema，不读真实样本、数据库、会话或模型。原三个CLI自检保留；本轮未增加任意路径CLI。全套工程结果见记录204，不能用用例数代替实际历史覆盖率、性能或未见资格。

## 5. 下一步

按真实检索/回放行文件的固定Schema准备第二类字段适配器与受限runner契约；单独登记还不能定位的日志/解密/访问身份缺口。真实历史及封存题的读取先满足独立保管安排、实际授权和访问前审计，正式近重复参数在新题接入前校准。PLAN-02 D-01/D-02已由记录205确认，下一主任务AGENT-01；本项第二类读取准备穿插，真实保管环境仍待提供，每次托管模型费用另行授权。
