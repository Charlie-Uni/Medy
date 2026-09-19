# DEC-011 候选文档清单 v0.4（编制 2026-09-13；承接 v0.3，订正 cand-0034～0038 的抽取证据并排除 cand-0036）

> 政策：ADR-0003。每条候选自带完整许可证据（url/locator/quote 一一对应）。`reviewer_decision` 为决策人结论；只有 `eligible` 可进入 corpus.json。

## v0.4 变更

- 按 2026-09-13 审核意见，cand-0034～0038 的文本层扫描证据改为实际执行信息：2026-09-12 以 pypdf 6.15.0 初筛，2026-09-13 以锁定版 pypdf 6.18.1 复测，记录页数、字符数与 pypdf 告警数。
- cand-0036（欣服寧）复测四页均有字形映射错误，按 SPEC §4 本轮排除，不作为探针集 v1 gold 来源；许可预判不变。
- cand-0034～0038 `notes` 补充：许可证现行不等于该 PDF 为现行修订版，仿單版本以文内版本行为准。
- cand-0001～0033 与 v0.3 逐字相同。

## 汇总

| 部门 | eligible | research_only | needs_review | rejected | 合计 |
| --- | --- | --- | --- | --- | --- |
| MA | 8 | 0 | 10 | 0 | 18 |
| PV | 8 | 1 | 1 | 0 | 10 |
| CO | 3 | 0 | 4 | 3 | 10 |
| 合计 | 19 | 1 | 15 | 3 | 38 |

eligible 按语言：en 8；zh-Hans 2；zh-Hant 9

## 清单

| ID | 部门 | 类型 | 语言 | 标题 | 状态 | 决策 | PDF |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cand-0001 | MA | label | zh-Hant | 艾必克凝膜衣錠2.5毫克／5毫克（Eliquis Film-Coated Tablet, apixaban）仿單 | needs_review | needs_review | 有 |
| cand-0002 | MA | label | zh-Hant | 拜瑞妥膜衣錠10／15／20毫克（Xarelto Film-coated Tablets, rivaroxaban）仿單 | needs_review | needs_review | 有 |
| cand-0003 | MA | label | zh-Hant | 恩排糖膜衣錠25毫克（Jardiance 25 mg, empagliflozin）仿單 | needs_review | needs_review | 有 |
| cand-0004 | MA | label | zh-Hant | 保栓通膜衣錠75毫克（PLAVIX 75 mg, clopidogrel）仿單 | needs_review | needs_review | 有 |
| cand-0005 | MA | label | zh-Hant | 耐適恩錠20／40公絲（Nexium Tablets, esomeprazole）仿單 | needs_review | needs_review | 有 |
| cand-0006 | MA | label | zh-Hant | 脈優錠5毫克（Norvasc Tablets 5 mg, amlodipine besylate）仿單 | needs_review | needs_review | 有 |
| cand-0007 | MA | label | en | ELIQUIS (apixaban) tablets, film coated — US Prescribing Inf | needs_review | needs_review | 有 |
| cand-0008 | MA | label | en | SYNTHROID (levothyroxine sodium) tablets — US Prescribing In | needs_review | needs_review | 有 |
| cand-0009 | PV | guideline | en | Guideline on good pharmacovigilance practices (GVP) – Module | eligible | — | 有 |
| cand-0010 | PV | guideline | en | Guideline on good pharmacovigilance practices (GVP) – Module | eligible | — | 有 |
| cand-0011 | PV | guideline | en | Sponsor Responsibilities—Safety Reporting Requirements and S | eligible | — | 有 |
| cand-0012 | PV | guideline | en | ICH E2A: Clinical Safety Data Management: Definitions and St | eligible | — | 有 |
| cand-0013 | PV | guideline | en | ICH E2F: Development Safety Update Report | eligible | — | 有 |
| cand-0014 | PV | guideline | zh-Hant | 藥品不良反應通報表填寫指引（第四版） | eligible | — | 有 |
| cand-0015 | PV | guideline | zh-Hant | 醫護人員指引—呈報藥品不良反應（第3.1版） | research_only | — | 有 |
| cand-0016 | PV | guideline | zh-Hans | 上海市药物警戒管理办法（沪药监规〔2026〕3号） | needs_review | — | 有 |
| cand-0017 | CO | guideline | en | ICH Harmonised Guideline: Guideline for Good Clinical Practi | eligible | — | 有 |
| cand-0018 | CO | guideline | en | Protocol Deviations for Clinical Investigations of Drugs, Bi | eligible | — | 有 |
| cand-0019 | CO | sop | en | Protocol Deviations and Violations — VCU/VCU Health Clinical | needs_review | — | 有 |
| cand-0020 | CO | sop | en | CR010 Management of Protocol and GCP Deviations and Violatio | rejected | — | 有 |
| cand-0021 | CO | protocol | en | Phase I, Open-Label, Dose-Ranging Study of the Safety and Im | rejected | rejected | 有 |
| cand-0022 | CO | protocol | en | A Phase 2, Open-label, Single-arm Study of PVSRIPO and Pembr | rejected | — | 有 |
| cand-0023 | CO | protocol | en | A Phase 1b, Randomized, Double-Blind, Placebo-Controlled Tri | needs_review | — | 有 |
| cand-0024 | CO | guideline | zh-Hans | 药物临床试验质量管理规范（2026年修订）（国家药监局 国家卫生健康委 国家中医药局 国家疾控局公告 2026年第50号 | needs_review | — | 无 |
| cand-0025 | CO | guideline | zh-Hans | 关于印发《提升本市临床试验质量 助力创新药械研发上市的实施方案》的通知（沪药监药注〔2024〕216号） | needs_review | — | 有 |
| cand-0026 | PV | guideline | zh-Hans | MedDRA 术语选择：考虑要点（ICH 认可的 MedDRA 用户指南，发布版本 4.26） | eligible | eligible | 有 |
| cand-0027 | PV | guideline | zh-Hans | MedDRA 数据检索和展示：考虑要点（ICH 认可的 MedDRA 用户数据输出指南，发布版本 3.26） | eligible | eligible | 有 |
| cand-0028 | CO | guideline | en | ICH Harmonised Guideline E8(R1): General Considerations for  | eligible | eligible | 有 |
| cand-0029 | MA | label | zh-Hant | 美洛醣膜衣錠850毫克（Loformin Film-coated Tablets 850mg, metformin hy | eligible | eligible | 有 |
| cand-0030 | MA | label | zh-Hant | 安通脈膜衣錠10毫克/10毫克（Amlodipine Besylate and Atorvastatin Mylan 1 | eligible | eligible | 有 |
| cand-0031 | MA | label | zh-Hant | 吉福坦膜衣錠100毫克（Losartan Jubilant film-coated tablet 100mg, losa | eligible | eligible | 有 |
| cand-0032 | MA | label | zh-Hant | 艾摩喜林黴素膠囊（安莫西林）（AMOXICILLIN CAPSULES "TAI YU"）仿單 | needs_review | needs_review | 有 |
| cand-0033 | MA | label | zh-Hant | 血脂安膜衣錠20毫克（pms-Rosuvastatin 20mg tablets）仿單 | needs_review | needs_review | 有 |
| cand-0034 | MA | label | zh-Hant | 痛風停錠300毫克（Deurinol Tablets 300mg, allopurinol）仿單 | eligible | — | 有 |
| cand-0035 | MA | label | zh-Hant | 穩壓膜衣錠50毫克（Zosaa F.C. Tablets 50mg, losartan potassium）仿單 | eligible | — | 有 |
| cand-0036 | MA | label | zh-Hant | 欣服寧錠3毫克（Synfarin Tablets 3mg, warfarin sodium）仿單 | eligible | — | 有 |
| cand-0037 | MA | label | zh-Hant | "明德"心壓暢錠100毫克（美托普洛）（Cancliol Tablets 100mg, metoprolol tartr | eligible | — | 有 |
| cand-0038 | MA | label | zh-Hant | 胃所樂腸溶膜衣錠40毫克（Esomen Enteric-Coated Tablets 40mg, esomeprazol | eligible | — | 有 |

## 逐条证据

### cand-0001：艾必克凝膜衣錠2.5毫克／5毫克（Eliquis Film-Coated Tablet, apixaban）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；許可證持有者：輝瑞大藥廠股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E9%83%A8%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC026124%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_15fa16ad-2bd6-4d51-ab90-59e69d771834
- 版本：In-text 版本：USPI 202103-1；file uploaded 2022-01-20；licence 衛部藥輸字第026124號 / 026133號，active
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-09 主会话 WebFetch 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)）：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告（2026-09-09 主会话复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採政府資料開放授權條款-第1版發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用 … 使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務 … 使用時應註明出處 … 部分的影音、圖像、樂譜、專人專案撰文或其他著作，經機關特別聲明須經同意方可使用者。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明）：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-10 下载：zip sha256 4817da5299bdf4d66a38ba17e42986b25c7d0ee47787a961aabe1c1f9ad92abe，内层 39_5.json sha256 ce8276a050ee039a55609b55aad158b0d3c5266584fe691f22dc6f37f4e72c4d，29,855 行；字段 仿單圖檔連結，許可證字號 衛部藥輸字第026124號（机械核对：本条 pdf_url 未逐字出现））：https://mcp.fda.gov.tw/exportpdf/衛部藥輸字第026124號
- 第三方内容：Label text authored by the MAH (Pfizer); Traditional-Chinese translation of the US PI, uploaded by the company (自行上傳). Contains Pfizer/BMS trademarks and figures. Script variant zh-Hant.
- 理由：The exact PDF link is distributed by TFDA in an open dataset under OGDL-1.0 (CC BY 4.0-compatible, commercial reuse allowed), which would support eligible; but the hosting platform footer prohibits any reproduction without TFDA consent and the text is manufacturer-authored. Conflicting notices plus third-party authorship make this an owner decision.
- 复核备注：2026-09-10 决策：有条件接受数据集 9117 的 OGDL-1.0 为特定授权依据；进入 corpus 前须机械证明 (1) pdf_url 在同日数据集快照中逐字出现 (2) 记录快照哈希/日期/字段 (3) PDF 无附加限制声明 (4) 遵守 OGDL 署名、不主张商标权。核对结果：条件 (1) 不成立，快照中该許可證字號的仿單圖檔連結为 exportpdf/<許可證字號>，不是本条 pdf_url；条件 (3) 通过：PDF 全文无版权/保密/禁止复用声明（命中词均为临床文本）。保持 needs_review。后续可改选数据集中仿單圖檔連結为 /insert/pdfcasefile/ 形式的仿單（快照中 16,989 行）重新核对。
- 备注：页数：30；PDF 2026-09-10 重新下载 sha256 ab1af4e76a79099af824cf5c35fbadba4c61de0d93a6e05a885a4904000358cd，2206563 字节，30 页，可抽取 28606 字符；脚本变体 zh-Hant

### cand-0002：拜瑞妥膜衣錠10／15／20毫克（Xarelto Film-coated Tablets, rivaroxaban）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台；許可證持有者：台灣拜耳股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC025648%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_37960232-a732-45eb-9938-b85471f715e7
- 版本：File uploaded 2022-08-10；licence 衛署藥輸字第025648號 (15 mg)，active
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-09 主会话 WebFetch 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)）：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告（2026-09-09 主会话复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採政府資料開放授權條款-第1版發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用 … 使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務 … 使用時應註明出處 … 部分的影音、圖像、樂譜、專人專案撰文或其他著作，經機關特別聲明須經同意方可使用者。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明）：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-10 下载：zip sha256 4817da5299bdf4d66a38ba17e42986b25c7d0ee47787a961aabe1c1f9ad92abe，内层 39_5.json sha256 ce8276a050ee039a55609b55aad158b0d3c5266584fe691f22dc6f37f4e72c4d，29,855 行；字段 仿單圖檔連結，許可證字號 衛署藥輸字第025648號（机械核对：本条 pdf_url 未逐字出现））：https://mcp.fda.gov.tw/exportpdf/衛署藥輸字第025648號
- 第三方内容：Bayer-authored; 2-page 65x29.7 cm broadsheet with clean text layer (用法用量 x13, 禁忌 x4, 交互作用 x15). The 2.5 mg licence (027750) PDF has no usable text layer and was excluded. Script variant zh-Hant.
- 理由：该 PDF 链接由 TFDA 在 OGDL-1.0（与 CC BY 4.0 相容，允许商业复用）数据集中发布，可支持 eligible；但托管平台页脚禁止未经同意的任何重製，且正文为厂商撰写，两项声明冲突加第三方作者身份，需要决策人判断而非机械判定 eligible。Bayer 撰写；2 页大幅面单张但文字层完整（用法用量、禁忌、交互作用条款丰富）。
- 复核备注：2026-09-10 决策：有条件接受数据集 9117 的 OGDL-1.0 为特定授权依据；进入 corpus 前须机械证明 (1) pdf_url 在同日数据集快照中逐字出现 (2) 记录快照哈希/日期/字段 (3) PDF 无附加限制声明 (4) 遵守 OGDL 署名、不主张商标权。核对结果：条件 (1) 不成立，快照中该許可證字號的仿單圖檔連結为 exportpdf/<許可證字號>，不是本条 pdf_url；条件 (3) 通过：PDF 全文无版权/保密/禁止复用声明（命中词均为临床文本）。保持 needs_review。后续可改选数据集中仿單圖檔連結为 /insert/pdfcasefile/ 形式的仿單（快照中 16,989 行）重新核对。
- 备注：页数：2；PDF 2026-09-10 重新下载 sha256 7cc8505bb5e8521d26892e34b1a0ac61f50e1dad18f819ed71a594ab1f75f384，1068228 字节，2 页，可抽取 38341 字符；脚本变体 zh-Hant

