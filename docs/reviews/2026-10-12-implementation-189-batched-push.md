# 记录189：已完成架构任务分批提交与推送

日期：2026-10-12。任务W-03/W-04；实现者和自审核者均为Codex，不是第二独立人工。所有者授权“推送已完成任务，然后继续”。

## 范围与批次

开始HEAD为`69fca598e405423b14f7a04e9336bdadc8f33163`，暂存区为空，66个实际文件待提交；另外13个既有提交尚未推送。依据已完成记录185～188按依赖拆为五批，逐文件备份、SHA核对、Python语法、暂存路径/tree、diff空白和凭据模式检查。排除output/pdf、私有.env、缓存、备份及本地产物。

| 批次 | 提交 | 内容 | 文件数 |
| --- | --- | --- | ---: |
| 1 | `69cce16e2b5d` | refactor(retrieval): share reranker weights across frozen output views | 8 |
| 2 | `4c0a1bca3e07` | feat(workers): supervise progress and isolate scheduled maintenance | 19 |
| 3 | `d151e341f7a7` | ci: require service dependencies and verify the production container | 27 |
| 4 | `558a5d998ba4` | test(database): assess transaction lifetime and final fact freshness | 6 |
| 5 | `80cba0a52537` | docs: synchronize audited architecture results and remaining gates | 6 |

所有五批及既有13提交已推送。工程提交HEAD与`git ls-remote origin refs/heads/main`均为`80cba0a52537e32153e5976fdae9b8a949305914`。本记录/台账作为随后一批文档提交；其提交号由git log查询，推送收据留在本地，避免在自身内容里写自身哈希。

## 验证与故障补救

559项维护输入与记录188最后通过的快照逐字节一致。10月12日重跑required服务全量make check：退出0，2163 passed、70 skipped、1 warning，pytest72.25秒、总76.362秒；Ruff519文件、mypy、218模块架构边界零违例、四个数据集及Schema检查通过。70跳过仍属可选B/C词法实验，必需PG/Redis没有跳过。

凭据扫描第一次把task文件名内部的sk-误认为密钥前缀；收紧词边界并复扫，未发现凭据。前四批提交不回退，修正扫描后续提第五批。

两次Git打包停滞，sample栈停在loose_object_info→mmap；主动终止，远端仍是旧HEAD，无force或历史重写。外部缓存新建远端裸克隆、复制821个10月11日以后生成的松散对象，使用外部GIT_OBJECT_DIRECTORY推送退出0；远端SHA核验一致。保留原仓库和本地对象。

CI已触发：[工程提交运行](https://github.com/Charlie-Uni/Medy/actions/runs/38182444634)，此记录时in_progress；不能记为远端通过。没有替换共享API/worker服务，没有部署。

## 八项自审核

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 需求与范围 | 通过 | 66文件五批，无输出或临时产物；既有13提交一并推送 |
| ADR与阶段硬门 | 通过 | 不改Agent目标、PLAN-02、盲测或生产签字 |
| 正确性与失败路径 | 通过 | 语法/路径/tree/摘要/full check通过；推送停滞及扫描误报修复 |
| 权限与数据 | 通过 | 不改事实库/ACL/冻结集；凭据检查通过 |
| 预算与取消 | 通过 | 0托管调用/0USD；仅停止本轮Git进程 |
| 追溯与版本 | 通过 | 批次SHA与机器清单绑定，远端工程HEAD已核对 |
| 验证充分性 | 通过 | required全量门通过；远端CI仍运行，部署待做 |
| 状态与文档 | 通过 | 最新提交与未完成边界同步，下一主项ARCH-15 |

## 限制与下一步

这是提交/推送工程自审，不是业务质量、长期部署或Agent阶段验收。历史记录185～188中的未提交状态描述保留为当时事实；最新状态以本记录和台账为准。下一项ARCH-15先完成实际入口反例，再补输出前身份/证据及提交间竞态防护，全程不调用托管模型。
