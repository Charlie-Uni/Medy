# 实现记录 107：M5-04 首个成本候选的一次作废运行、原因与修正

日期：2026-10-01。决策人 2026-09-30 同意启动 M5-04 首个成本候选（证据 8 → 5，约 13 USD）。本记录如实报告：这次运行比较对象有误，花掉 3.86 USD 后终止；暴露的是一个会让已发布策略被静默撤销的流程缺口，已修正。

## 1. 发生了什么

- 23:10 以 `evals/replay/candidates/2026-09-26-context-rerank5.json`（diff 只有 `rerank_output: 8 → 5`，9 月 26 日编写）在 replay-v2 上启动两臂三轮。
- 01:08 第 1 轮中期读数：配对 200 题 baseline 成功 0.80、candidate 0.73（−7.0 pp）；每题 token 3,560 → 2,364（−33.6%）。成本门禁允许的总体下降上限是 1 pp，实现方按"三轮均值已不可能达标"终止运行以节省约 9 USD（共 692 行，3.86 USD）。
- 随后核对候选臂的实际配置，发现比较对象错了：候选臂是「无词表、无 multi_query、无 doc_focus、无查询翻译、证据 5 段」，而不是「released 四件套 + 证据 5 段」。证据：候选臂每题模型调用 1.96 次、基线 2.92 次，少的正是翻译调用；−7 pp 与四件套自身的收益（记录 104：+8.33 pp）同量级；候选臂两条 `injection_document` 安全项失败 `must_flag_evidence` 也是同一原因（注入文档不再进入证据）。

## 2. 根因

策略模型是「每个目标（kind, name）一条 released 策略，其 diff 作用在仓库常量上」。同一目标的新候选**替换**已发布的 diff，而不是叠加。检索四件套 2026-09-30 全量发布后，9 月 26 日写的这份候选等价于「撤掉四件套 + 裁剪证据」。校验没有拦住它：`validate_candidate` 只核对 `HybridConfig` 四个数值键的 `from`，不核对 `rerank_output` 与四个扩展键，也不检查候选是否遗漏了已发布的键。

两层责任：流程上缺这条校验；操作上实现方在启动付费运行前只看了 `--estimate` 与基线臂来源，没有打印候选臂的生效配置。后果若未被发现会更重：这份候选一旦通过并发布，生产上的四件套会被静默撤销。

## 3. 修正

1. `medops.application.policy_loader.check_restates_release(current, kind, name, diff)`：同一目标已有 released 策略时，候选必须重述其全部键（`from == to` 表示保持），且每个键的 `from` 必须等于现行值；否则 `PolicyDiffError`（「candidate would silently revert released keys …」）。
2. 接入两处：`medops.loop.adapt.validate_candidate / submit`（CLI 提交时以 `load_released` 的现行集合校验）与 `evals/replay/tools/replay_run.py::candidate_set`（付费运行构造候选臂之前）。实测：旧候选文件对现行 released 状态被拒绝，新候选文件通过。
3. 新候选文件 `evals/replay/candidates/2026-10-01-context-rerank5-on-bundle.json`：四件套四个键重述（from == to），只改 `rerank_output: 8 → 5`；旧文件保留作记录，运行器不再接受它。
4. 测试：`tests/unit/loop/test_adapt.py::test_a_candidate_must_restate_every_released_key_of_its_target`（遗漏键被拒、重述通过、`from` 过期被拒、无 released 策略或其他目标不受影响）。
5. 运行目录 `evals/harness/runs/2026-09-30-replay-eval-v4-context-rerank5/STOPPED.md` 写明该目录不是门禁报告、候选臂 329 行作废、baseline 第 1 轮 363 行是有效的 released 基线测量。

未做：发布路由（`POST /admin/policies/{id}/release`）本身不重复这条校验，依赖候选经 Adapt 提交；若将来允许绕过 Adapt 直接写候选，需要在发布处再加一道。运行器的 `--estimate` 不连库，不触发该校验，真实运行在构造候选臂时触发。

## 4. 这次运行里仍然有效的信息

- released 基线第 1 轮：200 题成功率 0.80，每题 3,560 token、2.92 次模型调用、0.0084 USD；安全 163/163。与记录 104 候选臂三轮（0.810 / 0.805 / 0.820）一致，说明全量发布后的状态可复现。
- 「证据 8 → 5」本身对质量的影响**没有测到**，需要用新候选文件重跑。

## 5. 需要决策人

是否用修正后的候选重跑（两臂三轮约 12.8 USD；余额约 33 USD）。零费用离线估计（用记录 R2 的证据排名）：released 检索下 gold 落在重排第 6–8 位的样本，主集 553 条里有 8 条（1.45%），回放子集 177 条带 gold 的题里有 4 条；baseline 第 1 轮成功的 160 题中 gold 在第 6–8 位的只有 1 题，即裁到 5 段的**直接**损失约 0.5 pp，低于成本门禁的 1 pp 上限。间接损失（模型依赖的旁证段落被裁掉）测不出来，只能靠重跑。token 降幅按证据占比估计 25–30%，在 25% 门槛附近。结论：修正后的候选有通过的可能，值得一测，但不是必然。

## 6. §9 自审

- 错误由实现方造成并在 3.86 USD 处止损；本记录、运行目录说明与给决策人的回复三处口径一致，未把作废数据写进验收报告。
- 修正落在规则层（候选不能静默撤销已发布键），有测试钉住；未改门禁阈值。
- 未提交任何候选；released 状态未变。