### cand-0003：恩排糖膜衣錠25毫克（Jardiance 25 mg, empagliflozin）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台；許可證持有者：台灣百靈佳殷格翰股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E9%83%A8%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC026405%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_9ab68bbd-bf40-4b59-a784-4f5153751449
- 版本：CCDS 0278-15 (2022-04-18) uploaded 2022-04-25；in-text 2021年09月 / 2022年04月；licence 衛部藥輸字第026405號，active
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-09 主会话 WebFetch 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)）：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告（2026-09-09 主会话复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採政府資料開放授權條款-第1版發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用 … 使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務 … 使用時應註明出處 … 部分的影音、圖像、樂譜、專人專案撰文或其他著作，經機關特別聲明須經同意方可使用者。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明）：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-10 下载：zip sha256 4817da5299bdf4d66a38ba17e42986b25c7d0ee47787a961aabe1c1f9ad92abe，内层 39_5.json sha256 ce8276a050ee039a55609b55aad158b0d3c5266584fe691f22dc6f37f4e72c4d，29,855 行；字段 仿單圖檔連結，許可證字號 衛部藥輸字第026405號（机械核对：本条 pdf_url 未逐字出现））：https://mcp.fda.gov.tw/exportpdf/衛部藥輸字第026405號
- 第三方内容：BI-authored CCDS-derived text; trademarks. Rich structured 用法用量/禁忌/交互作用 (x8) sections. Script variant zh-Hant.
- 理由：该 PDF 链接由 TFDA 在 OGDL-1.0（与 CC BY 4.0 相容，允许商业复用）数据集中发布，可支持 eligible；但托管平台页脚禁止未经同意的任何重製，且正文为厂商撰写，两项声明冲突加第三方作者身份，需要决策人判断而非机械判定 eligible。Boehringer Ingelheim 撰写的 CCDS 派生文本，编号章节结构清晰。
- 复核备注：2026-09-10 决策：有条件接受数据集 9117 的 OGDL-1.0 为特定授权依据；进入 corpus 前须机械证明 (1) pdf_url 在同日数据集快照中逐字出现 (2) 记录快照哈希/日期/字段 (3) PDF 无附加限制声明 (4) 遵守 OGDL 署名、不主张商标权。核对结果：条件 (1) 不成立，快照中该許可證字號的仿單圖檔連結为 exportpdf/<許可證字號>，不是本条 pdf_url；条件 (3) 通过：PDF 全文无版权/保密/禁止复用声明（命中词均为临床文本）。保持 needs_review。后续可改选数据集中仿單圖檔連結为 /insert/pdfcasefile/ 形式的仿單（快照中 16,989 行）重新核对。
- 备注：页数：26；PDF 2026-09-10 重新下载 sha256 21284cb5c0ded7fe0627e378522a9a5ac1724e6169aee72b3082e8c3aca120f9，1065925 字节，26 页，可抽取 37889 字符；脚本变体 zh-Hant

### cand-0004：保栓通膜衣錠75毫克（PLAVIX 75 mg, clopidogrel）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台；許可證持有者：賽諾菲股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC022932%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_da3dc509-0c5c-46f5-8d85-d3a328313acb
- 版本：In-text CCDS v29 (03 June 2021)；file uploaded 2022-04-26；licence 衛署藥輸字第022932號，active
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-09 主会话 WebFetch 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)）：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告（2026-09-09 主会话复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採政府資料開放授權條款-第1版發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用 … 使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務 … 使用時應註明出處 … 部分的影音、圖像、樂譜、專人專案撰文或其他著作，經機關特別聲明須經同意方可使用者。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明）：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-10 下载：zip sha256 4817da5299bdf4d66a38ba17e42986b25c7d0ee47787a961aabe1c1f9ad92abe，内层 39_5.json sha256 ce8276a050ee039a55609b55aad158b0d3c5266584fe691f22dc6f37f4e72c4d，29,855 行；字段 仿單圖檔連結，許可證字號 衛署藥輸字第022932號（机械核对：本条 pdf_url 未逐字出现））：https://mcp.fda.gov.tw/exportpdf/衛署藥輸字第022932號
- 第三方内容：Sanofi-authored; CYP2C19/PPI interaction content (交互作用 x17, 禁忌 x2, 警語 x11). Filename says CCDS v28 but text says v29; record the in-text version. Script variant zh-Hant.
- 理由：该 PDF 链接由 TFDA 在 OGDL-1.0（与 CC BY 4.0 相容，允许商业复用）数据集中发布，可支持 eligible；但托管平台页脚禁止未经同意的任何重製，且正文为厂商撰写，两项声明冲突加第三方作者身份，需要决策人判断而非机械判定 eligible。Sanofi 撰写；含 CYP2C19/PPI 相互作用条款。
- 复核备注：2026-09-10 决策：有条件接受数据集 9117 的 OGDL-1.0 为特定授权依据；进入 corpus 前须机械证明 (1) pdf_url 在同日数据集快照中逐字出现 (2) 记录快照哈希/日期/字段 (3) PDF 无附加限制声明 (4) 遵守 OGDL 署名、不主张商标权。核对结果：条件 (1) 不成立，快照中该許可證字號的仿單圖檔連結为 exportpdf/<許可證字號>，不是本条 pdf_url；条件 (3) 通过：PDF 全文无版权/保密/禁止复用声明（命中词均为临床文本）。保持 needs_review。后续可改选数据集中仿單圖檔連結为 /insert/pdfcasefile/ 形式的仿單（快照中 16,989 行）重新核对。
- 备注：页数：13；PDF 2026-09-10 重新下载 sha256 d41ffbb61eacd19c494b45a1d0367072b86761f4a5db2f8a4c470e8c38ffd40c，1066660 字节，13 页，可抽取 30785 字符；脚本变体 zh-Hant

### cand-0005：耐適恩錠20／40公絲（Nexium Tablets, esomeprazole）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台；許可證持有者：臺灣阿斯特捷利康股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC023221%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_d5340189-8ea1-422d-b30f-aa155d84d8c1
- 版本：File uploaded 2021-08-13；licence 衛署藥輸字第023221號 (40 mg) / 023225號 (20 mg)，active
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-09 主会话 WebFetch 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)）：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告（2026-09-09 主会话复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採政府資料開放授權條款-第1版發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用 … 使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務 … 使用時應註明出處 … 部分的影音、圖像、樂譜、專人專案撰文或其他著作，經機關特別聲明須經同意方可使用者。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明）：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-10 下载：zip sha256 4817da5299bdf4d66a38ba17e42986b25c7d0ee47787a961aabe1c1f9ad92abe，内层 39_5.json sha256 ce8276a050ee039a55609b55aad158b0d3c5266584fe691f22dc6f37f4e72c4d，29,855 行；字段 仿單圖檔連結，許可證字號 衛署藥輸字第023221號（机械核对：本条 pdf_url 未逐字出现））：https://mcp.fda.gov.tw/exportpdf/衛署藥輸字第023221號
- 第三方内容：AstraZeneca-authored; 交互作用 x14, 禁忌 x4. Script variant zh-Hant.
- 理由：该 PDF 链接由 TFDA 在 OGDL-1.0（与 CC BY 4.0 相容，允许商业复用）数据集中发布，可支持 eligible；但托管平台页脚禁止未经同意的任何重製，且正文为厂商撰写，两项声明冲突加第三方作者身份，需要决策人判断而非机械判定 eligible。AstraZeneca 撰写；相互作用与禁忌条款丰富。
- 复核备注：2026-09-10 决策：有条件接受数据集 9117 的 OGDL-1.0 为特定授权依据；进入 corpus 前须机械证明 (1) pdf_url 在同日数据集快照中逐字出现 (2) 记录快照哈希/日期/字段 (3) PDF 无附加限制声明 (4) 遵守 OGDL 署名、不主张商标权。核对结果：条件 (1) 不成立，快照中该許可證字號的仿單圖檔連結为 exportpdf/<許可證字號>，不是本条 pdf_url；条件 (3) 不成立：PDF 含“© AstraZeneca 2009 - 2013”“本註冊商標屬 AstraZeneca 集團之財產”。保持 needs_review。后续可改选数据集中仿單圖檔連結为 /insert/pdfcasefile/ 形式的仿單（快照中 16,989 行）重新核对。
- 备注：页数：3；PDF 2026-09-10 重新下载 sha256 50871b62d7dd2e37d06c6137f832082d9ae77fcdf943eb4e4755e3c6d287a8bc，747654 字节，3 页，可抽取 13643 字符；脚本变体 zh-Hant

### cand-0006：脈優錠5毫克（Norvasc Tablets 5 mg, amlodipine besylate）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台；許可證持有者：暉致醫藥股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC021571%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/27e94a5b-1414-4115-981b-d0df547d712f
- 版本：File uploaded 2024-09-25（廠商自行上傳）；in-text 版本: Australia 20170714-6；licence active
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-09 主会话 WebFetch 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)）：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告（2026-09-09 主会话复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採政府資料開放授權條款-第1版發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用 … 使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務 … 使用時應註明出處 … 部分的影音、圖像、樂譜、專人專案撰文或其他著作，經機關特別聲明須經同意方可使用者。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明）：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-10 下载：zip sha256 4817da5299bdf4d66a38ba17e42986b25c7d0ee47787a961aabe1c1f9ad92abe，内层 39_5.json sha256 ce8276a050ee039a55609b55aad158b0d3c5266584fe691f22dc6f37f4e72c4d，29,855 行；字段 仿單圖檔連結，許可證字號 衛署藥輸字第021571號（机械核对：本条 pdf_url 未逐字出现））：https://mcp.fda.gov.tw/exportpdf/衛署藥輸字第021571號
- 第三方内容：Viatris/Pfizer-authored (Australian PI-derived); lighter interaction section (交互作用 x2). Script variant zh-Hant.
- 理由：该 PDF 链接由 TFDA 在 OGDL-1.0（与 CC BY 4.0 相容，允许商业复用）数据集中发布，可支持 eligible；但托管平台页脚禁止未经同意的任何重製，且正文为厂商撰写，两项声明冲突加第三方作者身份，需要决策人判断而非机械判定 eligible。Viatris/Pfizer 撰写（澳洲 PI 派生）；相互作用条款较少，作为常见心血管通用名补充。
- 复核备注：2026-09-10 决策：有条件接受数据集 9117 的 OGDL-1.0 为特定授权依据；进入 corpus 前须机械证明 (1) pdf_url 在同日数据集快照中逐字出现 (2) 记录快照哈希/日期/字段 (3) PDF 无附加限制声明 (4) 遵守 OGDL 署名、不主张商标权。核对结果：条件 (1) 不成立，快照中该許可證字號的仿單圖檔連結为 exportpdf/<許可證字號>，不是本条 pdf_url；条件 (3) 通过：PDF 全文无版权/保密/禁止复用声明（命中词均为临床文本）。保持 needs_review。后续可改选数据集中仿單圖檔連結为 /insert/pdfcasefile/ 形式的仿單（快照中 16,989 行）重新核对。
- 备注：页数：12；PDF 2026-09-10 重新下载 sha256 ea9d4e4dd7d06e52559fa69b7c15472016752b1c6895f25c8091f4724e4e51c7，378149 字节，12 页，可抽取 11535 字符；脚本变体 zh-Hant

### cand-0007：ELIQUIS (apixaban) tablets, film coated — US Prescribing Information

- 发布方：US NLM DailyMed（labeler: E.R. Squibb & Sons, L.L.C.）
- 落地页：https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e9481622-7cc6-418a-acb6-c5450daae9b0
- PDF：https://dailymed.nlm.nih.gov/dailymed/downloadpdffile.cfm?setId=e9481622-7cc6-418a-acb6-c5450daae9b0
- 版本：SPL version 30, published 2025-05-05；label Revised: 4/2025
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://www.nlm.nih.gov/web_policies.html（Copyright Information）：Works produced by the U.S. government are not subject to copyright protection in the United States. Any such works found on National Library of Medicine (NLM) Web sites may be freely used or reproduced without permission in the U.S. || When using NLM Web sites, you may encounter documents, illustrations, photographs, or other content contributed by or licensed from private individuals, companies, or organizations that may be protected by U.S. and international copyright laws. || It is your responsibility to determine and satisfy copyright or other use restrictions when using materials that are not in the public domain. NLM cannot guarantee the copyright status for any item.
  - https://open.fda.gov/license/（License 页（2026-09-09 主会话复核一致；含 GMDN 第三方内容例外））：unless otherwise noted, the content, data, documentation, code, and related materials on openFDA is public domain and made available with a Creative Commons CC0 1.0 Universal dedication.
  - https://dailymed.nlm.nih.gov/dailymed/about-dailymed.cfm（About DailyMed）：The labeling on DailyMed is the most recent submitted labeling to the FDA by companies and currently in use
- 第三方内容：Labeling text is company-submitted (BMS/Pfizer); contains trademarks and figures. NLM explicitly does not guarantee copyright status of contributed content.
- 理由：Federal site plus FDA's own CC0 dedication for the identical SPL labeling data is an explicit open licence → proposed eligible. If the owner requires the licence to attach to the exact URL fetched rather than the openFDA copy, downgrade to needs_review or ingest via openFDA instead.
- 复核备注：2026-09-10 决策：由 eligible 降为 needs_review。openFDA 的 CC0 只覆盖其自身分发的 SPL 数据，DailyMed PDF 是另一分发对象与呈现形式，NLM 明确不保证第三方内容版权状态，许可不跨渠道传递。若使用 openFDA，应建立新的 openFDA 来源候选，不再把 DailyMed PDF 标为 CC0。
- 备注：页数：66

