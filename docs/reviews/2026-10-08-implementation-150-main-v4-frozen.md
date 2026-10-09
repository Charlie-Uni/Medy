# 记录 150：probe v3 导入与 main-v4-provisional 冻结

日期：2026-10-08。OPT-12/13，EVAL-09/10。状态：**probe v3 与 `main-v4-provisional` 已冻结；所有变化的主集复核输入均有当前意见，完整 gold 映射已生成。第二独立人工、未见盲测及新版本正式运行仍待完成。**

## 1. 数据版本结果

- probe v3：107 条，dataset hash `5707f29ddb750287015098dc8bee74246fc3f0b8b17b1f107aa0b5f75a28c97f`。
- main-v4-provisional：615 条，其中 554 条有答案、61 条无答案、107 条原样导入 probe v3、508 条本地主集样本；dataset hash `79e0c56920252a6e86694e1228c3c4f5ab47fbdfab2f89aa85dd9891ac618c7d`。
- 新版相对 main-v3-provisional 新增 `ms-0525`；15 条既有本地样本的标注字段发生已确认修订；485 条既有本地样本逐字节不变。
- probe v3 的 107 条样本以 canonical JSONL 字节原样并入主集，SHA-256 为 `e3a8c6bd7535bba1e45ff32ce6ba1160025c8d67fda7ba060f1b5e1c445d89de`。
- corpus 除根级 `dataset_version` 外只修改一项：`fda-investigator-safety-reporting-2025.title` 从错误的 September 2021 修正为封面与 version label 一致的 December 2025。

机器审计见[记录 150 JSON](2026-10-08-implementation-150-audit.json)。

## 2. 标题修正的复核传播闭包

复核输入包含文档标题，因此标题修正会改变同文档其他样本的输入哈希。确定性闭包检查发现 7 条未包含在原 19 条修订包中的受影响样本：

- PV：`ms-0235`、`ms-0237`、`ms-0239`；
- EN：`ms-0236`、`ms-0238`、`ms-0240`；
- NA：`ms-0475`。

项目所有者回复“授权”。执行前固定为 `claude-opus-5`、requested effort=high、每条一个独立调用、最多 7 次、无自动重试；单次 CLI 停止阈值 0.30 USD，总账本 2.25 USD。七条均返回 `agree`：

| 批次 | 调用 | 争议 | 账本费用 |
| --- | ---: | ---: | ---: |
| PV | 3 | 0 | 0.233869 USD |
| EN | 3 | 0 | 0.250862 USD |
| NA | 1 | 0 | 0.108342 USD |
| 合计 | **7** | **0** | **0.593073 USD** |

没有失败、重试、未知费用或单次阈值越界。原始 CLI capture 权限为 0600 且被 Git 忽略；run、verdict、输入、实际 prompt、模型、session 与账本逐项绑定。本轮仍是独立 LLM 复核，不能记作第二独立人工。

## 3. 历史提示与真实调用证据

main-v3 的未变化样本使用旧提示 `8538a516…d1e90`；本轮多证据与修订样本使用新提示 `7572d16e…b758`。若在 manifest 中把全部样本统一写成新提示，会伪造旧调用的来源。

本轮扩展 PR-09：

1. 当前 `review_prompt.md` 继续绑定 manifest 的当前提示哈希；
2. 旧提示按内容哈希归档到 `review_evidence/review_prompts/`；
3. 每个 invocation chunk 记录实际 review prompt 哈希；
4. 每条样本的 `second_reviewer.prompt_hash` 必须与其 latest invocation 一致；
5. 校验器用对应历史提示、历史或当前输入逐字重建实际 prompt；未使用、篡改或缺失的归档提示均报错。

新增回归测试覆盖提示升级后的历史意见保留和归档提示篡改。旧冻结版本保持兼容。

## 4. Gold 映射

新主集共有 574 个 gold 单元：568 mapped、6 unmappable。映射 SHA-256 为 `404ca270f850025d37df88f397fa5b1c86aa643a12d39bf29ef6391539ca5f41`。

完整数据库快照导出先失败关闭，错误为 `ValueError: expected exactly one stored document per frozen corpus entry`。定位到三份文档：

