# TFDA 仿單图像层核查（ADR-0003 决策 1 条件 3）——候选清单 v1.7 签字批

日期：2026-09-29。对象：v1.7 签字 `eligible` 的 14 份 TFDA 仿單（cand-0361～0374）。方法与 2026-09-21 / 09-28 相同：pypdfium2 以约 65 dpi 渲染每一页，6 页拼成一张检视图，逐张目视（Claude Fable 5.1 查看图像），只判断版权 / 保密 / 禁止复用标记；疑点处以 200 dpi 单独渲染裁切核对。覆盖：14 份、28 页、14 张检视图全部看过。

## 结论

- **13 份通过**：只见廠商標誌、產品商標（®）、PIC/S GMP 标志、許可證字號与厂商地址；未见 ©、版權、著作權、保密或禁止复用声明。
- **1 份疑点，暂不激活**：cand-0371 美贊錠（中國化學製藥）第 1 页廠商地址栏末尾有一个单独的 Ⓒ 记号（200 dpi 裁切确认），无年份、无权利人、无声明文字；同厂 cand-0372 佩里波持續性藥效錠同一位置为 Ⓐ，判为印刷版次代号而非版权声明。按条件 3 从严处理：入库为 draft，不激活，列入激活计划 `held_back`，请决策人裁决（激活 / 撤回）。
- 产品身份：14 份的英文品名或成分名均在各自页文本中找到（cand-0366 页面印作 "Antoohin"，資料集英文品名 ANTOCHIN，中文品名安妥清膠囊与成分 indomethacin 一致，判为同一产品）。

| 候选 | 标题 | 页数 | 结论 |
| --- | --- | ---: | --- |
| cand-0361 | "永勝"歐適錠５公絲（羥布托尼）（OXIPAN TABLETS 5MG (OXYBUTYNIN CHLORIDE)"EVEREST"，oxy | 1 | 通过 |
| cand-0362 | "壽元"優尿錠５０公絲（本補麻隆）（UROTIN TABLETS 50MG  "S.Y." (BENZBROMARONE)，benzbrom | 2 | 通过 |
| cand-0363 | 彼洛喜錠（PROCID TABLETS，probenecid）仿單 | 1 | 通过 |
| cand-0364 | 抑痛寧靜脈注射液（Analif for IV Injection，ketorolac）仿單 | 1 | 通过 |
| cand-0365 | "明大"普士當錠５００毫克（邁菲那密酸）（MEFENAMIC ACID TABLETS 500MG "M.T"，mefenamic）仿單 | 1 | 通过 |
| cand-0366 | 安妥清膠囊（ANTOCHIN CAPSULES，indomethacin）仿單 | 2 | 通过 |
| cand-0367 | 風濕痛膠囊10毫克(匹洛西卡)（HONSUTON CAPSULES 10MG (PIROXICAM)，piroxicam）仿單 | 2 | 页 2 空白（印刷稿背面），通过 |
| cand-0368 | "南光" 舒解痛膜衣錠５００公絲（SUBUTON F.C. TABLETS 500MG "N.K."，nabumetone）仿單 | 2 | 商標識別行 Ⓡ S.B.T.（商标标识，不主张商标权），通过 |
| cand-0369 | 可洛拉平錠100毫克（可洛慮平）（MEZAPIN TABLETS 100MG(CLOZAPINE)，clozapine）仿單 | 2 | 通过 |
| cand-0370 | "瑞士"舒神膜衣錠２００毫克（斯比樂）（SUSINE F.C.TABLETS 200MG  "SWISS"(SULPIRIDE)，sulpi | 4 | 通过 |
| cand-0371 | 美贊錠 200 毫克（Misul Tablets 200 mg，amisulpride）仿單 | 1 | 疑点：Ⓒ 记号（见下） |
| cand-0372 | 佩里波持續性藥效錠3毫克（Pardone Extended-Release Tablets 3mg，paliperidone）仿單 | 6 | 通过 |
| cand-0373 | "泰和碩" 服緒妥糖衣錠（FUXITOL S.C. TABLETS 3MG "TAXO"，flupentixol）仿單 | 1 | 通过 |
| cand-0374 | 鹽酸氯普魯麻淨糖衣錠５０公絲（CHLORPROMAZINE HCL S.C. TABLETS 50MG "VPP"，chlorpromazi | 2 | 通过 |

## 说明

- cand-0363 彼洛喜錠的厂商「強生化學製藥廠股份有限公司 JOHNSON CHEMICAL PHARMACEUTICAL WORKS」是台湾公司，与 Johnson & Johnson 无关；页面无版权声明。
- 检视图与裁切图在会话临时目录，不入库；本文件是核查记录。