### cand-0008：SYNTHROID (levothyroxine sodium) tablets — US Prescribing Information

- 发布方：US NLM DailyMed（labeler: AbbVie Inc.）
- 落地页：https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1e11ad30-1041-4520-10b0-8f9d30d30fcc
- PDF：https://dailymed.nlm.nih.gov/dailymed/downloadpdffile.cfm?setId=1e11ad30-1041-4520-10b0-8f9d30d30fcc
- 版本：SPL version 1537, published 2024-02-29；label Revised: 2/2024
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://www.nlm.nih.gov/web_policies.html（Copyright Information）：Works produced by the U.S. government are not subject to copyright protection in the United States. Any such works found on National Library of Medicine (NLM) Web sites may be freely used or reproduced without permission in the U.S. || When using NLM Web sites, you may encounter documents, illustrations, photographs, or other content contributed by or licensed from private individuals, companies, or organizations that may be protected by U.S. and international copyright laws. || It is your responsibility to determine and satisfy copyright or other use restrictions when using materials that are not in the public domain. NLM cannot guarantee the copyright status for any item.
  - https://open.fda.gov/license/（License 页（2026-09-09 主会话复核一致；含 GMDN 第三方内容例外））：unless otherwise noted, the content, data, documentation, code, and related materials on openFDA is public domain and made available with a Creative Commons CC0 1.0 Universal dedication.
  - https://dailymed.nlm.nih.gov/dailymed/about-dailymed.cfm（About DailyMed）：The labeling on DailyMed is the most recent submitted labeling to the FDA by companies and currently in use
- 第三方内容：AbbVie-authored; chosen for time-window clauses (30–60 min before breakfast, 4-hour separation from calcium/iron/antacids) and negation-heavy contraindications.
- 理由：联邦站点加 FDA 自身对同一 SPL 数据的 CC0 声明构成明确开放许可，代理预判 eligible；AbbVie 撰写，选取原因是含时间窗条款（早餐前 30 到 60 分钟、与钙铁抗酸剂间隔 4 小时）与否定式禁忌。若要求许可附着于抓取的确切 URL 而非 openFDA 副本，应降为 needs_review。
- 复核备注：2026-09-10 决策：由 eligible 降为 needs_review。openFDA 的 CC0 只覆盖其自身分发的 SPL 数据，DailyMed PDF 是另一分发对象与呈现形式，NLM 明确不保证第三方内容版权状态，许可不跨渠道传递。若使用 openFDA，应建立新的 openFDA 来源候选，不再把 DailyMed PDF 标为 CC0。
- 备注：页数：45

### cand-0009：Guideline on good pharmacovigilance practices (GVP) – Module VI – Collection, management and submission of reports of suspected adverse reactions to medicinal products (Rev 2)

- 发布方：European Medicines Agency (EMA) and Heads of Medicines Agencies (HMA)
- 落地页：https://www.ema.europa.eu/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/good-pharmacovigilance-practices-gvp
- PDF：https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/guideline-good-pharmacovigilance-practices-gvp-module-vi-collection-management-submission-reports-suspected-adverse-reactions-medicinal-products-rev-2_en.pdf
- 版本：Rev 2, EMA/873138/2011 Rev 2, 28 July 2017
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://www.ema.europa.eu/en/about-us/about-website/legal-notice（Legal notice（2026-09-09 主会话复核一致））：Information and documents made available on EMA's webpages are public and may be reproduced and / or distributed, totally or in part, irrespective of the means and / or the formats used, for non-commercial and commercial purposes, provided that EMA is always acknowledged as the source of the material. […] The above-mentioned permissions do not apply to content supplied by third parties.
  - https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/guideline-good-pharmacovigilance-practices-gvp-module-vi-collection-management-submission-reports-suspected-adverse-reactions-medicinal-products-rev-2_en.pdf（PDF 封面版权声明）：© European Medicines Agency and Heads of Medicines Agencies, 2017. Reproduction is authorised provided the source is acknowledged.
- 第三方内容：Low. 84 mentions of MedDRA, references to WHO-UMC causality system, CIOMS/WHO reports and ICH E2B as citations only. Copyright jointly EMA/HMA; legal notice excludes third-party-supplied content.
- 理由：Explicit site-wide permission for commercial and non-commercial reproduction with attribution, restated on the document cover. Core ICSR collection, validity, 15-day/90-day submission time limits.
- 复核备注：无
- 备注：PV 归属理由：用于 PV 部门个例安全报告收集、有效性判断与 15 日/90 日提交时限条款检索；页数：144

### cand-0010：Guideline on good pharmacovigilance practices (GVP) – Module IX – Signal management (Rev 1)

- 发布方：European Medicines Agency (EMA) and Heads of Medicines Agencies (HMA)
- 落地页：https://www.ema.europa.eu/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/good-pharmacovigilance-practices-gvp
- PDF：https://www.ema.europa.eu/en/documents/scientific-guideline/guideline-good-pharmacovigilance-practices-gvp-module-ix-signal-management-rev-1_en.pdf
- 版本：Rev 1, EMA/827661/2011 Rev 1, 9 October 2017
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://www.ema.europa.eu/en/about-us/about-website/legal-notice（Legal notice（2026-09-09 主会话复核一致））：Information and documents made available on EMA's webpages are public and may be reproduced and / or distributed, totally or in part, irrespective of the means and / or the formats used, for non-commercial and commercial purposes, provided that EMA is always acknowledged as the source of the material. […] The above-mentioned permissions do not apply to content supplied by third parties.
  - https://www.ema.europa.eu/en/documents/scientific-guideline/guideline-good-pharmacovigilance-practices-gvp-module-ix-signal-management-rev-1_en.pdf（PDF 封面版权声明）：© European Medicines Agency and Heads of Medicines Agencies, 2017. Reproduction is authorised provided the source is acknowledged.
- 第三方内容：Low. Cites CIOMS Working Group VIII and SCOPE guide as further reading; one MedDRA mention. No reproduced third-party material found.
- 理由：Same explicit EMA reuse permission as Module VI; entirely about signal detection, validation, prioritisation and assessment.
- 复核备注：无
- 备注：PV 归属理由：用于 PV 部门信号检测、验证、优先级与评估条款检索；页数：25

### cand-0011：Sponsor Responsibilities—Safety Reporting Requirements and Safety Assessment for IND and Bioavailability/Bioequivalence Studies: Guidance for Industry

- 发布方：U.S. Food and Drug Administration (CDER/CBER)
- 落地页：https://www.fda.gov/regulatory-information/search-fda-guidance-documents/sponsor-responsibilities-safety-reporting-requirements-and-safety-assessment-ind-and
- PDF：https://www.fda.gov/media/150356/download
- 版本：Final (Level 1), December 2025, docket FDA-2020-D-2099; replaces December 2012 final guidance
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://www.fda.gov/about-fda/about-website/website-policies（Website Policies: Copyright（2026-09-09 主会话复核一致））：Unless otherwise noted, the contents of the FDA website (www.fda.gov) — both text and graphics — are not copyrighted. They are in the public domain and may be republished, reprinted and otherwise used freely by anyone without the need to obtain permission from FDA. […] Credit to the U.S. Food and Drug Administration as the source is appreciated but not required.
- 第三方内容：Low. Three MedDRA mentions and ICH references as citations only; no reproduced-with-permission or copyright markers.
- 理由：US government work in the public domain. Current guidance on 7-day/15-day IND safety reports, unexpected/serious definitions and aggregate safety assessment.
- 复核备注：无
- 备注：PV 归属理由：用于 PV 部门 IND 期间 7 日/15 日安全报告与严重性/非预期定义条款检索；页数：43

### cand-0012：ICH E2A: Clinical Safety Data Management: Definitions and Standards for Expedited Reporting

- 发布方：International Council for Harmonisation (ICH)
- 落地页：https://www.ich.org/page/efficacy-guidelines
- PDF：https://database.ich.org/sites/default/files/E2A_Guideline.pdf
- 版本：Step 4, 27 October 1994 (current)
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://www.ich.org/page/legal-mentions（Legal Mentions（页面客户端渲染；文本经站点 JSON 接口 admin.ich.org/api/v1/nodes?alias=/page/legal-mentions 取得，2026-09-09 主会话复核一致））：The information, material and photographic content provided on this website are protected by copyright and may, with the exception of the ICH logo, be used, reproduced, incorporated into other works, adapted, modified, translated or distributed under a public license provided that ICH's copyright in the information and material is acknowledged at all times. […] The above-mentioned permissions do not apply to content supplied by third parties. Therefore, for documents where the copyright vests in a third party, permission for reproduction must be obtained from this copyright holder.
- 第三方内容：Low. Mentions CIOMS-1/CIOMS-2 and WHO Uppsala centre as precedents; no reproduced material. The 1994 PDF carries no in-document legal notice, so reliance is on site-wide Legal Mentions. ich.org is client-side rendered; Legal Mentions text captured from the site's public JSON endpoint (admin.ich.org/api/v1/nodes?alias=/page/legal-mentions).
- 理由：Site-wide public licence expressly allowing use, reproduction and incorporation into other works with acknowledgement. Foundational SAE/expedited-reporting definitions and 7/15-day time limits.
- 复核备注：无
- 备注：PV 归属理由：用于 PV 部门 SAE 定义与加速报告 7 日/15 日时限条款检索；页数：12；1994 版 PDF 无文内法律声明，依据站点级 Legal Mentions

### cand-0013：ICH E2F: Development Safety Update Report

- 发布方：International Council for Harmonisation (ICH)
- 落地页：https://www.ich.org/page/efficacy-guidelines
- PDF：https://database.ich.org/sites/default/files/E2F_Guideline.pdf
- 版本：Step 4, 17 August 2010 (current)
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://www.ich.org/page/legal-mentions（Legal Mentions（页面客户端渲染；文本经站点 JSON 接口 admin.ich.org/api/v1/nodes?alias=/page/legal-mentions 取得，2026-09-09 主会话复核一致））：The information, material and photographic content provided on this website are protected by copyright and may, with the exception of the ICH logo, be used, reproduced, incorporated into other works, adapted, modified, translated or distributed under a public license provided that ICH's copyright in the information and material is acknowledged at all times. […] The above-mentioned permissions do not apply to content supplied by third parties. Therefore, for documents where the copyright vests in a third party, permission for reproduction must be obtained from this copyright holder.
- 第三方内容：Low-moderate. 13 references to CIOMS Working Group VII DSUR report (guideline derived from it) and one MedDRA mention; citations only. No in-document legal notice.
- 理由：Same ICH site-wide licence. Periodic safety reporting during development (DSUR). Same landing-page caveat as E2A.
- 复核备注：无
- 备注：PV 归属理由：用于 PV 部门研发期间定期安全报告（DSUR）条款检索；页数：35；PDF 无文内法律声明，依据站点级 Legal Mentions

### cand-0014：藥品不良反應通報表填寫指引（第四版）

- 发布方：衛生福利部食品藥物管理署 (Taiwan Food and Drug Administration)
- 落地页：https://www.fda.gov.tw/TC/siteContent.aspx?sid=4240
- PDF：https://www.fda.gov.tw/tc/includes/GetFile.ashx?mid=133&id=10137&t=s
- 版本：第四版, 2025年3月
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告（2026-09-09 主会话复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採政府資料開放授權條款-第1版發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用 … 使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務 … 使用時應註明出處 … 部分的影音、圖像、樂譜、專人專案撰文或其他著作，經機關特別聲明須經同意方可使用者。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明）：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
- 第三方内容：Low. Seven ICH mentions as citations; no MedDRA/WHO-UMC content reproduced. Open-data declaration excludes items specifically flagged as requiring consent; this PDF carries no such flag. Secondary evidence: https://www.fda.gov.tw/TC/copyright.aspx. Script variant zh-Hant.
- 理由：Explicit Open Government Data Licence v1 covering site material within copyright scope, permitting reproduction, adaptation and public transmission with attribution. Entirely about post-marketing ADR report completion (fields, seriousness, timelines, causality).
- 复核备注：无
- 备注：PV 归属理由：用于 PV 部门不良反应通报字段、严重性与时限条款检索；脚本变体 zh-Hant；页数：19

### cand-0015：醫護人員指引—呈報藥品不良反應（第3.1版）

- 发布方：衞生署藥物辦公室 (Drug Office, Department of Health, Hong Kong SAR)
- 落地页：https://www.drugoffice.gov.hk/eps/do/tc/healthcare_providers/adr_reporting/index.html
- PDF：https://www.drugoffice.gov.hk/eps/do/tc/doc/Guidance_for_HCP_tc.pdf
- 版本：Version 3.1, 2024年1月
- 预判状态：**research_only**；决策：待定
- 许可证据：
  - https://www.drugoffice.gov.hk/eps/do/en/healthcare_providers/important_notices.html（Important Notices: Copyright）：Materials found on this site are subject to copyright owned by the Government of the Hong Kong Special Administrative Region. […] The Department of Health ('DH'), as the source of materials, is acknowledged […] In respect of any other materials available within this website, the re-dissemination and reproduction of such other materials shall only be made for non-commercial purpose […] Where third party copyrights are involved, an appropriate notice will appear in this website.
