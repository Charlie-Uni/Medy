# 记录204：EVAL-33历史种子清单与主集/探针字段读取

- 日期：2026-10-15；实现/自审：Codex，不是第二独立人工。
- 基线：83a67b7ae2eafb06aaed123a5b900b29d6013c26；唯一主切片EVAL-33历史目录/字段读取准备。
- 实施后进入REVIEW；代码全量门禁通过，文档/范围核对后结论为**本轮范围工程自审通过**。EVAL-33仍IN_PROGRESS、PLAN-02 HUMAN、EVAL-32 BLOCKED；D-01/D-02和保管安排pending，S2未开始。
- 机器证据：[204-results.json](2026-10-15-implementation-204-results.json)；原始成功/失败日志、源摘要、审核/同步/发布收据在本机.local/audit204，不入Git。

## 1. 做了什么、为什么先做这一步

记录203只校验计划/回执，不能证明实际完整读取。本轮补[历史契约v0.1](../agent/EVALUATION_HISTORY.md)、[16条元数据种子](../../evals/holdout/protocols/history-source-seeds-v1.json)和[主集字段读取器](../../src/medops/evals/isolation/history_reader.py)。路径、摘要来自已有清单/SHA256SUMS；实际历史正文扫描0、封存新题0，不能称已审完历史。九条主集/探针文件只是该读取器的候选，旧版本实际格式尚未核查，其余七条安全/回放格式不在准入内。

复用已有jsonschema和两个原Schema的固定SHA，避免维护重复Schema和任意字段抓取。main-probe-samples-v1仅支持dataset-fields-v1里的query/gold/source投影；不解析安全/回放、检索结果、加密执行材料或会话日志。Claude/Codex真实日志路径尚未指定，本轮未读取，也没有把工程记录称为历史原话。

接收可信调用方已经打开的文件描述符，不新增任意路径CLI或网络端点。文件必须属当前OS身份、无group/other权限、普通文件；pread不改offset、不关闭fd、不写文件。全文件大小/摘要、固定Schema、显式限额和前后文件状态绑定；仅成功解析全部非空行才能返回checked回执与私有投影。固定错误码不含文件路径、行正文或底层异常，失败不导出部分结果。

资源在读取/行切片前检查，不整文件split成大量行对象。UTF-8、重复JSON键、最后坏行、必需字段/类型、重复题/gold、gold所属题、区间/key自洽均拒绝不合格结果。取消在块/行/返回前检查；截止时间必须是有限绝对monotonic值。它是合作式停止，不能强杀阻塞文件系统调用；保管部署不能省略这一限制。

## 2. 本轮错误、发现与补救

| 过程 | 实际错误/问题与补救 |
| --- | --- |
| 首次测试收集 | 退出2：`SyntaxError: unterminated string literal (detected at line 59)`。生成测试脚本时坏JSON的bytes换行未转义，修正测试源，原失败日志保留；随后52 passed |
| 静态检查 | ruff 52项：压缩测试语句尚未格式化，且取消回调异常边界需写明BLE001例外理由；格式化并保留固定错误脱敏边界。mypy 1项：`Argument 1 to "_sample" has incompatible type "object"; expected "dict[str, Any]"`，在Schema验证前显式检查dict，复测通过 |
| 自审代码 | catch ValueError会同时捕获IsolationError并抹掉原失败码，增加先行IsolationError重抛；文件split会额外分配全量行列表，改按LF逐行定位。请求层次收紧为恰好query/gold/source，避免少声明层次却返回全部私有字段；均在最终测试前修复 |
| 共享隔离命令 | 退出4：`file or directory not found: tests/unit/evals/test_isolation_contracts.py`，本次没有执行测试；按rg实际文件清单重跑，243 passed。只读检查另两次猜错旧审计/文档测试路径，纠正实际路径，不计验证通过 |

