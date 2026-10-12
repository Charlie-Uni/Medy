# 记录196：恒真断言核验与错误检出能力

2026-10-12，CODE-02；HEAD61509bc，CODE-01三批已推送，当前远端CI单独核对。实现者/自审者Codex，同一模型，不是第二独立人工。主要核验测试判别能力和补静态防回归；另修复全量门禁现场复现的worker停止探测缺陷，不改业务作答规则、gold、评分、预算、模型、角色或生产策略。本轮0托管调用/0USD。

## 核实历史和当前源码

代码质量审查指向回放/超说明书两处 `or True`，Git可核对原文：

- 历史回放断言尾部 `and report["replay"]["run_id"] == report["replay"]["trace_id"] or True`，无论前面结果如何都真；且run ID与trace ID本来应不同。[2f09218](https://github.com/Charlie-Uni/Medy/commit/2f092181314e2825b5d0ab7fa575b81cedc75a51)在ARCH-07替换为两个明确不相等的断言。
- 历史Skill断言 `"建議" not in "".join(f.note for f in out.findings) or True` 不能阻止错误。[8372cd6](https://github.com/Charlie-Uni/Medy/commit/8372cd6297d4b06b8fa6733d840ba248d30a7868)在ARCH-03增加具体剂量依据与最终判断核验；原不建议/错来源/错部门和最终语义负例继续保留。

本轮不把前两轮已修内容重复计算为新业务修复。当前tests扫描未发现已知恒真形式；`test_maintenance_worker`的 `observed.update(...) or True` 是假consumer返回值，不是assert，保留其行为。

## 防回归及反例

新增 `scripts/check_test_assertions.py` 使用AST，只检查可静态判断为真的字面量/布尔组合/not/条件表达式，不执行测试源码。拒绝 `assert ... or True`、`assert not False` 和真字面量；保留有实际条件的断言、用于负例的 `assert False` 与字符串示例。Makefile与CI显式必需检查，docs hygiene也覆盖。不是任意Python表达式恒真证明或全测试质量度量。

在仓库外验证树分别注入两个错误，仅修改测试运行的源码，每个finally恢复原字节并核对SHA、清理自己的pyc；原工作区的两个业务模块不变：

1. `_side`错误地把run_id写为trace_id。现有回放测试退出1、1 failed，失败就在 `assert report["replay"]["run_id"] != report["replay"]["trace_id"]`。
2. 最终Skill输出把剂量note改为 `mutation: missing rationale`。现有测试退出1、1 failed，失败就在 `assert by["dose"].note == "12 mg 超過每日最高 8 mg"`。

静态CLI的坏assert退出1、正常条件退出0、空输入退出2；不允许空扫描冒充通过。两次变异失败是预期证据，不是未修业务缺陷；不按错输出重写期望。

首次定向命令误写不存在的 `test_judgment_verification.py`，pytest退出4、无测试运行；核对实际文件后改为 `test_final_judgments.py`。正确定向docs/replay/risk/final judgment为71 passed，pytest4.33秒、总4.881秒。最终required全量退出0：**2276 passed、70 skipped、1 warning**，pytest85.51秒、总89.644秒；679文件格式、mypy325、架构325模块0违例/2既有例外。静态assert扫描248测试文件0违例，4套冻结审计与公开Schema通过；678维护输入SHA与独立验证树一致。70可选B/C skip与测试短HMAC warning保持，不是缺必需依赖。

## 全量现场缺陷与补救

首次required全量退出2：2273 passed、1 failed、70 skipped、1 warning，pytest83.81秒、总111.473秒。失败原文 `PermissionError: [Errno 1] Operation not permitted`，位于 `supervision.stop_child` 的 `os.killpg(child.pid, 0)`。不是CODE-02断言不成立，而是实际停止过程抛错。

20次只运行合成sleep子进程的本机复现中2次观察到退出后的短暂探测EPERM，后续探测可消失；单独原监督测试又通过。基于复现推测退出可见性竞态，尚未确认具体内核分支，不能宣称所有EPERM原因均相同。[Apple killpg文档](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/killpg.2.html)区分权限失败与找不到进程组，因此不把EPERM当成ESRCH。

探测PermissionError现在只在既有grace内重试，最后仍需SIGKILL成功或ESRCH；永久权限失败继续抛出，生产CLI按原规则记录固定异常类型并失败退出。不增加grace、不改ready/健康标准，也不吞初次SIGTERM或最终SIGKILL的授权失败。期限末已经不存在的组不再误报forced=true。新增两个确定性反例覆盖短暂/持续失败；真实进程的TERM/KILL、进展与不重叠测试继续保留。

准备仓库外验证树时iCloud读文件迟滞，调用方未等复制校验结束便启动测试：81 passed、2 failed读到了旧supervision实现。该次不作为候选结论；停止自己的迟滞读者、顺序重新准备，核对678输入SHA相同后再运行。私有准备脚本一次插入进度标记造成语法错误，已修正并成功运行；不改公开门禁。变异后的源码恢复与最终校验不是根据一次绿色推断。

修复后的正确顺序定向检查：83 passed，pytest6.51秒、总7.086秒。CODE-01的61509bc远端[CI38192411532](https://github.com/Charlie-Uni/Medy/actions/runs/38192411532)全部28步骤通过，含新原生backup/restore、运行镜像和真实容器门。

文档41 passed（1.69秒、总2.113秒），142任务集合保持，本地链接存在、冻结/迁移/Schema/策略tracked diff为空；README最新入口更新，旧轮次快照保留。

机器证据：[记录196结果](2026-10-12-implementation-196-results.json)。

## 八项自审核

| 项目 | 状态 | 证据/范围 |
| --- | --- | --- |
| 需求/范围 | 通过 | 核实两历史缺陷已修，补静态防回归/实际变异；门禁现场监督探测缺陷同轮修复 |
| ADR/阶段门 | 通过 | 原门禁未降，Agent/盲测/付费/生产签字边界保持 |
| 正确性/失败 | 通过 | 两业务错误各被原断言检出；静态1/0/2；短暂探测重试、持续权限失败不冒充停止 |
| 权限/数据 | 通过 | 改repo检查与worker退出探测；变异位于独立树，未改业务作答模块/数据库/冻结资料 |
| 预算/取消/副作用 | 通过 | 0托管调用，无运行模型预算变化；变异finally恢复原字节/清理pyc |
| 追溯/兼容 | 通过 | 两历史SHA与错误行可追溯；新静态必需门明确有限范围 |
| 验证充分性 | 通过 | 最终83定向、2276/70全量、678输入一致；两个预期变异失败，248文件静态0违例，冻结/Schema通过 |
| 状态/文档 | 通过 | IN_PROGRESS→REVIEW→工程DONE；台账/CI契约与失败迭代同步，不冒充独立人工 |

## 限制与下一步

静态检查不分析动态调用、常量跨模块传播、任意比较式或语义冗余，不能证明剩余全部断言有充分覆盖。两变异只证明指定错误当前会失败，不是全程序变异得分。本轮强化工程测试，不补齐医学质量、第二人工或未见盲测。下一CODE-03核实死代码/重复设置契约，然后CODE-06测试夹具治理；PLAN-02仍需所有者冻结行动/profile与EVAL-32验收。

回滚仅新静态门/检查与文档；不要把已经修正的历史断言还原为恒真。生产未重启，新CI以最终推送SHA核对。

## 分批提交

- `6da62e1`：supervision，2个路径，精确暂存/cached diff通过。
- `49dfe7e`：assertion-guard，4个路径，精确暂存/cached diff通过。
- 第三批文档包含README当前入口、台账、CI契约及本轮自审/机器证据；最终SHA由Git查询，远端结果按该SHA核对。
