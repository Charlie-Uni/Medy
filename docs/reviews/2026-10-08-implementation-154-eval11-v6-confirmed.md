# 记录 154：EVAL-11 v6 所有者确认与差量复核准备

日期：2026-10-08。状态：**所有者裁决已绑定；差量复核输入与费用边界已准备；尚未调用模型。**

## 1. 所有者裁决

项目所有者回复：“确认 EVAL-11 v6 建议”。该确认绑定以下决定：

1. `ms-0197/ms-0198` 保留 main-v4 原 gold，在 `chunker-v2` 下继续作为 `unmappable` miss 留在召回分母；
2. `ms-0440/ms-0441` 采用 5 个共同必需 gold；
3. `pc-0070/pc-0102` 采用完整 1.5.1 条款 evidence span 与单一记录列表 key。

精确绑定：

- revision manifest：`9eba65082184d9f9311287ed6af4309d616a08566e40ee83de936eb2609b5c3c`；
- proposals：`f2b77ed5f2c647c06da5b8fefcff86129cf41f85ab879d8197cc87e057da80ed`；
- human confirmation：`d23e9326d6c8989dbf8b6fb8ec8928b6f6d1df6067b026e50532db8856243171`；
- review preparation：`518f1c9928238699a848651e2aa1aa8b5439029cd8af03654b7030c6cd7c0863`。

该确认是项目所有者/第一人工标注裁决，不计作第二独立人工。

## 2. 两条 agree 的安全复用

`ms-0440` 和 `ms-0441` 在 v6 的完整 reviewer input 与 v5 已复核输入逐对象规范化哈希一致；复核提示、模型与 requested effort 也一致。原 run 的 latest binding、归档输入和 verdict 哈希相互吻合：

| 样本 | reviewer input SHA-256 | verdict SHA-256 | 结论 |
| --- | --- | --- | --- |
| `ms-0440` | `7ba40a99…d453` | `64a3d517…33f` | agree |
| `ms-0441` | `2cb7c17b…0f51` | `ccd00062…d29` | agree |

机器证据为 `review/reused_agree_verdicts.json`，SHA-256 为 `09a3bab23f89e340329f11327eb88ad6b618409fe928d2c64afa7e71d7b61c7f`。因此无需再次付费，也不把复用模型意见误记为第二人工。

## 3. 需要新复核的差量

`pc-0070/pc-0102` 从 v5 的物理双切分改为 v6 的单一完整列表 gold，reviewer input 哈希已经改变。准备结果为：

| scope/batch | 样本 | input SHA-256 | prompt SHA-256 |
| --- | --- | --- | --- |
| probe/CO | `pc-0070` | `95d45fdd…fccb` | `ba856262…35be` |
| probe/EN | `pc-0102` | `5724d255…6a61` | `ba856262…35be` |

建议费用边界：`claude-opus-5`、high effort、每条 1 次、最多 2 次、单次阈值 0.30 USD、总上限 0.65 USD、无自动重试；任一 CLI 失败、无效 verdict、未知费用或越界立即停止。机器请求 `review/budget_request_2026-10-08.json` 的 SHA-256 为 `2148c0fa6465fa73288f3d335bd79a16789e17d5641509d8ce1b7a8bb1b8c745`。

v5 授权尚余 1.370938 USD，但其授权文件绑定 v5 的 revision、confirmation、preparation、batch input 与 prompt 哈希。两条 `pc-*` 输入已改变，未用余额不能自动转移到 v6；需要针对当前精确范围重新明确授权。

## 4. 当前边界

- 本步骤模型调用为 0，新增费用为 0 USD；
- 冻结的 probe v3 与 `main-v4-provisional` 未被改写；
- v6 仍是草案，必须等两条新复核均可接受后才能组装 probe v4 和 main v5；
- 第二独立人工仍未完成。

## 5. 自审

- v6 页级 annotation revision 与人工确认绑定重新校验通过；
- 4 条复核输入覆盖与 preparation 哈希一致；
- 两条复用记录的当前输入、源 run binding、归档输入和 verdict 哈希逐项一致；
- 新费用请求只包含两个发生变化的 `pc-*` 输入，不包含已复用的 ICH E7 两题；
- 定向单元测试、评测审计和工作区 whitespace 检查通过后，本记录才作为当前状态依据。
