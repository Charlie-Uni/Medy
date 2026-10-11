# 实现记录 185：共享重排 scorer 与不可变输出配置

日期：2026-10-11。任务 ARCH-10 / Goal OPT-11。实现与自审核者：Codex，同一实现者，不是第二独立人工。状态 READY → IN_PROGRESS → REVIEW → DONE，八项工程自审通过。机器结果见[185-results.json](2026-10-11-implementation-185-results.json)。

## 1. 授权、基线与问题

用户“现在继续”授权按当前台账推进无付费工程。基线 `69fca598e405423b14f7a04e9336bdadc8f33163`，开始工作区干净，原任务台账和启动信息保存于忽略的 `.local/arch10/`。没有托管模型费用授权，因此本轮没有真实问答/语义裁判/容量 API 请求，也没有提交、推送、迁移、部署或重启服务。

旧子进程以 output 为键缓存 BgeRerankerV2M3：最初 output=8，遇到4/5/12等新输出时再次构造 CrossEncoder。output 只用于取排序后的前N项，CrossEncoder.score 本身为每个候选计算分数，权重、revision、512最大长度、归一化及批大小均不需要随N改变。按输出加载模型会重复持有模型对象，并让灰度配置切换产生额外冷启动。

## 2. 改动与责任边界

- [rerank.py](../../src/medops/retrieval/rerank.py)增加冻结的 RerankerView：持有原 scorer 和独立冻结 spec，仅覆盖 output；不加载权重、不储存用户正文、不改变 score、框架标签或 tie-break。
- [inference_process.py](../../src/medops/retrieval/inference_process.py)的每个 lane 只保留 factory 初始化的一个 scorer，所有 score 请求都交给它；私有Pipe不再发送output作为模型选择参数。ProcessReranker 的 spec 改为只读属性，仍是原 RerankerSpec 字段。
- [bootstrap/retrieval.py](../../src/medops/bootstrap/retrieval.py)沿用既有RLock：同输出视图构造为singleflight，成功后才入缓存，失败不留下坏视图；原输出复用基础scorer。非pinned替身也按真正的output构造视图，修复旧分支返回原spec的配置不一致。
- 接受整数1～max_input，拒绝bool、字符串、浮点和越界，防止True/8.0与已有整数字典键别名匹配。视图数量受原最多20输出值限制。

初始化singleflight分两层：推理lane的factory在子进程主线程只调用一次，score串行复用该scorer；父进程RLock合并并发的同输出视图构造。没有新增全局模型池、线程池、网络服务或跨owner缓存。API/worker/MCP各有自己的lane；不同device/revision/owner不得假设共享一份权重，需分别初始化或重启。

原8在途/250ms准入、调用队列和总截止时间继续保持。任一已发送推理超时/子进程崩溃会停止并回收整个lane，所有视图一起失败关闭；视图切换不自动重启或重试旧工作，恢复仍由监督承担。父进程只创建轻量配置，真实加载与推理仍在子进程主线程。

## 3. 验证、错误与修复

| 检查 | 结果 | 覆盖 |
| --- | --- | --- |
| 定向测试 | 37 passed / 6.61s，退出0 | 真实spawn、多输出并发、冻结配置、初始化singleflight/失败不缓存、invalid键别名、排序/tie-break/前N、共享lane超时与旧取消反例 |
| Ruff/类型 | 最初Ruff I001已修；复测退出0，mypy216源文件通过 | 新测试引用已有settings helper，按仓库第三方/项目分组修正导入；格式检查通过 |
| 真实本地BGE | 离线CPU，4个合成文本，8并发请求/5种输出，加载1次 | 4/5/8/12/20及回切；分数最大绝对差0、spec与原配置一致、主线程加载/推理、进程已回收 |
| 全量门禁 | **2105 passed / 70 skipped / 1 warning，180.95s，退出0** | 504格式文件、216源类型、216架构模块零违例/2精确允许边、四套评测审计、Schema无漂移 |
| 源码绑定 | 537维护输入与注册核验工作树SHA一致，零缺失/不符 | 隐藏测试配置仅比较字节一致，不输出凭据或摘要 |

