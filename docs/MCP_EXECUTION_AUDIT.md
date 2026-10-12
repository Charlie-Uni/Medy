# MCP执行材料与观测职责

2026-10-12，CODE-07；实现、自审和失败迭代见[记录194](reviews/2026-10-12-implementation-194-mcp-audit-and-observability.md)。沿用DEC-013的载荷加密、用途说明、受限读取、访问日志和保留期，不改变四个只读工具的公开Schema。

## 1. 四工具保存的材料

`mcp-audit-v1` 使用既有三类载荷，node为 `mcp`：

| 类别 | 内容 |
| --- | --- |
| input | 工具名、经验证的完整typed输入及SHA、原用户身份、实际版本；搜索另保存解析后的QueryContext和已观察执行条件 |
| evidence_snapshot | 搜索的完整retrieval outcome：改写、候选/通道名次、证据、拒绝、缓存/来源标志及返回子集；其他工具的完整原始chunk行/不存在观察、版本行 |
| model_output | 实际工具输出或失败原因码/异常类型；搜索翻译的完整ModelRequest、SDK发送/回复、parsed响应和逐调用回执；call journal完整性标记 |

Trace原500字符输入摘要继续存在，完整输入另写受限input载荷。非搜索工具没有模型调用，model_calls为空；未执行搜索时配置/日期为null，不冒造未发生的执行条件。搜索条件采集在原retrieve执行期限和预算内，包含磁盘源码/环境摘要、实际灰度/策略内容、检索参数和执行profile；没有新增模型调用或预算。

没有事实查询或搜索重跑来组装材料。McpService返回已观察快照，包括不存在的chunk；最终检查仍由ARCH-15栅栏及当前身份验证负责。快照限本次观察，不是完整语料、ACL或索引历史。源码摘要表示磁盘文件，不证明已加载对象或签名镜像；原条件恢复/Task-MCP回放仍拒绝。

## 2. 写入、权限与失败

MCP读取继续使用readonly LOGIN和部门RLS；写审计使用app LOGIN。成功调用的最终app栅栏事务持有到readonly服务提交、Trace和加密载荷提交；它们共用同一写事务。仅保存成功后的证据不能替代原最终授权检查。

配置 `PAYLOAD_KEY_FILE` 时启动即加载现有LocalFileKeyProvider；权限/格式/密钥错误不静默改成无正文模式。未配置key时保持原开发行为，仅写Trace。生产仍应使用既有KEK overlay；本轮没有重启实际MCP服务，因此代码交付不代表已有服务正在写新材料。

持久化/密封失败时事务回滚，结果不返回，不自动重跑模型或再次尝试同一审计写入。已经发生的真实费用由独立费用账本/调用回执继续保留，回滚Trace不撤销外部收费；本轮数据库测试使用假模型和合成计费，验证调用次数和原子回滚，不代表供应商账单对账。

搜索失败仍保存已发生的模型请求、已知回复/费用回执及失败类型。普通未预期异常也写失败审计，公开返回固定internal_error，异常消息不进入材料或遥测。无认证身份的拒绝仍由协议认证处理，不补造用户。

CallJournal沿用128调用/16MiB上限。MCP三类材料另有合计16MiB序列化上限；超限或journal不完整不能返回成功。超限失败只保留输入/身份哈希、部门/原因和费用回执，明确 `input_audit_complete=false` / `model_call_audit_complete=false`；回执本身过大时也改存摘要并标 `call_receipts_included=false`，独立费用账本保留。不得将截断失败材料当完整复现证据。这些是记录容量限制，不是整个进程严格内存上限；序列化及SDK对象仍有临时内存。

## 3. 观测分工

| 层 | 模块 | 职责与方向 |
| --- | --- | --- |
| 在线元数据采集 | core.telemetry / MeteredGateway | 受控span、版本、耗时/用量/费用；不输出输入/证据/回复或异常消息 |
| 受限执行事实 | mcp.audit / SearchExecution / CallJournal | request-local正文/调用事实；交给ExecutionAuditWriter和加密PayloadWriter，不发Langfuse |
| 评分wire | infrastructure.observability.schema | allowlist、固定ID/时间、值类型；不依赖HTTP、SQLite、队列/反馈采集 |
| HTTP发送 | infrastructure.observability.client | 固定目标、认证、trace关联与应答校验；不管理持久队列/反馈读取 |
| 持久队列 | infrastructure.observability.queue | 容量、退避、死信、目标绑定和收据；不采集反馈/正文，客户端仅类型依赖 |
| 反馈采集 | infrastructure.observability.feedback | 只读已提交反馈ID/类别/时间及稳定namespace；不选query/correction_text |
| 驱动 | worker.observability | 常驻调度、退出/重放控制；提交后的评分导出与业务请求写事务分开 |

原 `medops.infrastructure.observability` 的公开评分API继续通过包 `__all__` 提供；生产调用方使用具体职责模块。九个原类/函数与三个格式/allowlist常量AST相同，未改HTTP协议、SQLite布局、事件ID、退避/死信或评分含义。保留固定timestamp的score-create兼容路径，没有趁重构升级Langfuse。

新增静态边界阻止schema接入HTTP/队列、客户端依赖队列、队列采集反馈。对全仓库显式import图审查：模块级提前导入无环；把函数内/TYPE_CHECKING也算入时，保留原三组（probe复核/validator、Harness相关类型、检索完整性/维护/production），本轮无新环。该机械图不覆盖动态执行、隐式父包加载或所有架构不变式，不宣称全仓库已经达到某个通用“优秀架构”标准。

## 4. 工程状态与限制

详见记录194的required门禁、普通LOGIN/加密读取/部分写失败反例、真实元数据protobuf回归和源码对照。本轮0托管调用/0USD，无共享库迁移、索引重建、部署或真实Langfuse后端复测。OBS-03登录后的人工UI核对、原条件回放、第二人工、盲测与S2/S3门保持。

评测工具、失败实验产物和历史draft源码继续保留；CODE-05规范包已有当前入口，不因候选被否决删证据。共享MCP测试client从单测模块提取到 `tests/mcp_client.py`，不把整个CODE-06夹具治理记为完成。

回滚本轮代码与契约即可恢复旧MCP元数据审计与旧观测模块；没有新增迁移。新写的mcp-audit-v1按现有载荷保留/读取规则保存，回滚不删除历史执行材料。