- `fda-meta-analyses-of-randomized-controlled-clinic-draft-2018`：PDF Launch 动作；
- `tfda-label-plusdmax-tablets-sinphar`：PDF JavaScript；
- `fda-providing-submissions-in-electronic-format-2015`：PDF embedded file。

它们是记录 98 中按 ADR-0009 有意拒收入库的候选，当前主集没有任何有答案或无答案样本引用它们。没有为了导出而绕过安全策略或补入事实库。

由于 main-v3→v4 的 source hash、version label、norm-v1 与 chunker-v2 坐标系不变，正式映射由以下冻结证据确定性合成：

1. main-v3 的已冻结完整映射；
2. v4 修订包中经原页和 chunk span 校验的 39 条映射预览；
3. 对每个新增或内容变化 gold 强制要求 preview 覆盖；
4. 对每个未变化 gold 复用 base entry；
5. 最终要求映射 gold ID 与 main-v4 samples 完全相等。

6 个 unmappable 单元继续作为失败留在召回分母，没有删除或改成 mapped。

## 5. 组装中发现并修复的问题

| 现场错误 | 原因 | 修复与复测 |
| --- | --- | --- |
| `ValueError: too many values to unpack (expected 2)` | successor assembler 把 `pack()` 返回的记录列表误当作键值对迭代 | 按 `record["sample_id"]` 建哈希映射；重跑进入下一检查 |
| `ValueError: NA: latest coverage mismatch` | 历史 run 合法保留已撤下的 `ms-0509`，初版组装器把 dropped review evidence 当成当前样本 | 覆盖比较按 manifest 的 `dropped_after_review` 过滤，历史调用仍保留；重跑通过 |
| 多条 `sample second_reviewer.prompt_hash differs from manifest` | 原 PR-09 假定一个主集只能有一个提示版本，无法如实表示后继版本保留旧意见 | 增加哈希归档提示和逐调用/逐样本绑定；测试 36 passed 后继续 |
| `ms-0084: actual prompt hash differs from current input` | 混合提示校验的样本循环错误复用了前一循环最后一个 `chunk_prompt_hash` | 在每条 latest binding 上重新取本 chunk 的提示哈希；冻结复测通过 |
| `make check` 首次因 2 文件格式不合格退出 | 新增分支排版未执行最终 formatter | `ruff format` 后重跑 |
| mypy：`Match[str] | None` 无法调用 `group` | 自定义 `_require` 不具备类型收窄语义 | 在已检查非空后增加显式 `assert`；mypy 复测通过 |

冻结工具仍保持事务性：冻结后校验失败会恢复 draft manifest 并删除临时 `SHA256SUMS`，没有留下伪冻结版本。

## 6. 验证与自审

- `tests/unit/evals`：528 passed。
- `make check`：1637 passed、70 skipped；ruff、430 个维护文件格式、186 个源文件 mypy、Schema 漂移和评测审计全部通过。
- `medops.evals.audit --with-pages`：4 套登记数据 PASS。
- main-v4 冻结校验：615 条、339 份 corpus 记录、页锚点、offset、review prompt、run/verdict/resolution 和文件哈希全部通过。
- 当前审计警告保持为真实缺口：6 个 unmappable gold 单元、历史 replay 使用旧 safety、第二人工 pending、无未见盲测；另有一条测试专用短 HMAC key 警告。

| 自审项 | 结论 | 依据与限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | 只应用用户确认的 v4 修订、导入 probe v3、补足标题传播复核；没有改门禁阈值 |
| 正确性与失败路径 | 通过 | 变化输入闭包为 23 条；所有当前 hash 有 latest verdict；失败冻结和不完整数据库导出均关闭失败 |
| 权限与追溯 | 通过 | 未摄取 ADR-0009 拒收文档；两版提示、调用、费用和唯一人工裁决均可重建 |
| 验证 | 通过 | 定向 528 项及全量 1637 项通过，带页评测审计通过 |
| 状态与文档 | 通过 | 新主集明确为 frozen + provisional；历史 main-v3 成绩没有迁移或重算 |

**EVAL-09 和 EVAL-10 本轮自审通过。阶段 1 整体仍未通过，剩余关键项为 6 个 unmappable gold 的处理、独立人工/盲测证据，以及新版本正式运行。所有工作区改动仍未提交。**
