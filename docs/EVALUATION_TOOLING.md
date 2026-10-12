# 评测工具入口、共享机制与历史兼容

CODE-05；2026-10-12。实现与失败修复见[记录193](reviews/2026-10-12-implementation-193-evaluation-tool-packaging.md)。评测、运行器和实验适配器属于 `medops.evals`，不进入生产检索依赖。

## 1. 在哪里维护

79个原维护模块迁入 `src/medops/evals/tools/`。其中67个可执行命令在原 `evals/**/tools/` 文件位置保留薄入口，只导入规范模块的 `main` 并保留原退出/清理行为；另外12个辅助/起草模块不再保留转发壳。

| 分组 | 规范包 | 职责 |
| --- | --- | --- |
| 主集 | `medops.evals.tools.main_set` | 候选、起草、页锚定、复核、裁决应用、组装与冻结 |
| 探针 | `medops.evals.tools.probe` | 后继组装、冻结；既有 validator/review 协议仍在 `evals.probe` |
| 实况运行 | `medops.evals.tools.harness` | Ask/Skill/安全/容量/故障运行，答案与来源诊断 |
| 回放 | `medops.evals.tools.replay` | 回放集、召回诊断、诊断回放运行 |
| 安全集 | `medops.evals.tools.safety_set` | 起草、合成文档、审计、复核、标注表和冻结；起草模块在 `.authoring` |
| 核验实验 | `medops.evals.tools.verifier` | 规则/CLI/gateway 各实验臂及比较、模拟 |
| 术语 | `medops.evals.tools.glossary` | 术语/概念表构建 |
| 词法快照 | `medops.evals.tools.lexical` | 导出固定 chunk 快照；候选适配器仍在 `medops.evals.experiments.lexical` |

例如以下两个入口执行同一个 `main`：

```sh
venv/bin/python evals/harness/tools/smoke_ask.py --help
venv/bin/python -m medops.evals.tools.harness.smoke_ask --help
```

本例仅展示帮助。执行真实问答、生成和复核需本次范围、费用上限、停止条件授权，不能因入口可导入就直接运行。先按仓库 `make install` 安装包；维护代码不再注入 `sys.path` 或按文件名加载兄弟脚本。默认数据、Schema、历史产物仍位于仓库，以单一 `evals.paths.REPO` 定位；此轮没有把它们打包成可脱离仓库运行的 wheel 资源。

