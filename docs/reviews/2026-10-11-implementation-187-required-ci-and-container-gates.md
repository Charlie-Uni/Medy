# 记录187：ARCH-14 必需 CI 依赖与容器启动门禁

- 日期：2026-10-11；实现/自审核：Codex，同一实现者，非独立人工。
- 主任务：ARCH-14；对应 DEPLOY-02、运行完整性及架构可维护/可追溯要求。
- 开始状态 READY → IN_PROGRESS → REVIEW；工程自审通过后归 DONE，远端CI实际执行继续记为待验证。
- 起始 HEAD：`69fca598e405423b14f7a04e9336bdadc8f33163`，本轮HEAD不变。37个已有修改/未跟踪文件逐个备份；记录185/186改动保留，均未提交。
- 授权：所有者“继续”，仅使用无托管费用开发/核验权限。0模型API调用、0 USD；未推送、未替换共享服务、未迁移业务库。
- 行为契约：[CI_GATES](../CI_GATES.md)；机器证据：[结果JSON](2026-10-11-implementation-187-results.json)。

## 1. 原因与范围

原CI启动PostgreSQL/Redis，但fixture捕获连接失败后仍skip。基础依赖jieba也被importorskip包住；Compose检查会尝试读取开发者私有.env。CI没有显式架构步骤及真实运行镜像启动检查。因此服务坏掉或镜像丢失已发布词表时，原检查可能给出缺失关键证据的成功结果。

本轮保留模型、冻结数据/gold、分母、质量与性能门槛、生产策略指针、ACL和预算合同；工程门禁补充不代表业务验收。

## 2. 改动

| 路径/职责 | 实现 |
| --- | --- |
| `tests/service_requirements.py` | CI/GITHUB_ACTIONS/显式required任一成立则必需；CI不能由0退出；非法模式报配置错；只输出固定原因/异常类型 |
| `tests/integration/conftest.py` | 必需模式只接受显式测试URL，不读开发.env；PG/Redis缺失、格式或连接错误失败；PING不成功失败；Redis探测连接关闭 |
| 11个词法测试文件 | 移除jieba跳过保护并整理相关导入；它是requirements.lock基础依赖。B/C/D服务器可选规则保留 |
| `tests/unit/deploy/*` | 实际pytest子进程退出码、CI不能opt-out、模式验证、Docker/Compose缺失、无.env渲染、HTTP早关与随机端口回归 |
| `.github/workflows/ci.yml` | 必需开关、显式架构检查、实际镜像构建、公开模型缓存/固定revision下载、internal网络容器启动、失败清理；job上限45分钟 |
| `scripts/ci_download_models.py` | 只下载两个固定revision公开模型的运行文件，包含BGE-M3所需pytorch_model.bin；不下载语料或题目 |
| `deploy/ci/released-policies.json` | 当前已发布hybrid配置公开快照；仅复制到临时库，测试批准身份明确为ci:fixture |
| `deploy/ci/test_container_boot.py` / `http_probe.py` | 真实临时DB、部门BM25、BGE向量与默认API启动；容器内loopback检查200/503与UID；0模型预留，私有失败诊断和清理 |
| `Makefile` / CI与部署文档 | 明确必需/可选模式，增加独立ci-container-check，纳入deploy/ci格式检查，更新状态/入口/限制 |

公开配置逐内容只读核对，与本机当前released检索配置一致。测试策略生成新的ID并使用测试批准者，不借用生产批准者或切换生产发布指针。模型缓存只读挂载；环境文件0600，失败原始诊断0600且不输出/上传。

## 3. 真实容器核验

镜像复用记录186最后构建的 `sha256:04a5d57fa4c6f5973129b48d74cb082abad407817a0f669128a871822e7ff3dd`，Linux arm64。本轮没有改生产源码、Dockerfile、构建锁或词表；记录186已逐字节核对218个安装模块，本轮保护核验继续一致。

先在本机已有测试服务器上用临时数据库核验；随后使用另一个一次性PostgreSQL17+pg_textsearch1.5.1容器、internal专用网络、宿主随机映射端口和CI文件选择规则重现CI网络。公开模型缓存用16个所需文件组成，没有README、其他revision或宿主的额外配置；硬链接只读使用，测试后删链接，原缓存保留。