- 第三方内容：Low. No MedDRA/CIOMS/WHO-UMC markers; appendices are DH's own ADR form, ATMP definitions and a label sample. Script variant zh-Hant.
- 理由：Re-dissemination and reproduction expressly permitted but restricted to non-commercial purposes with DH acknowledged → research_only. Content wholly about what/when/how to report ADRs.
- 复核备注：无
- 备注：PV 归属理由：用于 PV 部门不良反应呈报范围、严重与非预期定义条款检索；脚本变体 zh-Hant；许可仅非商业；页数：21

### cand-0016：上海市药物警戒管理办法（沪药监规〔2026〕3号）

- 发布方：上海市药品监督管理局、上海市卫生健康委员会
- 落地页：https://yjj.sh.gov.cn/zx-yp/20260724/33d15d742c8f424c8e6a1eb24d2d571c.html
- PDF：https://yjj.sh.gov.cn/cmsres/c5/c50e476a82ec4ae487fba20c70fcea34/6c3b123fc451aa1e14f495344e0db4c0.pdf
- 版本：发布 2026-07-24；施行 2026-08-01 至 2031-07-31（替代 2024 年试行版 沪药监规〔2024〕4号）
- 预判状态：**needs_review**；决策：待定
- 许可证据：
  - https://yjj.sh.gov.cn/assets/js/bottom2019.js（站点页脚脚本注入文本）：沪ICP备10019319号-5  上海市药品监督管理局 版权所有
- 第三方内容：None detected. PDF is text-based (about 8,200 extractable characters), not a scan.
- 理由：Provincial MPA 规范性文件 (labelled guideline per doc_type rule); only rights statement is a bare 版权所有 footer; no 网站声明 page exists → needs_review. Covers holder PV duties, ADR reporting, monitoring, signal and risk control.
- 复核备注：无
- 备注：PV 归属理由：用于 PV 部门持有人药物警戒义务、不良反应报告与信号风险控制条款检索；页数：20

### cand-0017：ICH Harmonised Guideline: Guideline for Good Clinical Practice E6(R3) — Final version, adopted 06 January 2025

- 发布方：International Council for Harmonisation (ICH)
- 落地页：https://www.ich.org/page/efficacy-guidelines
- PDF：https://database.ich.org/sites/default/files/ICH_E6%28R3%29_Step4_FinalGuideline_2025_0106.pdf
- 版本：Step 4 final, adopted 2025-01-06
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://database.ich.org/sites/default/files/ICH_E6%28R3%29_Step4_FinalGuideline_2025_0106.pdf（PDF 第 ii 页 Legal notice）：This document is protected by copyright and may, with the exception of the ICH logo, be used, reproduced, incorporated into other works, adapted, modified, translated or distributed under a public license provided that ICH's copyright in the document is acknowledged at all times. In case of any adaption, modification or translation of the document, reasonable steps must be taken to clearly label, demarcate or otherwise identify that changes were made to or based on the original document. […] The above-mentioned permissions do not apply to content supplied by third parties. Therefore, for documents where the copyright vests in a third party, permission for reproduction must be obtained from this copyright holder.
- 第三方内容：Legal notice carves out third-party-supplied content and the ICH logo; no third-party content identified in the guideline body. Exclude the logo when rendering. ich.org/page/legal-notice returned only an app shell and could not be verified.
- 理由：Explicit public licence covering use, reproduction, incorporation and distribution with attribution. Contains important-protocol-deviation definition (3.9.3), investigator deviation duties (2.5.3), Appendix B/C protocol-content requirements.
- 复核备注：无
- 备注：页数：86

### cand-0018：Protocol Deviations for Clinical Investigations of Drugs, Biological Products, and Devices — Guidance for Industry (Draft Guidance)

- 发布方：U.S. Food and Drug Administration (CDER, CBER, CDRH, OCE)
- 落地页：https://www.fda.gov/regulatory-information/search-fda-guidance-documents/protocol-deviations-clinical-investigations-drugs-biological-products-and-devices
- PDF：https://www.fda.gov/media/184745/download
- 版本：Draft, December 2024; Docket FDA-2023-D-5016
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://www.fda.gov/about-fda/about-website/website-policies（Website Policies: Copyright（2026-09-09 主会话复核一致））：Unless otherwise noted, the contents of the FDA website (www.fda.gov) — both text and graphics — are not copyrighted. They are in the public domain and may be republished, reprinted and otherwise used freely by anyone without the need to obtain permission from FDA. […] Credit to the U.S. Food and Drug Administration as the source is appreciated but not required.
- 第三方内容：Quotes ICH E3(R1) definitions in short excerpts (ICH copyright, quotation-length only). Otherwise a US government work. Marked Draft — Not for Implementation; may be superseded.
- 理由：Public-domain US government work with explicit republication permission. Contains verbatim protocol-deviation and important-protocol-deviation definitions.
- 复核备注：无
- 备注：页数：13

### cand-0019：Protocol Deviations and Violations — VCU/VCU Health Clinical Research SOP No. CR-RE-340.3

- 发布方：Virginia Commonwealth University / VCU Health (Wright Center for Clinical and Translational Research)
- 落地页：https://cctr.vcu.edu/support/clinical-research-sops-new/
- PDF：https://cctr.vcu.edu/media/cctr/images/support/clinical-research-sops/CR-RE-340ProtocolDeviationsandViolations.docx.pdf
- 版本：CR-RE-340.3, Final, Version Date 02/11/2025, Effective 03/14/2025
- 预判状态：**needs_review**；决策：待定
- 许可证据：
  - https://webstandards.vcu.edu/requirements/general/（VCU web standards（站点无条款页；privacy statement 无版权措辞；policy.vcu.edu 返回 403））：Websites must comply with the Intellectual Property policy.
  - https://cctr.vcu.edu/media/cctr/images/sops/CR-AD-100_SOPOperationalGuidelines.pdf（SOP CR-AD-100.5 正文）：Posting of the finalized SOP on the web will represent approval and publication of the VCU/VCU Health Clinical Research SOPs.
- 第三方内容：Cites 21 CFR 312.66 and 21 CFR 812.150(a)(4) (public domain). Definitions are institution-specific.
- 理由：Publicly posted institutional SOP with no explicit reuse permission and no terms page, so needs_review. Contains verbatim protocol deviation and protocol violation definitions.
- 复核备注：无
- 备注：页数：4

### cand-0020：CR010 Management of Protocol and GCP Deviations and Violations, v8.0

- 发布方：ACCORD (NHS Lothian and the University of Edinburgh)
- 落地页：https://www.accord.scot/cr010-management-protocol-and-gcp-deviations-and-violations
- PDF：https://accord.scot/sites/default/files/2025-10/CR010%20SOP%20v8.0.pdf
- 版本：v8.0, Issue 22 SEP 2025, Effective 01 OCT 2025 (landing page still shows v7.0 link dated 7 Nov 2024)
- 预判状态：**rejected**；决策：待定
- 许可证据：
  - https://www.accord.scot/cr010-management-protocol-and-gcp-deviations-and-violations（accord.scot 页脚）：Unless explicitly stated otherwise, all material is copyright © The University of Edinburgh 2026.
  - https://www.ed.ac.uk/about/website/website-terms-conditions（University of Edinburgh website terms）：You may view or download any part of the Site for private purposes […] you are not permitted, without our permission, to: store the Site, or any part of the Site, for any other purpose; print copies of the Site, or any part of the Site, for any other purpose; reproduce, copy or transmit the Site, or any part of the Site, in any way, for any other purpose or in any other medium.
- 第三方内容：Joint NHS Lothian / University of Edinburgh document; rights split not stated. PDF is AES-encrypted (empty password); every page says parties must visit www.accord.scot for the latest version.
- 理由：Terms permit download for private purposes only and prohibit storage/reproduction for other purposes without permission; rejected unless permission is obtained. Content is strong (deviation vs violation definitions, visit-window example, 3-day violation reporting limit).
- 复核备注：无
- 备注：页数：12

### cand-0021：Phase I, Open-Label, Dose-Ranging Study of the Safety and Immunogenicity of 2019-nCoV Vaccine (mRNA-1273) in Healthy Adults — DMID Protocol 20-0003, Version 7.0

- 发布方：NIAID DMID (IND sponsor); collaborator ModernaTX, Inc.; hosted on ClinicalTrials.gov
- 落地页：https://clinicaltrials.gov/study/NCT04283461
- PDF：https://cdn.clinicaltrials.gov/large-docs/61/NCT04283461/Prot_002.pdf
- 版本：Version 7.0, 30 July 2021; uploaded 2023-03-13；登记号：NCT04283461; DMID 20-0003
- 预判状态：**rejected**；决策：rejected
- 许可证据：
  - https://cdn.clinicaltrials.gov/large-docs/61/NCT04283461/Prot_002.pdf（PDF 每页页眉）：DMID/NIAID/NIH CONFIDENTIAL Page 1 of 116
  - https://clinicaltrials.gov/about-site/terms-conditions（Terms and Conditions（客户端渲染，代理引文取自站点 JS 路由包；2026-09-10 决策人经 Chrome 核实，页面最后更新 2023-01-31））：The ClinicalTrials.gov data carry an international copyright outside the United States and its Territories or Possessions. Some ClinicalTrials.gov data may be subject to the copyright of third parties; you should consult these entities for any additional terms of use. || You shall not assert any proprietary rights to any portion of the database, or represent the database or any part thereof to anyone as other than a United States Government database.
  - https://www.nlm.nih.gov/web_policies.html（Copyright Information）：Works produced by the U.S. government are not subject to copyright protection in the United States. Any such works found on National Library of Medicine (NLM) Web sites may be freely used or reproduced without permission in the U.S. || When using NLM Web sites, you may encounter documents, illustrations, photographs, or other content contributed by or licensed from private individuals, companies, or organizations that may be protected by U.S. and international copyright laws. || It is your responsibility to determine and satisfy copyright or other use restrictions when using materials that are not in the public domain. NLM cannot guarantee the copyright status for any item.
- 第三方内容：Contains Moderna proprietary descriptions (mRNA platform, proprietary ionizable lipid SM-102) inseparable from dosing sections.
- 理由：Confidentiality notice → rejected under rule 3. Flag for owner: NIH-authored and NIH-posted, header may be a legacy document-control marking. Content ideal for clause retrieval (deviation definition, five-working-day reporting limit, visit windows ±2/±14 days).
- 复核备注：2026-09-10 决策：维持 rejected，不作例外。明确的 CONFIDENTIAL 页眉和 Moderna 第三方内容优先于 NIH 作者身份；可另行向 NIAID 求证，但只有取得书面授权后才能作为新候选重新审核，不能原地翻转。2026-09-10 经 Chrome 复核 ClinicalTrials.gov 官方 Terms and Conditions（页面最后更新 2023-01-31）：条款适用于所有格式及取得方式，要求署名、保持数据更新、记录处理日期与修改，并明确部分数据可能受第三方版权约束，需向相关实体确认。结论：站点条款不构成对具体上传 protocol PDF 的独立开放许可。
- 备注：页数：116

### cand-0022：A Phase 2, Open-label, Single-arm Study of PVSRIPO and Pembrolizumab in Recurrent Glioblastoma — Protocol LUMINOS-101, Version 4.0

- 发布方：Istari Oncology, Inc. (sponsor); hosted on ClinicalTrials.gov
- 落地页：https://clinicaltrials.gov/study/NCT04479241
- PDF：https://cdn.clinicaltrials.gov/large-docs/41/NCT04479241/Prot_000.pdf
- 版本：Version 4.0, 26 May 2021; uploaded 2025-03-11；登记号：NCT04479241; LUMINOS-101; IND 014735
- 预判状态：**rejected**；决策：待定
- 许可证据：
  - https://cdn.clinicaltrials.gov/large-docs/41/NCT04479241/Prot_000.pdf（PDF 第 1 页 Confidentiality Statement）：Information contained in this protocol is confidential in nature, and may not be used, divulged, published, or otherwise disclosed to others except to the extent necessary to obtain approval of the institutional review board or independent ethics committee, or as required by law. Persons to whom this information is disclosed should be informed that this information is confidential and may not be further disclosed without the express written consent of Istari Oncology, Inc. (Istari)
  - https://clinicaltrials.gov/about-site/terms-conditions（Terms and Conditions（客户端渲染，代理引文取自站点 JS 路由包；2026-09-10 决策人经 Chrome 核实，页面最后更新 2023-01-31））：The ClinicalTrials.gov data carry an international copyright outside the United States and its Territories or Possessions. Some ClinicalTrials.gov data may be subject to the copyright of third parties; you should consult these entities for any additional terms of use. || You shall not assert any proprietary rights to any portion of the database, or represent the database or any part thereof to anyone as other than a United States Government database.
- 第三方内容：Entire document sponsor-proprietary; Merck pembrolizumab information embedded.
- 理由：Explicit sponsor confidentiality statement prohibiting use; unambiguous rejected. Kept as the documented example of the industry-protocol pattern.
- 复核备注：2026-09-10 经 Chrome 复核 ClinicalTrials.gov 官方 Terms and Conditions（页面最后更新 2023-01-31）：条款适用于所有格式及取得方式，要求署名、保持数据更新、记录处理日期与修改，并明确部分数据可能受第三方版权约束，需向相关实体确认。结论：站点条款不构成对具体上传 protocol PDF 的独立开放许可。
- 备注：页数：98

### cand-0023：A Phase 1b, Randomized, Double-Blind, Placebo-Controlled Trial of L9LS in Infants in Mali and Impact on R21/Matrix-M Vaccine Immunogenicity

