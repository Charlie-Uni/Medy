# 记录 203：EVAL-33 近重复参考方法与历史扫描回执

- 日期：2026-10-14；实现/自审：Codex，不是第二独立人工。
- 基线：`b9ce2ed87a5cc4935a73287b0df2a96429b1fd46`；主切片EVAL-33，关联修复校验入口和全量门禁暴露的旧测试竞态。
- 结论：对应离线机制工程自审通过。**EVAL-33仍IN_PROGRESS，PLAN-02 HUMAN，EVAL-32 BLOCKED，D-01/D-02和真实保管安排pending；S2未开始。**
- 机器证据：[203-results.json](2026-10-14-implementation-203-results.json)。原始失败/成功日志与收据存本机`.local/audit203/`，不入Git。

## 1. 交付与选择理由

[方法v0.1](../agent/EVALUATION_SCREENING.md)定义现有硬重叠检查、词面近重复、家族/关联核查及历史暴露盘点的关系。新[screening.py](../../src/medops/evals/isolation/screening.py)使用固定字符片段集合Jaccard，用整数比较阈值，无新依赖/模型；原字符量/组合数限制在处理前检查，不截断后报告“无命中”。输入必须与inventory原/规范化query摘要一一匹配，方法与两侧清单摘要绑定，输出私有复核对，不读gold。

数字、否定、条件沿用norm-v1保留。相近的相反陈述仍只是review_required；未命中、短文本或译文不能叫未暴露。公开[参考参数](../../evals/holdout/protocols/screening-reference-v1.json)标example_only/未批准正式使用；未用合成测试宣称召回率/正式阈值通过，没有自动家族合并或修改258来源候选资格。

[history.py](../../src/medops/evals/isolation/history.py)校验固定历史计划与来源/适配器/必查层次/记录数回执：缺失、未支持或未选择均保留缺口，错摘要/层次/适配器/重复/额外回执拒绝。declared_scope_status=complete仅表示登记计划回执齐全，qualification仍unknown，历史穷尽标记false。接口名称不是实际解析器；没有读取会话、历史运行正文、受限载荷或封存新题。

新增`--screening-self-check`六项公开合成检查；旧9项输入/账本和6项聚合检查保持。无任意路径、数据库或模型入口，输出固定布尔及unknown资格。

## 2. 发现的问题、原输出与修复

### 2.1 复制对象的strict校验漏洞

首轮定向原输出：`2 failed, 54 passed in 0.11s`。一条原文是`Failed: DID NOT RAISE IsolationError`；另一条预期invalid_metadata，实际binding_mismatch。

原因：原validated_copy先model_dump(mode=json)，复制进入整数栏的bool可能序列化为1，再做strict校验时已失去原类型。将共享重校验改为Python模式，继续抑制带私有值的serializer警告；随后重新验证，错误只报固定码。新bool反例通过，旧121隔离用例保留，全部182项通过；有效原模型的hash仍在json规范形式计算，没有更改norm-v1或冻结资料。

mypy曾报：`Incompatible types in assignment (expression has type "HistoryReceipt | None", variable has type "HistoryReceipt")`。两循环复用同变量导致推断冲突；分开变量，最终338源文件通过。

### 2.2 全量门禁失败与补救

首次完整门禁：**退出2，7 failed、2475 passed、92 skipped**，pytest135.80秒，总182.311秒。失败没有改成skip。

- 六项原输出为`No such file or directory: 'docker'`、`required dependency: Docker Compose unavailable`及备份依赖错误。当前执行PATH没包含已安装CLI目录；Docker实际29.8.0、Compose5.5.1可用。只在本机验证子进程PATH补/usr/local/bin和/opt/homebrew/bin，未改部署、.env或测试required模式。
- 旧`test_successful_scheduled_exit_stays_healthy_while_waiting`原输出为`count == 'xx'`成立但`all(observations)`为false。测试先读status=waiting、再让healthy重读；中间允许变成starting。确定性反例已复现这两次读跨状态的条件；观察者现在保存实际已观测的原子快照，再用原healthy检查该快照。原all断言、5秒deadline、0.2秒interval和tick保持，未改worker生产实现。新增反例证明unready waiting仍失败。

补救后三文件21 passed（pytest7.49秒，总10.163秒）。第二完整门禁退出0、2483/92（pytest158.77秒，总165.24秒），但多出的22 skip仍未满足原覆盖，未作为最终等价验证。