结果：

- 两次成功门禁均使用真实BGE-M3生成合成chunk的1024维向量，真实部门BM25，默认API命令加载BGE-M3与reranker。
- `hybrid@2026-09-30-c41bd6d8` 从临时库发布指针读取；指定词表在镜像中可加载。
- UID=10001，`/healthz=200`、`/readyz=200`；删除临时向量后`/readyz=503`，存活仍200。
- API只在容器内loopback探测，不依赖internal网络宿主端口映射；DB内端口固定5432，不沿用宿主随机端口。
- 两容器顺序执行，内存上限4GiB/CPU2/128pids；这只证明合成启动核验能完成，未验证业务负载或全部服务并驻容量。
- private网络复测pytest **1 passed，25.89s**；含准备/清理 **28.693s**。私有PG、网络、临时模型目录、测试API/索引容器、临时LOGIN用户及数据库清理成功。
- 没有调用Ask；OpenAI地址为无服务回环端口、合成不可用key、月预算0，模型费用预留表为0行，托管调用0。

## 4. 失败与补救（保留原失败）

| 观察/原文 | 为什么发生 | 修复与复测 |
| --- | --- | --- |
| Ruff首次12项问题（I001/F401） | 移除skip后留下导入位置/空行和无用pytest导入 | 仅整理本轮关联导入；最终lint/format通过 |
| `ModuleNotFoundError: No module named 'yaml'` | 工作流静态解析误用系统python3，仓库依赖在venv | 使用venv/bin/python；YAML解析和20个run步骤bash -n通过 |
| 初稿公开下载规则漏BGE-M3的pytorch_model.bin | 只考虑safetensors；实际固定模型在该revision使用bin | 文件清单核对后纳入bin；16文件受限缓存真实启动通过 |
| `http.client.RemoteDisconnected: Remote end closed connection without response` | 宿主端口发布早于uvicorn监听，探测只捕获部分网络异常 | HTTP协议早关/重置/超时作为待就绪，但保留总时限；四条回归、真实启动通过 |
| `RuntimeError: Docker port exit 1` | 第一轮private实验将PG只接internal网络，宿主端口不可用；API方案也错误依赖宿主发布端口 | PG保留用于测试fixture的bridge端口并另接internal；API在容器内探测；真实private网络通过 |
| bridge第一重试 `container gate command failed: run (exit 1; raw output withheld)` | 原探测有意不输出raw日志，因此该次不能单凭固定消息确认细节 | 保留该次日志/退出码；增加可选0600原始诊断。公开临时模型目录从700调整为UID10001可读；日志未证实权限是该次失败原因 |
| 后续私有诊断 `psycopg.OperationalError` / `Connection refused`，端口53941 | 宿主随机端口误带入容器到PG的DSN，容器实际监听5432 | 使用容器内5432；端口回归和完整private网络复测通过 |
| 自审发现显式URL可能绕过非法required值验证 | URL先返回，模式只在回退/失败时解析 | 模式先验证；新增显式URL非法模式反例，全量最终包含此测试 |

本地`.local/arch14/`保存初始备份、初次容器失败、private网络多次失败、private raw诊断（0600）、各轮门禁日志与源摘要；都不入Git。两轮先前make check通过后，本轮继续修复发现的门禁缺陷，再对最终输入重跑，最终结果见下一节。

## 5. 最终验证与环境

注册隔离工作树位于仓库外、非iCloud路径；由HEAD加所有工作区修改组成，venv外部链接，PYTHONPATH明确指向该快照。私有.env/.env.dec001仅在本地复制为0600并核对相同，所有测试命令移除非法继承的DEBUG。显式required PG/Redis URL通过进程环境注入，不写命令或日志。

