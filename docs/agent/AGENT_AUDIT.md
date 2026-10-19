# Agent 受限历史审计读取

2026-10-19记录223最新进度：当前条件诊断与差异报告已接入真实运行器，完整CI及八项工程自审已通过，AGENT-06 DONE；后续SESSION/集成/真实试跑仍待；[回放契约](AGENT_REPLAY.md)。本页后续记录220～222的原状态保留为当轮历史。

2026-10-19，AGENT-06，记录221。本切片八项工程自审通过；整体AGENT-06 IN_PROGRESS。依据ADR-0012、PLAN-02、DEC-013的管理员/用途/访问日志边界，沿用记录217的runtime保留期。本切片提供真实读取入口；业务Trace/反馈登记和诊断回放仍待，不把读取当作恢复或重放。

## 1. 使用与返回材料

`GET /admin/agent-runs/{run_id}/audit?purpose=<8–500字符用途>`。run_id必须是原Agent运行UUID；用当前管理员Bearer身份，管理员可在受限审计边界内查历史跨部门材料。返回既有`TracePayloadResponse`，trace_id取持久控制记录；响应`Cache-Control: no-store`。响应头X-Trace-Id仍标识本次HTTP请求，body.trace_id标识被读取的原业务运行。没有新增请求/响应模型或改变旧路径。

首项`node=agent.runtime.head, kind=runtime_head`：payload.control是原case/task/run/attempt、principal/dept、生命周期/终态指针等数据库元数据；payload.head是revision、租约、原预算快照和期限；payload.body是通过AEAD认证并核对绑定的历史JSON（叙述、要求、配置、Loop/行动理由、证据注册、待处理规划/工具等）。head本身仍是running执行检查点，不能据此否定或宣称已交付；业务终态由control.terminal_ref指向的加密事件识别。

其余`node=agent.runtime.event`，kind沿用call_admitted/call_settled/tool_committed/checkpoint/late_stop；包含真实event_id、item_id、租约及解密body。原模型请求/回复、实际回执、工具观察/证据、核验与终态材料按原样保留。不生成新的行动理由、不补造丢失调用、不重算医学质量。预算head是该版本的检查点，晚到回执单独保留，不能把head当成最终账单。

## 2. 授权、日志与密文兼容

复用privileged_connection：先应用连接认证管理员，再在应用身份栅栏内核对受限连接是否同一事实库、当前角色/活跃状态和Token；栅栏保持至受限事务结束。普通analyst/approver、无身份、撤权和错库不能到达读取器；读取器也显式检查admin角色与有效用途。

0031只增加现有medops_restricted_role在Agent控制/heads/events上的SELECT策略和control SELECT授权；不新增角色，不扩大普通用户/部门ACL，不给受限角色新增INSERT/UPDATE/执行权限。0029既有过期DELETE策略/不可变事件、0030终态封闭和所有写入守卫保持。降级0030移除新增读取权限，不改历史密文/Nonce/DEK/KEK。正式三库本轮不迁移/重启。

runtime AAD抽为共享纯函数，严格保留pv-agent-runtime-v1原字节格式；以固定golden bytes与真实写入/读取验证。仍使用原KEK版本及AES-GCM绑定，原run/条件摘要/事件ID/类型/item/租约及head预算/期限不能被替换；不重新封装历史记录。历史读取不调用当前Loop重建、Prompt/工具或预算恢复校验；当前版本变化不能阻止查阅原件。完整性认证不代表重新判定原业务结论正确，当前恢复/执行守卫保持。

每次成功返回前，在同一受限事务插入payload_access_log（原Trace、管理员假名、用途），在日志写入之后才解密。上下文退出提交成功后才返回对象，提交失败不得返回已解密材料。密钥/密文/结构/日志故障失败关闭；错误只保留安全类型，不输出原异常、正文或密钥。失败并回滚的读取不保证留下访问日志；本轮没有另外增加失败尝试日志，也不声称SQL管理员的直接密文访问由此自动审计。

## 3. 完整性、并发与资源限制

一次最多512个事件、32 MiB密文/封装/预算元数据总量；先查小型metadata manifest和长度，再取密文，超过上限503 audit_unavailable，不能静默截断后称完整。解密后再核对总明文字节。读取器本身受5秒总期限约束（连接/认证沿用既有超时），不新建执行根、预算、租约或模型调用。

使用READ COMMITTED和原身份栅栏；读取head与事件manifest，取得限定ID的密文，再复查head/control与manifest。head revision单调、事件不可变，任何并发变化409 version_conflict，调用者可重取。材料按created_at/event_id排序，实际行动关系应看decision/action/item ID，不能以时间排序推测因果。返回完整受限快照，不构造跨进程一直存活的span。

按数据库时钟排除head.retained_until已过的材料（即使尚未purge也404），并检查事件保留期和归属一致。这里沿用Agent runtime现有retained_until；不把普通trace_payloads的升级案宽限规则自动移植到runtime。purge/审计密钥轮换/业务保留期扩展仍须各自契约。

## 4. 验证与后续

真实临时PG、五类LOGIN与生产ProductionRuntime/HTTP装配；供应商全部Fake。核验成功/澄清/升级、原始材料/同Trace、用途/日志、当前管理员与错库/撤权、提交/密钥/日志失败、密文替换、并发、大小/数量、过期及迁移往返。历史Ask/Skill/MCP/Agent与原Schema检查同时回归。

AGENT-06整体保持IN_PROGRESS：持久业务Trace/反馈后由记录222完成，诊断回放与原条件拒绝边界尚待；真实模型质量、Langfuse实际后端演示、容量、正式部署/独立盲测分别验收。实际命令、失败、修复和八项自审见[记录221](../reviews/2026-10-19-implementation-221-agent-restricted-audit.md)。

2026-10-19记录222已完成[持久业务Trace及原反馈接线](AGENT_TRACE.md)，本切片八项工程自审通过。诊断回放仍待，整体AGENT-06未完成；既有管理员用途审计边界保持。