没有真实业务数据失败、付费调用或新标注修改；这些错误是本轮生成测试/工程检查和自审发现。不能删掉失败记录或把最终通过写成全程无错误。

## 3. 最终验证

| 验证 | 结果 |
| --- | --- |
| 新旧隔离测试 | 243 passed，新增61读取反例，旧182保留；pytest5.50秒，总7.034秒 |
| required-services make check | 退出0，2566 passed、70 skipped、1 warning；pytest100.03秒，总134.805秒 |
| 静态门禁 | 格式731文件、mypy339源文件、架构339模块0违例/2既有例外、286断言文件0违例 |
| 冻结输入/Schema | 4数据集PASS，导出Schema无漂移；2个unmappable继续计miss，独立人工/历史安全回放/无新盲测警告保留 |
| 旧实际CLI | 9/9、6/6、6/6 true，0模型调用、unknown，源文件字节保持 |
| 文档与源范围 | 41文档测试通过，244本地链接/10片段通过，143任务ID保持；本轮13路径、727既有维护输入中726保持，仅contracts新增固定错误码；新增3 Python文件 |

70 skip仍为旧B/C可选实验；必需PG/Redis/Docker和D实际执行。D仅测试子进程绑定只读核实的PG17/pg_textsearch1.5.1，使用一次性库/角色，.env与业务DSN未改。warning是原JWT负例的短HMAC key。全量门禁不代表真实历史扫描、模型质量、未见资格、医学标注或生产验收。

## 4. 八项强制自审核

| 项目 | 结论 | 证据及限制 |
| --- | --- | --- |
| scope | 通过（本轮范围） | 固定样本读取原语/来源元数据，无其他主任务/Agent实现 |
| ADR_and_stage | 通过（本轮范围） | 未批准D-01/D-02、未改ADR/生产门，EVAL-33部分进行中 |
| correctness_and_failures | 通过（本轮范围） | 61新用例含完整/空/尾行、坏行/类型/重复、所有绑定/限额、取消/期限、权限/文件变化；工程错误已修复 |
| permissions_and_data | 通过（本轮范围） | 私有结果明确不可公开，真实扫描0；鉴权/访问前审计/独立保管未完成，未冒称隔离成立 |
| budget_cancellation_side_effects | 通过（本轮范围） | 0模型/费用、无业务DML/部署变化，合作式取消限制明示 |
| traceability_and_versions | 通过（本轮范围） | 计划/文件/Schema/资源摘要及reader版本绑定，原失败收据保留；不是身份签名/全历史证明 |
| verification | 通过（本轮范围） | 243定向、2566/70全量、旧三CLI及文档/源码核对，原skip/warning保留 |
| status_and_documentation | 通过（本轮范围） | EVAL-33 IN_PROGRESS、PLAN-02 HUMAN、EVAL-32 BLOCKED，16种子均not_selected/unknown |

## 5. 限制、回滚与下一步

只证明公开合成文件的读取行为；固定Schema可能拒绝其他历史格式，必须作为缺口处理，不能跳过后称完整。文件字节摘要及自洽区间不证明原件、医学正确性、独立人工或历史未见。普通文件权限不能隔离管理员；上游必须完成真实身份、访问前审计、安全打开、签发回执和受限结果出口。历史来源发现/解密、第二类适配器、ExposureEvent联动、可信runner、分片/全部历史覆盖仍待。

下一准备实际检索/回放字段适配器与受限runner契约；真实新题先落实保管安排，正式近重复参数先在已暴露开发资料校准。PLAN-02两项决定仍是S2前置；付费逐次授权，自动激活只实验，原生产批准门保持。

13路径按固定错误码、读取实现/反例、元数据/契约、关联方法文档、审核/台账五批提交；核对根目录/快照/提交tree与实际SHA的CI。无迁移、重启或生产接线；需要回滚时撤回本轮提交即可，冻结数据/旧账本原样保留。提交和CI回执不自写进同一个已审核commit，另存本机和交付时真实SHA证据。