- 发布方：NIAID (OCRPRO, Division of Clinical Research) with FMOS/USTTB Bamako; hosted on ClinicalTrials.gov
- 落地页：https://clinicaltrials.gov/study/NCT06461026
- PDF：https://cdn.clinicaltrials.gov/large-docs/26/NCT06461026/Prot_SAP_000.pdf
- 版本：Version Date 26 February 2026; uploaded 2026-05-20；登记号：NCT06461026; FMOS Protocol 2024/158/CE/USTTB; IND 160213
- 预判状态：**needs_review**；决策：待定
- 许可证据：
  - https://clinicaltrials.gov/about-site/terms-conditions（Terms and Conditions（客户端渲染，代理引文取自站点 JS 路由包；2026-09-10 决策人经 Chrome 核实，页面最后更新 2023-01-31））：The ClinicalTrials.gov data carry an international copyright outside the United States and its Territories or Possessions. Some ClinicalTrials.gov data may be subject to the copyright of third parties; you should consult these entities for any additional terms of use. || You shall not assert any proprietary rights to any portion of the database, or represent the database or any part thereof to anyone as other than a United States Government database.
  - https://www.nlm.nih.gov/web_policies.html（Copyright Information）：Works produced by the U.S. government are not subject to copyright protection in the United States. Any such works found on National Library of Medicine (NLM) Web sites may be freely used or reproduced without permission in the U.S. || When using NLM Web sites, you may encounter documents, illustrations, photographs, or other content contributed by or licensed from private individuals, companies, or organizations that may be protected by U.S. and international copyright laws. || It is your responsibility to determine and satisfy copyright or other use restrictions when using materials that are not in the public domain. NLM cannot guarantee the copyright status for any item.
- 第三方内容：Co-authored by non-federal institutions (USTTB/FMOS Mali; University of Washington, Harvard, Indiana University), so US-government public-domain basis may not cover the whole text. R21/Matrix-M is Serum Institute/Novavax product.
- 理由：Publicly downloadable with no restrictive statement and strong public-domain basis, but no affirmative permission and mixed authorship → needs_review. Rich in target clauses: visit-window table, missed-visit deviation rule, 7-calendar-day reporting limit, weight-based dosing table.
- 复核备注：2026-09-10 经 Chrome 复核 ClinicalTrials.gov 官方 Terms and Conditions（页面最后更新 2023-01-31）：条款适用于所有格式及取得方式，要求署名、保持数据更新、记录处理日期与修改，并明确部分数据可能受第三方版权约束，需向相关实体确认。结论：站点条款不构成对具体上传 protocol PDF 的独立开放许可。
- 备注：页数：90；PDF 全文检索无版权、保密或专有声明（仅受试者隐私相关“confidentiality”）

### cand-0024：药物临床试验质量管理规范（2026年修订）（国家药监局 国家卫生健康委 国家中医药局 国家疾控局公告 2026年第50号 附件1）

- 发布方：国家药品监督管理局等四部门；上海市药品监督管理局转载
- 落地页：https://yjj.sh.gov.cn/qtgzwj/20260608/89cbf084b5cb4eab8fd0fb56d8538a1d.html
- PDF：无（见备注）
- 版本：发布 2026-05-21，施行 2026-09-01；2020年第57号公告同时废止
- 预判状态：**needs_review**；决策：待定
- 许可证据：
  - https://yjj.sh.gov.cn/assets/js/bottom2019.js（站点页脚脚本注入文本）：沪ICP备10019319号-5  上海市药品监督管理局 版权所有
- 第三方内容：四部门联合发布，无第三方内容。格式标记：官方附件仅为 .doc（https://www.nmpa.gov.cn/directory/web/nmpa/images/1780901652137067855.doc，HTTP 200，80,384 字节），无 PDF；NMPA 原始页面 https://www.nmpa.gov.cn/xxgk/fgwj/xzhgfxwj/20260608103856150.html 返回 HTTP 412。法律审阅提示：著作权法第五条对行政性质官方文件的排除属于法律判断，非站点证据。
- 理由：中国 GCP 核心文本，2020 版已于 2026-09-01 废止；仅有“版权所有”声明 → needs_review；且违反 PDF-only 规则，需决策人裁定 .doc 是否可接受。含第五十四条术语定义与重要方案偏离报告要求。
- 复核备注：2026-09-10 决策：spec-v1 保持 PDF-only；本候选官方附件仅为 .doc，可保留在候选清单，不进入本轮探针集；DOCX/legacy DOC 支持留待后续 ingestion 版本。
- 备注：页数：25；格式标记：官方附件仅有 .doc（https://www.nmpa.gov.cn/directory/web/nmpa/images/1780901652137067855.doc）；NMPA 原页 HTTP 412

### cand-0025：关于印发《提升本市临床试验质量 助力创新药械研发上市的实施方案》的通知（沪药监药注〔2024〕216号）

- 发布方：上海市药品监督管理局、上海市卫生健康委员会、上海市科学技术委员会
- 落地页：https://yjj.sh.gov.cn/cmsres/2f/2f722e36aeb64be4a63eefefe49d95be/83fc871f1ef42dc6379c647c4713d308.pdf
- PDF：https://yjj.sh.gov.cn/cmsres/2f/2f722e36aeb64be4a63eefefe49d95be/83fc871f1ef42dc6379c647c4713d308.pdf
- 版本：2024-08-16（公开范围：主动公开）
- 预判状态：**needs_review**；决策：待定
- 许可证据：
  - https://yjj.sh.gov.cn/cmsres/2f/2f722e36aeb64be4a63eefefe49d95be/83fc871f1ef42dc6379c647c4713d308.pdf（PDF 首页）：（公开范围：主动公开）
  - https://yjj.sh.gov.cn/assets/js/bottom2019.js（站点页脚脚本注入文本）：沪ICP备10019319号-5  上海市药品监督管理局 版权所有
- 第三方内容：无；市级政府政策文件。
- 理由：本轮唯一验证到的白名单来源简体中文 PDF（省级药监）。相关性有限：属于市级临床试验质量政策而非 GCP 或操作 SOP。“主动公开”加“版权所有”不构成复用许可 → needs_review。
- 复核备注：无
- 备注：页数：10

### cand-0026：MedDRA 术语选择：考虑要点（ICH 认可的 MedDRA 用户指南，发布版本 4.26）

- 发布方：MedDRA MSSO（Maintenance and Support Services Organization）发布，ICH 认可指南；文档版权 ICH
- 落地页：https://www.meddra.org/how-to-use/support-documentation/chinese
- PDF：https://admin.meddra.org/sites/default/files/guidance/file/001329_termselptc_r4_26_mar2026_chinese.pdf
- 版本：发布版本 4.26，2026 年 3 月（PDF 物理第 1 页）；站点列表 date 2026-03-14；HTTP Last-Modified 2026-03-14
- 预判状态：**eligible**；决策：eligible
- 许可证据：
  - https://admin.meddra.org/sites/default/files/guidance/file/001329_termselptc_r4_26_mar2026_chinese.pdf（PDF 物理第 1 页「ICH 免责申明和版权公告」（2026-09-11 pypdf 6.15.0 抽取原文；文件 sha256 440123f479ab3c324337ef6f731fb6ab9303576c6c21ce30043e99a6d6b1a097））：本文档受版权保护，除 MedDRA 和 ICH 徽标外，只有始终承认 ICH 的文档版权，方可在公共许可下使用、复制、纳入其他作品、改写、修订、翻译或传播。在对本文档进行任何改写、修改或翻译时，必须采取合理措施清楚标明、区分或以其他方式识别出对原始文档或在原始文档基础上作出的变更。不能使人产生原始文件的改写、修订或翻译是经 ICH 认可或是由 ICH 发起的印象。 || 本文档“按原样”提供，概不作出任何类型的保证。在任何情况下，ICH 或原始文档的作者均不对因使用本文档而引致的任何申索、损失赔偿或其他法律责任负责。 || 上述许可不适用于由第三方提供的内容。因此，对于版权归属于第三方的文档，必须从该版权持有人处获得复制许可。 || MedDRA® 商标由 ICH 注册
  - https://www.meddra.org/how-to-use/support-documentation/chinese（页面为 Angular 客户端渲染；列表数据经站点 API https://admin.meddra.org/api/guidances-page（language=Chinese 分组，页面标题「考虑要点文档和 MedDRA 最佳规范文档」，date 2026-03-14）取得，2026-09-11 主会话核对；documentCollection 条目）："documentTitle": "MedDRA 术语选择：考虑要点 - 发布版本 4.26" … "guidanceFilePdf": {"url": "https://admin.meddra.org/sites/default/files/guidance/file/001329_termselptc_r4_26_mar2026_chinese.pdf", "size": "927064"}
- 第三方内容：文内 ICH 公告排除 MedDRA/ICH 徽标与第三方提供内容；正文示例使用 MedDRA 术语（LLT/PT），术语权利同属 ICH（MedDRA® 商标由 ICH 注册），不视为第三方；第 1.5 节提及 JMO 网站 www.pmrj.jp/jmo/ 仅为链接引用。PDF 元数据 Author 为个人姓名（译制人员），不改变许可主体。渲染时排除徽标。本许可只覆盖本指南文档，不覆盖 MedDRA 术语库、发行数据或 SMQ 数据集，不构成 DEC-005 术语源授权。
- 理由：文档自身载有与 ICH E6(R3)（cand-0017）实质相同的 ICH 公共许可：承认 ICH 版权即可使用、复制、纳入其他作品、改写与传播，改动须标明，不得暗示 ICH 认可；未见非商业限定。61 页、正文可抽取（42,076 字符），原生简体中文，是补足 zh-Hans ≥ 8 门禁的直接来源。归 PV：内容为不良事件/安全信息的 MedDRA 编码原则、死亡与转归、用药错误、超说明书使用等术语选择规则；不是 SOP，也不是临床诊疗依据，示例不得当作患者事实。
- 复核备注：2026-09-12 决策：许可通过（文内 ICH 公共许可）。使用条件：始终承认 ICH 版权；任何改写、翻译须标明；不得给人 ICH 认可或发起的印象；MedDRA/ICH 徽标与第三方内容不在许可内。本许可只覆盖本指南文档，不覆盖 MedDRA 术语库、发行数据或 SMQ 数据集，不构成 DEC-005 术语源授权。
- 备注：PV 归属理由：用于 PV 部门 AE/ADR 报告信息的 MedDRA 编码原则、只编码已报告信息、用药错误与超说明书使用术语选择条款检索；页数：61；PDF 2026-09-11 下载 sha256 440123f479ab3c324337ef6f731fb6ab9303576c6c21ce30043e99a6d6b1a097，927064 字节，HEAD Content-Length 一致；可抽取 42076 字符，第 13 页仅 93 字符（图表页，标注时需人工看图）；脚本变体 zh-Hans

### cand-0027：MedDRA 数据检索和展示：考虑要点（ICH 认可的 MedDRA 用户数据输出指南，发布版本 3.26）

- 发布方：MedDRA MSSO（Maintenance and Support Services Organization）发布，ICH 认可指南；文档版权 ICH
- 落地页：https://www.meddra.org/how-to-use/support-documentation/chinese
- PDF：https://admin.meddra.org/sites/default/files/guidance/file/001330_datretptc_r3_26_mar2026_chinese.pdf
- 版本：发布版本 3.26，2026 年 3 月（PDF 物理第 1 页）；站点列表 date 2026-03-14；HTTP Last-Modified 2026-03-14
- 预判状态：**eligible**；决策：eligible
- 许可证据：
  - https://admin.meddra.org/sites/default/files/guidance/file/001330_datretptc_r3_26_mar2026_chinese.pdf（PDF 物理第 1 页「ICH 免责申明和版权公告」（2026-09-11 pypdf 6.15.0 抽取原文；文件 sha256 ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938））：本文档受版权保护，除 MedDRA 和 ICH 徽标外，只有始终承认 ICH 的文档版权，方可在公共许可下使用、复制、纳入其他作品、改写、修订、翻译或传播。在对本文档进行任何改写、修改或翻译时，必须采取合理措施清楚标明、区分或以其他方式识别出对原始文档或在原始文档基础上作出的变更。不能使人产生原始文件的改写、修订或翻译是经 ICH 认可或是由 ICH 发起的印象。 || 本文档“按原样”提供，概不作出任何类型的保证。在任何情况下，ICH 或原始文档的作者均不对因使用本文档而引致的任何申索、损失赔偿或其他法律责任负责。 || 上述许可不适用于由第三方提供的内容。因此，对于版权归属于第三方的文档，必须从该版权持有人处获得复制许可。 || MedDRA® 商标由 ICH 注册
  - https://www.meddra.org/how-to-use/support-documentation/chinese（页面为 Angular 客户端渲染；列表数据经站点 API https://admin.meddra.org/api/guidances-page（language=Chinese 分组，页面标题「考虑要点文档和 MedDRA 最佳规范文档」，date 2026-03-14）取得，2026-09-11 主会话核对；documentCollection 条目）："documentTitle": "MedDRA 数据检索和展示：考虑要点 - 发布版本 3.26" … "guidanceFilePdf": {"url": "https://admin.meddra.org/sites/default/files/guidance/file/001330_datretptc_r3_26_mar2026_chinese.pdf", "size": "979986"}
