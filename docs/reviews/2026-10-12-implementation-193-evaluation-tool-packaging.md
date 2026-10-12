# 记录193：评测工具打包、共用机制与运行缺陷修复

日期：2026-10-12；任务CODE-05，前置ARCH-07/08的工程范围已通过。实现者与自审者：Codex，同一审核者，不是第二独立人工。用户要求推送完成任务后继续；开始HEAD68783f0、工作区干净，547相关输入备份。该HEAD远端[CI38188078574](https://github.com/Charlie-Uni/Medy/actions/runs/38188078574)全部步骤成功。0托管调用、0USD，无本轮付费授权。

## 1. 交付范围

79原维护模块迁入 `medops.evals.tools` 八个职责包；67可执行原文件保留薄main入口及原footer，12辅助/起草文件去除旧转发路径。活跃代码不再 `sys.path.insert` 或按兄弟文件名加载模块；历史draft工具保留原文。CLI/路径使用见[评测工具契约](../EVALUATION_TOOLING.md)，机器结果提供迁移映射。

收敛三个实况运行器的推理/预算/meter启动、部门事务、JSONL/原文SHA、主集/探针冻结、后继复核合并。保留不同数据集的人工确认/冻结资格/归档根规则，不为了复用统一业务规则。13个复核wire函数从历史probe-v2 runner提取，AST逐项相同；活跃主集调用不再依赖归档脚本，历史模型CLI未改。

原管理事实查询拆出独立只读接口。安全重判的 `dict.setdefault` 默认值被每行提前构造，导致已有库也打开新连接；改成一个库一个连接和ExitStack，正常/异常均关闭。三个SQL方法AST不变。原 `apply_resolutions` 只创建模块spec、未执行模块，无法使用其预期函数；规范包导入消除该加载缺陷。

原MPS缓存清理 `gpu.call(_mps_empty_cache)` 把函数送入字典消息协议；改为拥有模型的子进程执行明确 `empty_cache` 操作。CPU无操作，调用仍受既有排队/超时/取消协议约束；真实CPU spawn及模拟MPS分支验证，不声称实际MPS性能测试。

所有新维护模块纳入正常mypy，修正异构JSON容器、可选查找结果、required row等类型。没有弱化门禁/评分或增加宽泛ignore。Makefile改为覆盖全部维护入口，原归档draft仍排除格式化。16原单测改用规范导入及自动恢复monkeypatch，另补16机制/生命周期/普通LOGIN事务反例，再补1个MPS协议分支测试。

## 2. 实际失败与补救

| 发现 | 原因 | 修复与后续核验 |
| --- | --- | --- |
| 首次工具完整类型检查108处错误、35文件；第二轮33处 | 旧脚本此前不在mypy范围；类型缺失、变量复用、Optional未收窄；同时暴露函数传入消息协议缺陷 | 精确类型与必需值校验，子进程操作修复；最终318源码通过，没有整体忽略工具目录 |
| 首次定向577 passed、2 failed | 共享bootstrap后测试还patch旧运行器局部对象；一份假settings缺db_timeout | patch规范bootstrap、补测试配置；579 passed，无警告；之后新增机制检查595 passed |
| 初次全量lint立即失败，E902旧draft_common不存在 | Makefile仍指向迁移前辅助文件 | 检查路径改为所有维护入口，不删除对应规范模块检查；重跑完整门禁 |
| 初步main-only薄入口丢失清理footer | 自动迁移未保留原可执行结尾 | 自审恢复smoke/safety finally flush、perf版本检查与所有67原结尾；入口静态回归 |
| 最初帮助比较误把10个无parse_args脚本作为只读--help | 这些旧命令忽略参数并执行main | 仅独立基线工作树3个跟踪产物改变，全部恢复Git68783f0原字节；gen_acl_targets只有配置业务库SELECT，无写入/模型；之后AST筛选57个真正帮助命令，全部一致。原工作区数据未改 |
| 一次过宽Ruff指向evals，触碰9个归档draft源码 | 格式化范围包含历史tooling | 原工作区和验证树均恢复Git68783f0字节；后续只用维护入口＋src/tests，最终历史源码无diff |
| 原目录mypy受iCloud读取阻塞 | Documents所在文件系统按需拉取，读取停顿 | 停止自己的阻塞reader，使用仓库外同源工作树；逐输入SHA核对后运行相同门禁 |

本轮没有把首次失败版计作完成。误执行/过宽格式化及恢复保留在记录，不以最终绿色掩盖它们。

## 3. 验证

- 最终定向：**595 passed，17.49秒，总18.568秒**；包含评测包、真实spawn、冻结回滚、复核合并与普通LOGIN部门事务。之后新增模拟MPS测试并纳入全量门禁。
- 57个CLI `--help` stdout/退出码迁移前后一致（仅工作树路径归一化）；67原可执行路径均存在。10个不解析参数的main未再次执行帮助；它们按入口/职责回归核验。
- 安全九类起草170条 `rows()` 内容一致，摘要 `8a8413da5fd964ed46d44489c5137246e96b1b1ae21edd59ef23c96fcb7f8b87`。13个wire函数、3个只读事实方法AST一致。
- **required `make check`退出0：2240 passed、70 skipped、1 warning；pytest85.91秒，总91.257秒。** Ruff/666文件格式、mypy318、架构318模块零违例/2既有精确例外通过；4套冻结数据审计与公开Schema无漂移。70项是可选B/C服务器实验，1 warning来自测试用短HMAC密钥，不称新的业务故障。
- 仓库外工作树**665维护输入SHA与原目录一致，零不符**。本轮只对维护输入作该比较；不宣称重新完成iCloud原目录所有历史JSON逐个下载/哈希。历史draft源码、冻结JSON/JSONL、Schema与评分规则无Git差异。
- 文档后补查29 passed，2.28秒（总2.712秒）；142个任务ID/集合保持，218个本地链接有效。完整命令/映射/失败记录见[机器结果](2026-10-12-implementation-193-results.json)。

没有重跑真实后继组装/质量对照、升级业务库、重建共享索引、启动部署或托管模型。套件数据库为自己创建的临时库；真实部门事务使用普通app LOGIN。冻结数据、gold、分母、模型/发布策略和权限规则保持。

## 4. 八项自审核

| 项目 | 状态 | 证据/边界 |
| --- | --- | --- |
| 需求与范围 | 通过 | 79模块职责包、67旧CLI、12辅助去壳、共用mechanics；归档源码恢复 |
| ADR与阶段硬门 | 通过 | 不改变评测/Agent目标；PLAN-02和S2/S3前提保持 |
| 正确性与失败 | 通过 | 类型、旧测试patch、MPS协议和重判连接缺陷已修；冻结错误恢复/重复绑定拒绝 |
| 权限与数据 | 通过 | 原连接SET LOCAL/RLS保持、普通LOGIN反例；管理裁判read-only与用户通道分开 |
| 预算、取消与副作用 | 通过 | require_execution_budget、run cap不变，失败bootstrap回收子进程；0托管调用；帮助误执行影响已恢复 |
| 追溯与版本 | 通过 | CLI/170内容/13wire/3SQL方法对照，未来模块源码provenance准确更新；不伪造旧复核 |
| 验证充分性 | 通过 | 595定向、57帮助/170起草/AST对照、required全量2240/70及冻结/Schema通过；跳过与质量/MPS容量缺口明确 |
| 状态与文档 | 通过 | IN_PROGRESS→REVIEW→工程范围DONE，契约/记录/台账与下一项同步；自审不等于独立第二人工 |

不适用及理由：本轮没有医学质量裁决、付费盲测、候选生成/激活和生产发布；不授予相应完成状态。

## 5. 限制、下一步与回滚

冻结失败恢复是本地两文件的正常异常补救，不承诺进程死亡或并发写入事务；临时替换不增加fsync保证，原更强实现仍独立。模块默认资源仍依赖仓库，未交付独立wheel数据包。旧辅助Python路径删除，外部脚本须改规范导入；旧67命令兼容。未来源码provenance会改变，不重写旧结果冒称原条件。

下一CODE-07补观测职责和MCP受限完整材料；原条件回放/FOCUS-02跨块定位、PLAN-02行动/profile/EVAL-32、第二人工与未见盲测仍待。回滚须同时恢复包、命令、共用机制、测试及Makefile，无业务数据库回滚或生产策略变更。

## 6. 按功能分批提交

先提交七批代码/回归，再独立提交本轮契约、台账及证据；没有按作者拆分重叠文件。最终验证是上述完整树，不声称每个中间提交都单独跑了全量门禁。

| 批次 | SHA | 内容 | 路径数 |
| --- | --- | --- | ---: |
| 1 | `2bdda66f8c3f` | fix(inference): use typed child protocol for MPS cache maintenance | 2 |
| 2 | `960bef67f500` | refactor(evals): share bootstrap transactions facts and review mechanics | 15 |
| 3 | `84ae99da1fde` | refactor(evals): package main and probe tools with compatible commands | 69 |
| 4 | `7c9eabadd72d` | refactor(evals): package harness commands and preserve cleanup | 34 |
| 5 | `fbfcad3a23fb` | refactor(evals): package safety tooling and authoring sources | 38 |
| 6 | `d5fee35bdfda` | refactor(evals): package verifier glossary and lexical tooling | 27 |
| 7 | `7bc5365af50f` | test(evals): verify package bindings freeze recovery and resource lifetimes | 20 |

第八批文档提交的最终SHA由Git给出，推送后远端CI按该SHA核对，不预填成功。排除output/pdf、环境凭据与.local核验产物。