原辅助 Python 导入迁移：`main_set/tools/draft_common.py` → `medops.evals.tools.main_set.draft_common`，`verifier/tools/common.py` → `medops.evals.tools.verifier.common`，安全 `tools/authoring/*` → `medops.evals.tools.safety_set.authoring.*`。旧可执行文件名、参数、默认模型/数据/日期保持；原辅助导入路径有意移除。历史代码可通过[迁移前68783f0](https://github.com/Charlie-Uni/Medy/tree/68783f0f617298069107ceaea1a9d8796094e69b/evals)查看。

`Makefile CHECK_PATHS` 包含所有维护入口及 `src/tests`，新包进入正常 Ruff/mypy/架构检查；未加忽略目录或宽泛类型豁免。历史 `drafts/v*/tooling` 和冻结数据继续保留原文，不受活跃代码格式化影响。

## 2. 哪些机制共用

| 模块 | 共享内容 | 由调用方保留的规则 |
| --- | --- | --- |
| [bootstrap.py](../src/medops/evals/bootstrap.py) | 单推理子进程、embedding、按输出大小复用重排视图、预算 gateway 与 meter | 数据/索引预检、实际发布策略、逐执行预算上下文、运行上限及停止条件、关闭生命周期 |
| [transactions.py](../src/medops/evals/transactions.py) | 调用者连接的事务、`SET LOCAL medops.dept`、DeadlineConnection | SQL内容、查询参数、管理/普通身份的选择；不建立新池或绕过RLS |
| [fact_lookups.py](../src/medops/evals/fact_lookups.py) | 管理员只读事实查询；重判每个库只打开一个连接 | 这是离线裁判核对权限/版本的管理平面，不是用户召回路径；普通检索仍使用app身份/RLS |
| [files.py](../src/medops/evals/files.py) | UTF-8 JSONL、显式键排序、临时文件替换 | safety原排序格式与复核原非排序格式分别保持；原文/规范哈希语义不混用 |
| [freeze.py](../src/medops/evals/freeze.py) | 文件哈希、SHA256SUMS、manifest转换及失败恢复 | 主集/探针各自人工确认、provisional资格、退出码/错误输出、manifest键顺序 |
| [successor_review.py](../src/medops/evals/successor_review.py) | 复核JSONL、去重、prompt绑定、latest索引与合并offset | 主集/探针的准入、人工裁决、跨版本和归档输入查找规则 |
| [review_wire.py](../src/medops/evals/probe/review_wire.py) | 13个复核prompt/哈希/解析/恢复/绑定函数 | 历史模型运行脚本保留原文；新共享模块不启动模型CLI |

三个实况运行器共享启动机制，初始运行仍要求执行预算；启动后装配失败会回收已创建推理子进程。构造 gateway 没有发出请求。部门事务沿用原连接和局部身份，成功/异常后不会把该轮部门设置泄漏到下一事务。

安全重判原 `setdefault(name, _AdminPlane(name))` 会先求值默认对象，即使已有键仍打开连接。现用按需创建＋ExitStack，成功和异常均关闭；三个事实查询方法SQL及AST保持一致。MPS缓存清理原把Python函数传给字典消息协议，现通过 `empty_cache` 操作在拥有权重的子进程执行；CPU为无操作。真实spawn/CPU及模拟MPS分支已验证，未测实际MPS硬件容量。

## 3. 字节、复核和冻结边界

57个真正调用 `parse_args` 的命令，迁移前后 `--help` stdout（仅归一化工作树绝对路径）与退出码一致；10个没有参数解析的旧命令不会把 `--help` 当只读操作，应按其具体职责执行。67个原可执行入口均保留，smoke/safety 的 `finally flush` 和perf的Python版本检查保持。

九类安全起草 `rows()` 的170条内容逐字段一致；未来 drafting_provenance 会准确记录新的模块名和源码哈希，不能冒称旧源码。旧草稿、已签复核和冻结产物本轮未重新写入。复核 wire 的13个函数AST与历史原函数一致；JSONL读取另使用严格对象校验，非对象行提前失败。来源不变时沿用旧复核的绑定规则；内容或实际运行条件变更时依照原 `--resume` 检查拒绝复用，没有强制覆盖旧哈希的入口。

冻结仍先校验草稿与人工批准，拒绝已有 `SHA256SUMS`，再写哈希和manifest，最后校验冻结状态。成功时主集非排序、探针排序的manifest字节保持。后校验报错、抛异常或写入失败会恢复原草稿manifest字节并移除本次marker；这是单命令失败恢复，**不是跨两文件的崩溃事务，也不承诺并发冻结写入安全**。共享临时替换没有新增fsync持久性承诺；已有 `run_answer_review` 更强的fsync实现保留。

主集/探针保留不同的归档查找语义：主集允许多个归档根的相同字节，探针要求唯一根。合并只收敛共同mechanics，不改gold、证据组、评分、分母、人工裁决或许可。此轮没有重跑完整真实后继集构建，验证范围为共享函数、既有组装/绑定回归及冻结产物审计。

## 4. 验证、下一步与回滚

本轮仅本地工程回归，0托管调用、0USD；普通LOGIN真实PG部门事务已核验。详细首次失败、全量结果、输入摘要、自审与推送证据见记录193及其机器结果。

回滚需一起恢复规范包、原命令、测试和Makefile；无业务库迁移、索引重建或策略发布。包可维护并不代表Agent、自进化、真实质量或性能门完成。下一CODE-07补观测/MCP受限完整材料；PLAN-02业务行动/profile/EVAL-32契约、第二人工、盲测及逐次付费授权保持。