- 第三方内容：文内 ICH 公告排除 MedDRA/ICH 徽标与第三方提供内容；正文含 MedDRA 术语与 SMQ 名称示例，权利同属 ICH，不视为第三方；引用 ICH 认可的 SMQ 只作说明。多页为表格/图形页（第 6、16、17、18、42、43、46 页可抽取文本不足 150 字符），不能仅凭文本可抽取就宣称全部解析合格。渲染时排除徽标。本许可只覆盖本指南文档，不覆盖 MedDRA 术语库、发行数据或 SMQ 数据集，不构成 DEC-005 术语源授权。
- 理由：文档自身独立载有与 cand-0026 相同的 ICH 公共许可原文（不是借用其他渠道的许可）：承认版权、标明修改、不得暗示 ICH 认可，第三方内容与徽标除外；未见非商业限定。49 页、正文可抽取（35,451 字符），原生简体中文。归 PV：内容为药物警戒安全数据的检索、分析与呈现——源数据质量、检索记录、MedDRA 版本管理影响、SMQ 与自定义查询；不是 SOP。
- 复核备注：2026-09-12 决策：许可通过（文内 ICH 公共许可）。使用条件：始终承认 ICH 版权；任何改写、翻译须标明；不得给人 ICH 认可或发起的印象；MedDRA/ICH 徽标与第三方内容不在许可内。本许可只覆盖本指南文档，不覆盖 MedDRA 术语库、发行数据或 SMQ 数据集，不构成 DEC-005 术语源授权。
- 备注：PV 归属理由：用于 PV 部门安全数据检索方法、SMQ 与自定义查询、MedDRA 版本管理对分析影响的条款检索；页数：49；PDF 2026-09-11 下载 sha256 ea0824b58213d740df8ac7459c3c9b08819aa21127a7c63fe04b81ec056f9938，979986 字节，官方 admin.meddra.org 与镜像 alt.meddra.org/files_acrobat/ 同名文件 sha256 一致；可抽取 35451 字符；脚本变体 zh-Hans

### cand-0028：ICH Harmonised Guideline E8(R1): General Considerations for Clinical Studies

- 发布方：International Council for Harmonisation (ICH)
- 落地页：https://www.ich.org/page/efficacy-guidelines
- PDF：https://database.ich.org/sites/default/files/E8-R1_Guideline_Step4_2021_1006.pdf
- 版本：Final version, adopted 6 October 2021 (Step 4)（PDF 物理第 1、3 页）；HTTP Last-Modified 2021-10-06
- 预判状态：**eligible**；决策：eligible
- 许可证据：
  - https://database.ich.org/sites/default/files/E8-R1_Guideline_Step4_2021_1006.pdf（PDF 物理第 3 页（页码 i，Document History 下方）Legal notice（2026-09-11 pypdf 6.15.0 抽取原文；文件 sha256 99d56638828c823bb603ff3ef451fcfafc607de8a5b3926136d64980f27baa13））：Legal notice: This document is protected by copyright and may, with the exception of the ICH logo, be used, reproduced, incorporated into other works, adapted, modified, translated or distributed under a public license provided that ICH's copyright in the document is acknowledged at all times. In case of any adaption, modification or translation of the document, reasonable steps must be taken to clearly label, demarcate or otherwise identify that changes were made to or based on the original document. Any impression that the adaption, modification or translation of the original document is endorsed or sponsored by the ICH must be avoided. || The document is provided "as is" without warranty of any kind. In no event shall the ICH or the authors of the original document be liable for any claim, damages or other liability arising from the use of the document. || The above-mentioned permissions do not apply to content supplied by third parties. Therefore, for documents where the copyright vests in a third party, permission for reproduction must be obtained from this copyright holder.
  - https://www.ich.org/page/legal-mentions（Legal Mentions（页面客户端渲染；正文经站点 JSON 接口 admin.ich.org/api/v1/nodes?alias=/page/legal-mentions 于 2026-09-09 取得；2026-09-11 该接口仅返回节点元数据，正文段落未重新取得，以文内 Legal notice 为主证据））：The information, material and photographic content provided on this website are protected by copyright and may, with the exception of the ICH logo, be used, reproduced, incorporated into other works, adapted, modified, translated or distributed under a public license provided that ICH's copyright in the information and material is acknowledged at all times. […] The above-mentioned permissions do not apply to content supplied by third parties. Therefore, for documents where the copyright vests in a third party, permission for reproduction must be obtained from this copyright holder.
- 第三方内容：Legal notice carves out the ICH logo and third-party-supplied content; no third-party content identified in the body (references to other ICH guidelines are citations). Exclude the logo when rendering. Physical pages 2 and 6 are blank (0 extractable characters).
- 理由：In-document ICH public licence identical in substance to cand-0017 (E6(R3)): use, reproduce, incorporate into other works, adapt with acknowledgement; changes must be labelled; no impression of ICH endorsement. Independent CO guideline on study design, quality by design, participant protection and study conduct; adds a third CO document. Real type is guideline, not protocol. ICH adoption date is not the implementation date of any jurisdiction.
- 复核备注：2026-09-12 决策：许可通过（文内 ICH 公共许可）。使用条件：始终承认 ICH 版权；任何改写、翻译须标明；不得给人 ICH 认可或发起的印象；MedDRA/ICH 徽标与第三方内容不在许可内。
- 备注：CO 归属理由：临床研究设计、质量要素、受试者保护与研究实施通则，用于 CO 部门方案设计与偏离相关条款检索，doc_type 保持 guideline；页数：29；PDF 2026-09-11 下载 sha256 99d56638828c823bb603ff3ef451fcfafc607de8a5b3926136d64980f27baa13，368189 字节，HEAD Content-Length 一致；可抽取 79130 字符；物理第 2、6 页空白

### cand-0029：美洛醣膜衣錠850毫克（Loformin Film-coated Tablets 850mg, metformin hydrochloride）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；仿單載明 育生企業股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E9%83%A8%E8%97%A5%E8%A3%BD%E5%AD%97%E7%AC%AC058257%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_8537065c-b1e6-4158-8958-d2dab0a8a4c0?c=2
- 版本：仿單正文未见版本或修订日期；PDF 元数据 CreationDate 2015-10-06；licence 衛部藥製字第058257號（快照记录 69）；许可证现行状态未核对
- 预判状态：**eligible**；决策：eligible
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-11 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，zip 成员时间戳 2026-09-10 10:02，29,860 条记录，zip sha256 见 notes；字段 仿單圖檔連結）：记录序号 69（JSON 数组 1-based），許可證字號 衛部藥製字第058257號，中文品名 美洛醣膜衣錠850毫克；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_8537065c-b1e6-4158-8958-d2dab0a8a4c0?c=2
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_8537065c-b1e6-4158-8958-d2dab0a8a4c0?c=2（PDF 全文文本扫描（pypdf 6.15.0，2026-09-11；2 页，可抽取 7548 字符；标记词 ©/Ⓒ/版權/著作權/Copyright/All rights reserved/保密/Confidential/不得/禁止/授權/商標/®/™）；唯一命中为临床文本，未发现版权、保密或禁止复用声明）：【藥物間的交互作用】(依文獻記載) 禁止合併服用: 含碘顯影劑
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛部藥製字第058257號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛部藥製字第058257號", "註銷狀態": "", "註銷日期": null, "註銷理由": "", "有效日期": "2029/04/21", "發證日期": "2014/04/21", "申請商名稱": "盈盈生技製藥股份有限公司三峽廠", "製造商名稱": "生達化學製藥股份有限公司二廠"
- 第三方内容：仿單正文由許可證持有者/製造商撰寫（育生企業股份有限公司），含產品名稱商標；OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌，使用時不得主張商標權。同一 PDF 同時載 500 毫克（衛署藥製字第034549號；快照另有記錄 15392 指向不同上傳 PDF）與 850 毫克產品，按一份文檔登記，不拆分凑数。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对四项条件：(1) pdf_url 在 2026-09-11 同日下载的数据集快照中逐字出现（记录 69）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本层无版权、保密、禁止复用声明，唯一命中「禁止合併服用」为临床文本——文本层通过，图像层未做视觉核查；(4) OGDL 署名与不主张商标权——入库时在 license_or_terms 落实。据此预判 eligible。MAH 撰写内容是否在 OGDL 覆盖范围内、许可证是否现行有效，决策 1 未明示，由决策人裁定。
- 复核备注：2026-09-12 决策：许可通过（数据集 9117 OGDL-1.0；四项条件已机械证明；MAH 撰写内容视为在覆盖内；同日快照按下载日）。现行性核对：衛部藥製字第058257號 未註銷，有效日期 2029/04/21，申請商 盈盈生技製藥股份有限公司三峽廠、製造商 生達化學製藥股份有限公司二廠；仿單载 育生企業股份有限公司，与现行申請商不同，且无版本行，入 corpus 时 version_label 只能记 PDF 元数据日期 2015-10-06 并标注「未见版本行」。图像层：2 页 Quartz 渲染目视，无版权/保密标记。
- 备注：页数：2；PDF 2026-09-11 下载 sha256 b6af0d88b1f0e3b5660e6e3c6678e18c40616073bc082b6cb7214604b2f81f98，772806 字节，HEAD Content-Length 一致；可抽取 7548 字符；仿單同載 500mg/850mg；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

### cand-0030：安通脈膜衣錠10毫克/10毫克（Amlodipine Besylate and Atorvastatin Mylan 10mg/10mg）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；藥商 台灣邁蘭有限公司；製造廠 Mylan Laboratories Limited
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E9%83%A8%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC026582%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_cbb592f7-eda5-404e-836f-b68ebe87c47f?c=2
- 版本：仿單末页「版本日期：2014/11/05」；PDF 元数据 CreationDate 2015-10-22；licence 衛部藥輸字第026582號（快照记录 4778）；是否为现行版本未核对
- 预判状态：**eligible**；决策：eligible
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-11 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，zip 成员时间戳 2026-09-10 10:02，29,860 条记录，zip sha256 见 notes；字段 仿單圖檔連結）：记录序号 4778（JSON 数组 1-based），許可證字號 衛部藥輸字第026582號，中文品名 安通脈膜衣錠10毫克/10毫克；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_cbb592f7-eda5-404e-836f-b68ebe87c47f?c=2
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_cbb592f7-eda5-404e-836f-b68ebe87c47f?c=2（PDF 全文文本扫描（pypdf 6.15.0，2026-09-11；13 页，可抽取 33443 字符；标记词 ©/Ⓒ/版權/著作權/Copyright/All rights reserved/保密/Confidential/不得/禁止/授權/商標/®/™）；唯一命中为交互作用表中的第三方产品名，未发现版权、保密或禁止复用声明）：Maalox TC ® 30 毫升QD ，17 天
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛部藥輸字第026582號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛部藥輸字第026582號", "註銷狀態": "已廢止", "註銷日期": "2024/05/15", "註銷理由": "未依公告辦理變更", "有效日期": "2025/08/05", "發證日期": "2015/08/05", "申請商名稱": "台灣邁蘭有限公司", "製造商名稱": "MYLAN LABORATORIES LIMITED"
- 第三方内容：仿單正文由藥商/製造商撰寫（台灣邁蘭有限公司 / Mylan Laboratories Limited），含產品商標；交互作用表提及第三方產品名（Maalox TC®）僅為引用。OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌。抽取文本存在字形重复（如「版本日期版本日期…」），源于 PDF 字体嵌入方式，标注 key_text 时需人工核对。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对四项条件：(1) pdf_url 在 2026-09-11 同日下载的数据集快照中逐字出现（记录 4778）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本层无版权、保密、禁止复用声明，唯一命中 ® 为第三方产品名引用——文本层通过，图像层未做视觉核查；(4) OGDL 署名与不主张商标权——入库时落实。据此预判 eligible。文内版本日期 2014/11/05 是否为现行版本、MAH 撰写内容是否在 OGDL 覆盖范围内，由决策人裁定。
- 复核备注：2026-09-12 决策：许可通过（同 cand-0029 口径）。现行性核对：衛部藥輸字第026582號 已廢止（註銷日期 2024/05/15，理由 未依公告辦理變更；原有效日期 2025/08/05）。图像层：13 页目视无版权标记，仅 Maalox TC® 为第三方商标引用。许可可用但不是现行仿單；是否进入探针集 v1 由决策人按现行性口径决定。
- 备注：页数：13；PDF 2026-09-11 下载 sha256 981179a8193fb8c9e3cc0e5e62ec865cdca14153861482bd380117370ad87591，530101 字节，HEAD Content-Length 一致；可抽取 33443 字符，存在字形重复抽取；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