完整命令：`env -u DEBUG PYTHONPATH=<snapshot>/src:<snapshot> make check`，核验树由 `.local/arch10-worktree-path` 定位；日志 `.local/arch10/make-check.log`。定向测试与CPU真实测试都使用锁定venv，无托管模型调用。

CPU真实对照先在独立进程加载直接调用基线，再在新lane统计构造；“加载1次”指运行lane内，不把基线对照进程算作权重共用。实际reranker参数存储 `2271023108` 字节；child RSS ready为 `865239040`，8请求后为 `1681424384`。RSS包含按需驻留页和推理缓存，与参数字节数不是同一口径；未测旧多副本总体RSS，不宣称整套服务内存下降比例。

该CPU验证用HashingEmbeddingProvider隔离重排成本，不是完整BGE embedding+reranker/API配置的冷启动或容量测量。单次lane启动 10.789秒不能当P95；MPS具体分数、allocation与运行容量本轮未测，主线程dispatch代码保持。真实库/真实模型API质量、时延与费用仍归相应PAID任务。

真实模型日志提示已存在的sentence-transformers cache_dir弃用警告，没有升级库或夹带SDK迁移。全量的70跳过仍为可选DEC-001 B/C环境；认证反例短HMAC warning、2个unmappable gold、旧安全回放、独立人工和未见盲测提示继续保留。

最终文档核验：6份文档、152个本地链接存在，141个任务ID集合及1023个evals/Schema JSON/JSONL输入保持；`pytest -q tests/unit/docs`退出0，27 passed / 5.98s；diff检查通过。台账/记录回填后537维护输入SHA再次一致，没有修改已通过全量门禁的代码。

首次将ruff check与format合并在同一shell命令，末条format退出0不能代表首条ruff通过；按I001实际输出修复并单独复测，未冒称首次lint通过。实际自开始备份到此约14.6分钟，包含实现、CPU实测、隔离全量和文档核验；不作为全项目剩余工期保证。

## 4. 八项强制自审核

| 自审项 | 结论 | 本轮证据 |
| --- | --- | --- |
| 需求与范围 | 通过 | 一个lane一个scorer、输出视图冻结、singleflight、实际加载/内存核验；没有引入全局池或改变原策略 |
| ADR与阶段硬门 | 通过 | 沿既有ARCH-10与每进程owner约束；没有目标/验收变更，PLAN-02、S2/S3、盲测与实验激活门保持 |
| 正确性与失败路径 | 通过 | tie-break与score一致、取前N、并发同配置、回切、坏配置、创建失败、共享lane超时/停止与资源回收反例 |
| 权限与数据 | 通过 | 仍只重排已事实回查的Evidence，不改变ACL/日期/缓存事实层；视图不缓存正文，真实smoke仅合成文本 |
| 预算、取消与副作用 | 通过 | 0托管调用/0USD；沿用队列、总期限与进程回收；未迁移业务库、重启、导出或部署 |
| 追溯与版本 | 通过 | 模型ID/revision/spec/framework与原配置一致；输出仍入原检索版本/缓存绑定；源码与真实计数器、完整日志留证 |
| 验证充分性 | 通过 | 定向37、真实CPU加载/分数/内存和全量2105/70；没有以synthetic smoke替代API质量/容量或独立人工 |
| 状态与文档 | 通过 | ARCH-10由READY/IN_PROGRESS/REVIEW/DONE回填；README/阶段表/装配说明同步；下一主项ARCH-13；其他任务和门保持 |

## 5. 回滚与下一步

本轮改动尚未提交或部署。回滚只撤本轮三份生产模块、三份测试文件及本轮文档差异，以开始HEAD逐文件对照；不能整树reset覆盖后续工作。没有迁移/依赖锁/API Schema回退需要。已运行服务不会因本轮核验自动更新代码，需按部署流程选择发布时点。

下一主切片 **ARCH-13：资源声明、常驻消费者与监督**；ARCH-14的必需依赖CI门随后继续。MCP受限完整材料、Task/MCP及原条件回放、FOCUS-02跨块完整定位、PLAN-02剩余Agent契约、真实语义校准、独立人工、未见盲测与S2/S3未完成。每轮托管模型实验继续单独授权。