`-rs`确认额外skip来自旧D实验服务器不可达。一次诊断命令猜错词法测试文件名，退出4；按实际文件名重跑后定位，错误收据保留。本机只读核对原生PG17与pg_textsearch1.5.1，D契约套件绑定这个服务器上的一次性测试库/临时角色，不改旧实验DSN或业务库内容。22/22通过（pytest4.26秒，总5.464秒），再跑完整门禁：**2505 passed、70 skipped**。

检查过程中两次用快照cwd读取原仓库.local脚本，出现No such file；脚本实际位于原工作区，纠正读取位置。它们是只读检查命令错误，不计作验证通过或代码缺陷。

## 3. 最终验证与追溯

| 核验 | 实际结果 |
| --- | --- |
| 新旧隔离用例 | 182 passed，pytest1.14秒，总1.625秒；新增61隔离用例，后按职责分离CLI测试文件 |
| 备份/Compose/worker失败项 | 21 passed，含新增快照反例；原生产worker不变 |
| 原生D契约 | 22 passed；一次性数据库/角色清理，无业务库DML |
| 最终required-services make check | 退出0，2505 passed、70 skipped、1 warning；pytest139.98秒，总146.602秒 |
| 格式/类型/架构/断言 | 728文件 / 338源文件 / 338模块0违例、2既有例外 / 284文件0违例 |
| 三套实际CLI | 9/9、6/6、6/6 true，全部0 model calls、qualification unknown |
| 文档测试 | 初次41 passed；最终41 passed，pytest3.3秒，总3.976秒 |
| 文档/范围审核 | 143任务ID保持，231本地链接/10片段通过，717未改输入保持；18条路径、原canary/worker/S0/ADR字节核对 |

最终70 skip是原B/C可选实验依赖，必需PG/Redis/Docker及本轮D均已运行；warning为既有JWT负例故意短HMAC key。评测审计仍报告2个unmappable miss、历史安全回放不能替代新集、独立人工缺口与没有未见盲测；分母/Schema保持。

720既有维护输入中，只改contracts、__main__、旧worker测试三项；717其余字节保持，新增7个Python维护文件。旧canary文件、worker生产文件、PLAN-02/ADR/S0规格及家族示例保持；公开参考JSON与实际合成canary参数及hash核对。原根目录同步/暂存/提交tree绑定后才发布，无output/pdf、凭据或本机收据。

## 4. 八项强制自审核

| 自审项 | 结论 | 证据与限制 |
| --- | --- | --- |
| scope | 通过（本轮范围） | EVAL-33私有参考筛查/回执与方法文档，关联修复strict校验和已证实旧测试竞态 |
| ADR_and_stage | 通过（本轮范围） | D-01/D-02、保管pending；EVAL-33 IN_PROGRESS、EVAL-32 BLOCKED，未进S2 |
| correctness_and_failures | 通过（本轮范围） | 数字/否定、边界/绑定/超限/缺口反例；bool漏洞与跨状态测试已复现修复 |
| permissions_and_data | 通过（本轮范围） | 没有新盲测/历史正文或gold读取，无公开私有配对出口，资格始终unknown |
| budget_cancellation_side_effects | 通过（本轮范围） | 0托管费用，业务库仅只读探测；临时测试资源清理，无部署/激活 |
| traceability_and_versions | 通过（本轮范围） | 基线、策略/来源/计划摘要、失败补救和收据可定位；非正式预登记证明 |
| verification | 通过（本轮范围） | 182、21、22定向及最终2505/70全量，三套CLI；保留失败/额外skip定位 |
| status_and_documentation | 通过（本轮范围） | 参考参数未正式批准，解析/真扫描/穷尽/身份未完成，部分范围回填台账 |

## 5. 限制、回滚与下一步

本轮没有实际历史解析器、源发现、解密、访问鉴权、真实回执签发、审计先于披露编排或全历史覆盖。没有正式校准、语义/跨语言相似检测、完整家族关系、真实新盲测或独立人工。私有配对ID与hash也不能公开；当前resource上限是离线参考边界，不是运行吞吐/Agent SLA证明。

下一切片准备历史来源清单与实际schema字段适配器，先在公开合成文件验证完整读取、坏行、限额、取消及错误不泄漏；实际新题接入先落实所有者保管安排。PLAN-02仍需明确裁决；所有模型费用逐次授权；实验自动激活和原生产批准规则保持。

按功能分批提交18路径，核对根目录/快照/tree及实际SHA的CI。代码未接生产，无迁移或业务重启；回滚本轮提交即可，原账本/冻结资料不删除或改写。本轮检查耗时不是模型训练/真实API时延。