### cand-0031：吉福坦膜衣錠100毫克（Losartan Jubilant film-coated tablet 100mg, losartan potassium）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；藥商 吉富貿易有限公司；製造廠 Jubilant Generics Limited
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E9%83%A8%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC026322%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_73d0eb14-8c98-4ad4-afd4-aa92ebb40083?c=2
- 版本：仿單末行「版本：V2.01_20190124 修訂」；PDF 元数据 CreationDate 2019-02-12；licence 衛部藥輸字第026322號（快照记录 2927）；是否为现行版本未核对
- 预判状态：**eligible**；决策：eligible
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-11 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，zip 成员时间戳 2026-09-10 10:02，29,860 条记录，zip sha256 见 notes；字段 仿單圖檔連結）：记录序号 2927（JSON 数组 1-based），許可證字號 衛部藥輸字第026322號，中文品名 吉福坦膜衣錠100毫克；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_73d0eb14-8c98-4ad4-afd4-aa92ebb40083?c=2
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_73d0eb14-8c98-4ad4-afd4-aa92ebb40083?c=2（PDF 全文文本扫描（pypdf 6.15.0，2026-09-11；2 页，可抽取 13244 字符；标记词 ©/Ⓒ/版權/著作權/Copyright/All rights reserved/保密/Confidential/不得/禁止/授權/商標/®/™）；零命中，未发现版权、保密或禁止复用声明）：藥 商：吉富貿易有限公司 … 版本：V2.01_20190124 修訂
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛部藥輸字第026322號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛部藥輸字第026322號", "註銷狀態": "已註銷", "註銷日期": "2025/04/24", "註銷理由": "許可證已逾有效期", "有效日期": "2024/06/09", "發證日期": "2014/06/09", "申請商名稱": "吉富貿易有限公司", "製造商名稱": "JUBILANT GENERICS LIMITED"
- 第三方内容：仿單正文由藥商/製造商撰寫（吉富貿易有限公司 / Jubilant Generics Limited），含產品名稱商標；OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌。同一 PDF 同時載 50 毫克（衛部藥輸字第026321號；快照另有記錄 29092 指向不同上傳 PDF）與 100 毫克產品，按一份文檔登記，不拆分凑数。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对四项条件：(1) pdf_url 在 2026-09-11 同日下载的数据集快照中逐字出现（记录 2927）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本层标记词零命中——文本层通过，图像层未做视觉核查；(4) OGDL 署名与不主张商标权——入库时落实。据此预判 eligible。文内版本 V2.01_20190124 是否为现行版本、MAH 撰写内容是否在 OGDL 覆盖范围内，由决策人裁定。
- 复核备注：2026-09-12 决策：许可通过（同 cand-0029 口径）。现行性核对：衛部藥輸字第026322號 已註銷（註銷日期 2025/04/24，理由 許可證已逾有效期；有效日期 2024/06/09）。图像层：2 页目视无版权标记。许可可用但不是现行仿單；是否进入探针集 v1 由决策人按现行性口径决定。
- 备注：页数：2；PDF 2026-09-11 下载 sha256 af256d92508d5e3cc3dd6f872184ac5c165b84e4de63bf7c7055c1a3163090d0，1060542 字节，HEAD Content-Length 一致；可抽取 13244 字符；仿單同載 50mg/100mg；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

### cand-0032：艾摩喜林黴素膠囊（安莫西林）（AMOXICILLIN CAPSULES "TAI YU"）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；仿單載明 台裕化學製藥廠股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%A3%BD%E5%AD%97%E7%AC%AC021441%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_ba28a5d8-d65e-404f-8c1f-2e57fb505af7?c=2
- 版本：仿單正文未见版本或修订日期；PDF 元数据 CreationDate 2015-12-29，/Title 为模板文字「衛署藥製字第XXXXXX號」；licence 衛署藥製字第021441號（快照记录 375）；许可证现行状态未核对
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-11 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，zip 成员时间戳 2026-09-10 10:02，29,860 条记录，zip sha256 见 notes；字段 仿單圖檔連結）：记录序号 375（JSON 数组 1-based），許可證字號 衛署藥製字第021441號，中文品名 艾摩喜林黴素膠囊（安莫西林）；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_ba28a5d8-d65e-404f-8c1f-2e57fb505af7?c=2
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_ba28a5d8-d65e-404f-8c1f-2e57fb505af7?c=2（PDF 全文文本扫描（pypdf 6.15.0，2026-09-11；1 页，可抽取 695 字符；标记词 ©/Ⓒ/版權/著作權/Copyright/All rights reserved/保密/Confidential/不得/禁止/授權/商標/®/™）；文本末尾存在圈 C 符号 U+24B8「Ⓒ」，普通只查 © 的扫描会漏掉，含义未确认）：新竹縣竹東鎮員山路 11 巷 13 弄 1 號 TEL：(03)5826655 FAX：(03)5822389 Ⓒ
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛署藥製字第021441號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛署藥製字第021441號", "註銷狀態": "已註銷", "註銷日期": "2025/07/04", "註銷理由": "許可證已逾有效期", "有效日期": "2023/05/12", "發證日期": "1980/05/12", "申請商名稱": "台裕化學製藥廠股份有限公司", "製造商名稱": "政德製藥股份有限公司"
- 第三方内容：仿單正文由製造商撰寫（台裕化學製藥廠股份有限公司），含產品名稱商標；文本末尾製造商地址後有「Ⓒ」符号，可能是版权标记，也可能是排版符号，需人工看图与权利核验。全文仅 695 字符，可标注的精确条款很少。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对：(1) pdf_url 在 2026-09-11 同日下载的数据集快照中逐字出现（记录 375）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本末尾出现「Ⓒ」——不能证明无附加限制声明，条件 (3) 不通过；按决策 1「任一条件失败即保持 needs_review」。另外正文极短，样本产出有限。
- 复核备注：2026-09-12 决策：允许继续核查。结果：图像层确认文末为 © 标记（製造商標誌旁），条件 (3) 不通过；现行性：衛署藥製字第021441號 已註銷（2025/07/04，許可證已逾有效期；有效日期 2023/05/12）。保持 needs_review。
- 备注：页数：1；PDF 2026-09-11 下载 sha256 9a0e693974c7d22b7731bba272ebdcc2f42f2e7bbe9ca0ebfb01bfd5ab23fe6f，188746 字节，HEAD Content-Length 一致；可抽取 695 字符；文本末尾 U+24B8「Ⓒ」；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

### cand-0033：血脂安膜衣錠20毫克（pms-Rosuvastatin 20mg tablets）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；藥商/製造廠 未能自 PDF 文本抽取（扫描件）
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E9%83%A8%E8%97%A5%E8%BC%B8%E5%AD%97%E7%AC%AC026332%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_9c389897-3c7d-4592-8df3-1cde5b6245e7?c=2
- 版本：无可抽取文本，版本未知；PDF 元数据 CreationDate 2014-10-06；licence 衛部藥輸字第026332號（快照记录 2933）；许可证现行状态未核对
- 预判状态：**needs_review**；决策：needs_review
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-11 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，zip 成员时间戳 2026-09-10 10:02，29,860 条记录，zip sha256 见 notes；字段 仿單圖檔連結）：记录序号 2933（JSON 数组 1-based），許可證字號 衛部藥輸字第026332號，中文品名 血脂安膜衣錠20毫克；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_9c389897-3c7d-4592-8df3-1cde5b6245e7?c=2
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_9c389897-3c7d-4592-8df3-1cde5b6245e7?c=2（PDF 全文文本扫描（pypdf 6.15.0，2026-09-11；9 页，每页可抽取字符 0，总计 8 个空白字符）；元数据仅有 CreationDate）：D:20141006144049Z（PDF 元数据 /CreationDate；正文无可抽取文本）
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛部藥輸字第026332號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛部藥輸字第026332號", "註銷狀態": "已註銷", "註銷日期": "2020/08/27", "註銷理由": "屆期未申請展延", "有效日期": "2019/06/26", "發證日期": "2014/06/26", "申請商名稱": "富富企業股份有限公司", "製造商名稱": "PHARMASCIENCE INC."
- 第三方内容：扫描件：藥商、製造商、商標與任何版权标记均无法自文本层核验，需 OCR 或逐页视觉检查后才能判断第三方内容与附加限制。脚本变体 zh-Hant（按快照中文品名判断）。
- 理由：按 ADR-0003 决策 1 机械核对：(1) pdf_url 在 2026-09-11 同日下载的数据集快照中逐字出现（记录 2933）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) 9 页均无可抽取文本，无法机械证明无附加限制声明——条件 (3) 无法验证，保持 needs_review。另外 spec-v1 的 gold 与页文本校验依赖可抽取页文本，本文件未做 OCR，不建议进入首批。
- 复核备注：2026-09-12 决策：允许继续核查。结果：图像层 9 页目视未见版权标记，但无文本层、未做 OCR，条件 (3) 无法机械证明；现行性：衛部藥輸字第026332號 已註銷（2020/08/27，屆期未申請展延；有效日期 2019/06/26）。保持 needs_review。
- 备注：页数：9；PDF 2026-09-11 下载 sha256 1fb788ee7c0027797a5b9c2e6078e9def035d73f6bc17b8132f3df60dfb2db4f，6289605 字节，HEAD Content-Length 一致；每页可抽取字符 0（扫描件，未 OCR）；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

### cand-0034：痛風停錠300毫克（Deurinol Tablets 300mg, allopurinol）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；申請商/製造商 寶齡富錦生技股份有限公司（平鎮廠）
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%A3%BD%E5%AD%97%E7%AC%AC048564%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_919feaa0-dcde-4ceb-b0b4-d5b10a93c0c5?c=2
- 版本：仿單正文未见版本行；PDF 元数据 CreationDate 2018-02-09；licence 衛署藥製字第048564號 现行（有效日期 2027/01/30，異動日期 2026/07/20）
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-12 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，与 2026-09-11 下载逐字节相同，zip sha256 见 notes；29,860 条）：记录序号 15545（JSON 数组 1-based），許可證字號 衛署藥製字第048564號，中文品名 痛風停錠300毫克；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_919feaa0-dcde-4ceb-b0b4-d5b10a93c0c5?c=2
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛署藥製字第048564號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛署藥製字第048564號", "註銷狀態": "", "有效日期": "2027/01/30", "發證日期": "2007/01/30", "申請商名稱": "寶齡富錦生技股份有限公司", "製造商名稱": "寶齡富錦生技股份有限公司平鎮廠"
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_919feaa0-dcde-4ceb-b0b4-d5b10a93c0c5?c=2（PDF 全文文本扫描：2026-09-12 以 pypdf 6.15.0（会话临时环境）初筛，2026-09-13 以锁定版 pypdf 6.18.1 复测：10 页，可抽取 12854 字符，pypdf 告警 0 条；标记词 ©/Ⓒ/版權/著作權/Copyright/保密/不得/禁止/授權/商標/®/™；两处「不得」命中均为临床文本，未发现版权、保密或禁止复用声明）：Allopurinol 沒有抗發炎的效力，它必須不得使用於痛風性關節炎的急性發作
- 第三方内容：仿單正文由製造商撰寫（寶齡富錦生技股份有限公司），末页含公司標誌；OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌。正文含 HLA-B*5801 与 SJS/TEN 等安全条款，适合 negation/dose_unit/time_window 切片。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对四项条件：(1) pdf_url 在 2026-09-12 同日下载的数据集快照中逐字出现（记录 15545）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本层无版权、保密、禁止复用声明，且逐页 Quartz 渲染目视无版权标记——通过；(4) OGDL 署名与不主张商标权——入库时落实。按 2026-09-12 决策口径（MAH 撰写内容在 OGDL 覆盖内）预判 eligible。现行性：许可证未註銷，有效日期 2027/01/30。10 页正文可抽取且字形正常，是本批文本量最大的现行仿單。 2026-09-13 复测：逐页异常字符扫描仅见竖排标点 ︰﹕﹔（正常字符）。
- 复核备注：无
- 备注：页数：10；PDF 2026-09-12 下载 sha256 42f20f2b5b0ea0ed7afe8bb709699a58b222985b70ccada6e0c470f5c3f58a7f，348061 字节，HTTP 200 application/pdf；可抽取 12854（pypdf 6.18.1；6.15.0 初筛为 12909） 字符；pypdf 告警 0 条；许可证现行不等于本 PDF 为现行修订版，仿單版本以文内版本行为准；PDF 元数据 /Title 为模板文字「Xxxx錠 300公絲」；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

### cand-0035：穩壓膜衣錠50毫克（Zosaa F.C. Tablets 50mg, losartan potassium）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；申請商/製造商 中國化學製藥股份有限公司新豐工廠
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%A3%BD%E5%AD%97%E7%AC%AC047911%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_5d4379de-6b30-4c2d-a514-58be107f0df0?c=2
- 版本：仿單载日期字样「2015.9.11」「104.10.27」（含义未标明，需人工确认是否修订日期）；PDF 元数据 2016-01-29；licence 047911 现行，有效日期 2031/03/30
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-12 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，与 2026-09-11 下载逐字节相同，zip sha256 见 notes；29,860 条）：记录序号 14345（JSON 数组 1-based），許可證字號 衛署藥製字第047911號，中文品名 穩壓膜衣錠50毫克；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_5d4379de-6b30-4c2d-a514-58be107f0df0?c=2
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛署藥製字第047911號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛署藥製字第047911號", "註銷狀態": "", "有效日期": "2031/03/30", "發證日期": "2006/03/30", "申請商名稱": "中國化學製藥股份有限公司新豐工廠", "製造商名稱": "中國化學製藥股份有限公司新豐工廠"
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_5d4379de-6b30-4c2d-a514-58be107f0df0?c=2（PDF 全文文本扫描：2026-09-12 以 pypdf 6.15.0（会话临时环境）初筛，2026-09-13 以锁定版 pypdf 6.18.1 复测：1 页，可抽取 4800 字符，pypdf 告警 0 条；标记词 ©/Ⓒ/版權/著作權/Copyright/保密/不得/禁止/授權/商標/®/™；零命中，未发现版权、保密或禁止复用声明；页面右下公司標誌带 ® 为公司商标）：中國化學製藥股份有限公司 CHINA CHEMICAL & PHARMACEUTICAL CO., LTD. 總公司：台北市襄陽路 23 號
- 第三方内容：仿單正文由製造商撰寫（中國化學製藥股份有限公司），页面含带 ® 的公司標誌；OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌。单页双栏排版，抽取顺序需人工核对。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对四项条件：(1) pdf_url 在 2026-09-12 同日下载的数据集快照中逐字出现（记录 14345）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本层无版权、保密、禁止复用声明，且逐页 Quartz 渲染目视无版权标记——通过；(4) OGDL 署名与不主张商标权——入库时落实。按 2026-09-12 决策口径（MAH 撰写内容在 OGDL 覆盖内）预判 eligible。现行性：许可证未註銷，有效日期 2031/03/30。单页 4,809 字符，内容完整（适应症、用法用量、禁忌、警语、不良反应表）。 2026-09-13 复测：逐页异常字符扫描仅见 Ⅱ 与 ○（正常字符）。
- 复核备注：无
- 备注：页数：1；PDF 2026-09-12 下载 sha256 81069adaf87d21e640d9b5cbc83a799a59a33acbdc4ead46ed338c9ad6d06b3a，317957 字节，HTTP 200 application/pdf；可抽取 4800（pypdf 6.18.1；6.15.0 初筛为 4809） 字符；pypdf 告警 0 条；许可证现行不等于本 PDF 为现行修订版，仿單版本以文内版本行为准；单页双栏；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

