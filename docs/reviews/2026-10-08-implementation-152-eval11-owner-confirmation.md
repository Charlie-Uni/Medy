# 记录 152：EVAL-11 所有者确认与付费复核准备

日期：2026-10-08。状态：**所有者裁决已绑定；复核输入已准备；付费模型调用尚未授权、尚未执行。**

## 1. 人工裁决

项目所有者针对记录 151 的精确问题回复：“确认”。该答复只确认以下标注修订，不推定模型费用授权：

- `ms-0197/ms-0198`：2 个共同必需 gold；
- `ms-0440/ms-0441`：5 个共同必需 gold；
- `pc-0070/pc-0102`：2 个共同必需 gold。

确认记录绑定：

- revision manifest：`10c1b34d7b1cafa76483276a3668573ff4de2ad13c8c8b03cb8e082893f15916`；
- proposals：`eb00526d7e225af0aafb44fd73584c94641b52ab41eea5f515298b0ad0e5d986`；
- corpus edits：`37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`；
- human confirmation：`0b12b5fdef14172745ed2746b649d5ec1402e4d49413965d502e3b87e125e0b1`。

确认者角色仍为项目所有者/第一人工标注人，不计作第二独立人工。

## 2. 独立模型复核输入

`prepare_revision_review.py` 重新验证页坐标、gold 分组、孪生闭包、配额和人工确认后，生成 6 条 `multi-gold-review-v1` 输入。每次调用只放一条样本：

| scope/batch | 样本 | 调用数 | input SHA-256 |
| --- | --- | ---: | --- |
| main/CO | `ms-0440` | 1 | `675abc69…bd98` |
| main/EN | `ms-0198`、`ms-0441` | 2 | `5a7cb5ab…6f3e` |
| main/PV | `ms-0197` | 1 | `fcdbf8d7…e484` |
| probe/CO | `pc-0070` | 1 | `1ea035ef…a38` |
| probe/EN | `pc-0102` | 1 | `ea215352…bbc7` |

主集继续使用多证据提示 `7572d16e…b758`。旧探针提示写明“每条只有一条 gold”，不适用于本轮两个双 gold 样本；在任何调用前已生成多证据探针提示 `ba856262…35be`，要求逐组检查 key/span、联合充分性、冗余和孪生一致性。没有用矛盾提示发起调用。

## 3. 待授权的费用边界

建议授权范围：

- 模型：`claude-opus-5`；requested effort：high；
- 每条独立调用，最多 6 次；
- 单次 CLI 停止阈值：0.30 USD；
- 总账本上限：1.95 USD，其中 0.15 USD 用于 CLI 在阈值检查前可能产生的极小超额；
- 不自动重试；任一失败、无效 verdict、未知费用或超限立即停止；
- 原始 capture 权限 0600 且保持 Git 忽略。

机器可读请求为 `review/budget_request_2026-10-08.json`，其状态明确为 `pending_user_authorization`，不能作为 runner 的授权文件。

## 4. 当前限制与下一步

- `main-v4-provisional` 和 probe v3 未被改写；正式映射仍诚实保留 6 个 unmappable miss。
- 付费复核若全部得到可接受意见，才会按 PR-16 先冻结 probe v4，再组装并冻结 main v5，生成新的完整 gold 映射。
- 第二独立人工和未见盲测仍是独立缺口，本次项目所有者确认与 LLM 复核都不能替代。