| 核验 | 最终结果 |
| --- | --- |
| 定向早期词法/服务/Compose/探测回归 | 63 passed / 10.25s；此后两个模式/端口反例进入最终全量 |
| `make check`（required=1，两条显式服务URL） | 退出0；2157 passed、70 skipped、1 warning；pytest69.01s，总72.56s |
| Ruff/format | 通过；516维护Python文件已格式化 |
| mypy / architecture | 218源文件通过；218模块、0违规、2条既有精确例外 |
| 冻结评测审计 / Schema | 4数据集PASS；Schema up to date；既有人工/盲测/2 unmappable警告保留 |
| 70 skips解释 | 可选B/zhparser45条、C/pg_search25条；二者不可达，D可达。required基础服务没有skip出口；可选规则保留 |
| YAML / Shell | 解析通过；20个run步骤bash -n通过。没有运行远端GitHub Actions |
| 输入摘要 | 556维护输入在本树/隔离快照SHA-256一致 |
| 以前未提交内容 | 24个受保护的非文档路径字节一致；本轮允许改Makefile和已有Compose测试，文档按实际状态更新 |
| HEAD / 冻结文件 | HEAD不变；evals及schemas的Git diff为空 |

唯一pytest warning来自既有测试合成JWT短key，不是实际身份key。真实启动只核验Linux arm64；工作流Linux amd64冷构建、公开模型网络下载及远端CI运行保留DEPLOY-02外部证据缺口。

## 6. 八项自审核

| 项 | 结论 | 本轮核验依据 |
| --- | --- | --- |
| 需求与范围 | 通过 | required失败、optional保留、已发布配置真实容器启动、架构显式门均有实现和对应故障/正常证据；原质量门槛不变 |
| ADR/阶段硬门 | 通过 | 仅修执行门禁；ADR-0012、PLAN-02待决、S2/S3、实验限定激活、盲测与生产签字要求保持 |
| 正确性/失败路径 | 通过 | 缺失/错误/连接失败非零；CI不能opt-out；Docker/plugin错误；HTTP早关、private网络/端口及索引丢失已修复复测 |
| 权限/数据 | 通过 | 独立临时库/用户，真实app/admin角色；公开配置/合成批准标明；秘密文件0600，raw诊断不上传，冻结/ACL不变 |
| 预算/取消/副作用 | 通过 | 0托管调用；回环provider/合成key/预算0；检查超时有界，finally回收本次容器，CI always清理只按测试标签；共享服务未替换 |
| 追溯/版本 | 通过 | HEAD、公开发布版本、镜像ID、556输入SHA与每轮失败/成功日志定位；没有虚构新生产发布 |
| 验证充分性 | 通过 | 最终全量与真实网络/模型/index故障匹配本轮风险；未将arm64工程证据扩大到amd64、答案质量或容量 |
| 状态/文档 | 通过 | CI契约、台账、README、阶段及部署/架构入口同步；本地工程/远端CI/生产发布状态分别登记；最终文档机械核验已随JSON追加 |

## 7. 完成状态、回退与下一步

ARCH-14工程实现与自审通过；DEPLOY-02仍须在最终提交上执行远端CI、目标机器资源/故障/备份恢复验证。没有生产发布批准、真实医学质量或长期部署结论。

ARCH-12解除ARCH-14工程前置，下一轮先做零托管费用的事务/连接诊断与方案；有实际收益再实施。CODE-04/05/07仍按台账穿插。PLAN-02剩余Agent契约、真实语义校准、独立人工、新未见盲测、Task/MCP完整回放与S2/S3仍未完成。

回退本轮可按功能恢复工作流、测试mode helper/fixture、下载与容器gate；不会还原记录185/186或修改数据库生产发布记录。开始备份保留每个已有修改的原字节。代码仍在工作区；提交/推送等待相应授权。

耗时包含iCloud工作树读取等待、环境误用返修和private网络故障排查，机器JSON记录真实墙钟时长。没有新增付费或业务范围决定；剩余DEPLOY-02目标环境资源和PLAN-02业务/验收决定按现有人工项处理。

最终文档核验：8文件、180本地链接有效、141任务ID全部保留，仅ARCH-14/ARCH-12两行任务改变状态/依据；文档回归27 passed / 1.21s，退出0。八项工程自审最终通过，远端CI仍待实际执行。