### cand-0036：欣服寧錠3毫克（Synfarin Tablets 3mg, warfarin sodium）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；申請商/製造商 健喬信元醫藥生技股份有限公司（健喬廠）
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%A3%BD%E5%AD%97%E7%AC%AC050230%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_4958a013-b9fc-42d8-b0e9-ed8bdfb406ad?c=2
- 版本：仿單正文未见版本行；PDF 元数据 2016-02-22；licence 050230 现行，有效日期 2029/07/14；同一仿單同載 1/2.5/3/5 毫克，本条只登记 3 毫克记录
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-12 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，与 2026-09-11 下载逐字节相同，zip sha256 见 notes；29,860 条）：记录序号 2510（JSON 数组 1-based），許可證字號 衛署藥製字第050230號，中文品名 欣服寧 錠 3 毫克；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_4958a013-b9fc-42d8-b0e9-ed8bdfb406ad?c=2
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛署藥製字第050230號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛署藥製字第050230號", "註銷狀態": "", "有效日期": "2029/07/14", "發證日期": "2009/07/14", "申請商名稱": "健喬信元醫藥生技股份有限公司", "製造商名稱": "健喬信元醫藥生技股份有限公司健喬廠"
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_4958a013-b9fc-42d8-b0e9-ed8bdfb406ad?c=2（PDF 全文文本扫描：2026-09-12 以 pypdf 6.15.0（会话临时环境）初筛，2026-09-13 以锁定版 pypdf 6.18.1 复测：4 页，可抽取 18975 字符，pypdf 告警 0 条；标记词 ©/Ⓒ/版權/著作權/Copyright/保密/不得/禁止/授權/商標/®/™；零命中，未发现版权、保密或禁止复用声明）：健喬信元醫藥生技股份有限公司 藥商地址：303新竹縣湖口鄉光復北路21巷4號
- 第三方内容：仿單正文由製造商撰寫（健喬信元醫藥生技股份有限公司），含產品名稱商標；OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌。抽取文本存在少量字形映射错误（寧→⮏、字→⫿），按 SPEC §4 含乱码的页是否可作 gold 来源需在标注阶段逐页判定，key_text 不得含错误字形。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对四项条件：(1) pdf_url 在 2026-09-12 同日下载的数据集快照中逐字出现（记录 2510）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本层无版权、保密、禁止复用声明，且逐页 Quartz 渲染目视无版权标记——通过；(4) OGDL 署名与不主张商标权——入库时落实。按 2026-09-12 决策口径（MAH 撰写内容在 OGDL 覆盖内）预判 eligible。现行性：许可证未註銷，有效日期 2029/07/14。INR、时间窗与禁忌条款丰富。 2026-09-13 复测：逐页异常字符扫描：四页均有字形映射错误（p1 297、p2 300、p3 254、p4 33 个可疑字符，如「減Ͽ」「個㚰」「72军96」「欣服⮏」），属乱码页。2026-09-13 复测（锁定 pypdf 6.18.1）：四页均有字形映射错误，按 SPEC §4 属乱码页，本轮排除，不作为探针集 v1 gold 来源；不做 OCR，不建手写替换表。许可预判不变，仅抽取质量不合格。
- 复核备注：无
- 备注：页数：4；PDF 2026-09-12 下载 sha256 9f1538840d9bb2f919885a0ec74c8a12557452b28ac1ae096690770ec650f7ad，575636 字节，HTTP 200 application/pdf；可抽取 18975（pypdf 6.18.1；6.15.0 初筛为 18983） 字符；pypdf 告警 0 条；许可证现行不等于本 PDF 为现行修订版，仿單版本以文内版本行为准；字形映射错误遍及四页（如「減Ͽ」「個㚰」「欣服⮏」）；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36；本轮排除（抽取乱码）

### cand-0037："明德"心壓暢錠100毫克（美托普洛）（Cancliol Tablets 100mg, metoprolol tartrate）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；申請商/製造商 明德製藥股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E7%BD%B2%E8%97%A5%E8%A3%BD%E5%AD%97%E7%AC%AC029301%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_dd2c70ce-0124-4720-9874-a4be9305cfb9?c=2
- 版本：仿單正文未见版本行；PDF 元数据 CreationDate 2015-12-27；licence 衛署藥製字第029301號 现行（有效日期 2029/11/28）
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-12 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，与 2026-09-11 下载逐字节相同，zip sha256 见 notes；29,860 条）：记录序号 3663（JSON 数组 1-based），許可證字號 衛署藥製字第029301號，中文品名 "明德" 心壓暢錠100毫克（美托普洛）；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_dd2c70ce-0124-4720-9874-a4be9305cfb9?c=2
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛署藥製字第029301號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛署藥製字第029301號", "註銷狀態": "", "有效日期": "2029/11/28", "發證日期": "1986/11/28", "申請商名稱": "明德製藥股份有限公司", "製造商名稱": "明德製藥股份有限公司"
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_dd2c70ce-0124-4720-9874-a4be9305cfb9?c=2（PDF 全文文本扫描：2026-09-12 以 pypdf 6.15.0（会话临时环境）初筛，2026-09-13 以锁定版 pypdf 6.18.1 复测：2 页，可抽取 2594 字符，pypdf 告警 0 条；标记词 ©/Ⓒ/版權/著作權/Copyright/保密/不得/禁止/授權/商標/®/™；零命中，未发现版权、保密或禁止复用声明）：明德製藥股份有限公司 桃園市楊梅區民富路二段 360 號 Made in Taiwan
- 第三方内容：仿單正文由製造商撰寫（明德製藥股份有限公司），含產品名稱商標；OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌。正文较短（2,595 字符），注意事项以红色字排版。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对四项条件：(1) pdf_url 在 2026-09-12 同日下载的数据集快照中逐字出现（记录 3663）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本层无版权、保密、禁止复用声明，且逐页 Quartz 渲染目视无版权标记——通过；(4) OGDL 署名与不主张商标权——入库时落实。按 2026-09-12 决策口径（MAH 撰写内容在 OGDL 覆盖内）预判 eligible。现行性：许可证未註銷，有效日期 2029/11/28。文本量小，可标注条款有限。 2026-09-13 复测：逐页异常字符扫描零命中。
- 复核备注：无
- 备注：页数：2；PDF 2026-09-12 下载 sha256 2b8ab3b1bfea619d8eba938864e10614313dfa92e036bdba6a8fec2cb5fd2425，508645 字节，HTTP 200 application/pdf；可抽取 2594（pypdf 6.18.1；6.15.0 初筛为 2595） 字符；pypdf 告警 0 条；许可证现行不等于本 PDF 为现行修订版，仿單版本以文内版本行为准；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

### cand-0038：胃所樂腸溶膜衣錠40毫克（Esomen Enteric-Coated Tablets 40mg, esomeprazole）仿單

- 发布方：衛生福利部食品藥物管理署 藥品仿單查詢平台（mcp.fda.gov.tw）；申請商/製造商 健喬信元醫藥生技股份有限公司（健喬廠）；仿單署名 景德製藥股份有限公司
- 落地页：https://mcp.fda.gov.tw/im_detail_1/%E8%A1%9B%E9%83%A8%E8%97%A5%E8%A3%BD%E5%AD%97%E7%AC%AC058102%E8%99%9F
- PDF：https://mcp.fda.gov.tw/insert/pdfcasefile/i_025ea5d5-739b-4d9c-ad03-175c26f3a3fc?c=2
- 版本：仿單正文未见版本行；PDF 元数据 CreationDate 2013-11-08；licence 衛部藥製字第058102號 现行（有效日期 2028/10/18）
- 预判状态：**eligible**；决策：待定
- 许可证据：
  - https://mcp.fda.gov.tw/im（平台页脚（2026-09-09 代理抓取；2026-09-11 主会话 curl 复核一致））：本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。
  - https://data.gov.tw/dataset/9117（数据集元数据（授權方式、主要欄位說明；2026-09-11 主会话复核关键字段一致））：授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結
  - https://data.gov.tw/license（政府資料開放授權條款-第1版 §二(一)、§四(二)（2026-09-11 主会话复核一致））：各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容
  - https://www.fda.gov.tw/TC/opendata.aspx（網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（2026-09-11 主会话 curl 复核一致））：衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || (一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。
  - https://www.fda.gov.tw/TC/copyright.aspx（著作權聲明（2026-09-11 主会话 curl 复核一致））：本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。
  - https://data.fda.gov.tw/data/opendata/export/39/json（数据集快照 2026-09-12 下载（与 PDF 同日；内层 39_5.json sha256 1d27fcc3c5795635b556c7ab3382e6857ec713cf13e600babf99e3f586634378，与 2026-09-11 下载逐字节相同，zip sha256 见 notes；29,860 条）：记录序号 18747（JSON 数组 1-based），許可證字號 衛部藥製字第058102號，中文品名 胃所樂腸溶膜衣錠40毫克；仿單圖檔連結 与本条 pdf_url 逐字相等（机械核对通过））：https://mcp.fda.gov.tw/insert/pdfcasefile/i_025ea5d5-739b-4d9c-ad03-175c26f3a3fc?c=2
  - https://data.fda.gov.tw/data/opendata/export/36/json（TFDA 開放資料「全部藥品許可證資料集」快照 2026-09-12 下载：zip sha256 0b31742f1d86e3c8cefc6f8ccb32e752ec731ba3412d36b830e95f57198f7100，内层 36_5.json sha256 2e00df0bc61e880c090ace4ab8312665ecd96ec71c323aa2ccfab7ec7e28e9f8（成员时间戳 2026-09-10 10:03），72,043 条；許可證字號 衛部藥製字第058102號 的记录字段 註銷狀態/註銷日期/註銷理由/有效日期/發證日期/申請商名稱/製造商名稱）："許可證字號": "衛部藥製字第058102號", "註銷狀態": "", "有效日期": "2028/10/18", "發證日期": "2013/10/18", "申請商名稱": "健喬信元醫藥生技股份有限公司", "製造商名稱": "健喬信元醫藥生技股份有限公司健喬廠"
  - https://mcp.fda.gov.tw/insert/pdfcasefile/i_025ea5d5-739b-4d9c-ad03-175c26f3a3fc?c=2（PDF 全文文本扫描：2026-09-12 以 pypdf 6.15.0（会话临时环境）初筛，2026-09-13 以锁定版 pypdf 6.18.1 复测：4 页，可抽取 14633 字符，pypdf 告警 8 条；标记词 ©/Ⓒ/版權/著作權/Copyright/保密/不得/禁止/授權/商標/®/™；「不得」「禁止」命中均为临床文本，未发现版权、保密或禁止复用声明）：禁止同時併用 esomeprazole 和 nelfinavir
- 第三方内容：仿單署名 景德製藥股份有限公司（現行申請商為健喬信元，商号变更），含產品名稱商標；OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌。抽取文本的粗体标题存在字形重复（如「胃所樂胃所樂…」），正文正常；标注 key_text 时避开标题。脚本变体 zh-Hant。
- 理由：按 ADR-0003 决策 1 机械核对四项条件：(1) pdf_url 在 2026-09-12 同日下载的数据集快照中逐字出现（记录 18747）——通过；(2) 快照哈希/日期/字段已记录——通过；(3) PDF 文本层无版权、保密、禁止复用声明，且逐页 Quartz 渲染目视无版权标记——通过；(4) OGDL 署名与不主张商标权——入库时落实。按 2026-09-12 决策口径（MAH 撰写内容在 OGDL 覆盖内）预判 eligible。现行性：许可证未註銷，有效日期 2028/10/18。与 cand-0036 同一申請商，按 SPEC §3.4 仍是不同 document_key 与 source_hash 的独立文档。 2026-09-13 复测：pypdf 告警 8 条（fontTools 缺失，CFF Type1 字体编码未完整解析）；p2 有 4 个私用区字符 U+F074（符号字体）；标注前需页级质量复核。
- 复核备注：无
- 备注：页数：4；PDF 2026-09-12 下载 sha256 f80b904f4e2f15a59cb78fe1baed5c1c06b8b975d43dc0291217d64c43e43fbb，285282 字节，HTTP 200 application/pdf；可抽取 14633（pypdf 6.18.1；6.15.0 初筛为 14636） 字符；pypdf 告警 8 条；许可证现行不等于本 PDF 为现行修订版，仿單版本以文内版本行为准；粗体标题字形重复抽取；脚本变体 zh-Hant；快照 zip sha256 2b6ae0be3f63c3b176aa3c926af70235247dce9d7ba78cca8c4c20d2755cee36

