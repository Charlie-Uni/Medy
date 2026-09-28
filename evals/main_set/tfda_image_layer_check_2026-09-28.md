# TFDA 仿單图像层核查（ADR-0003 决策 1 条件 3）——候选清单 v1.3 签字批

日期：2026-09-28。对象：v1.3 签字 `eligible` 且尚未入库的 67 份 TFDA 仿單（cand-0264～0332 中除 cand-0293、0298 两份 needs_review 外的全部）。方法与 2026-09-21 相同：pypdfium2 以约 65 dpi 渲染每一页，6 页拼成一张检视图，逐张人工目视（Claude Fable 5.1 查看图像），只判断版权 / 保密 / 禁止复用标记；疑点处用 Quartz 以 150～400 dpi 单独渲染核对。覆盖：60 份、264 页、86 张检视图全部看过（7 份因抽取乱码在目视前已排除，见下）。分辨率限制同前：极小的 © 可能不可辨，正文级别的声明可辨。

## 结论

- **59 份通过**：只见廠商標誌、產品商標（®）、GMP / PIC/S 标志、回收标志、条码；未见 ©、版權、著作權、保密或禁止复用声明。
- **1 份排除（产品身份不符）**：cand-0325 的 PDF 内容是「培他旺糖衣錠 Peitaon S.C. TAB」（維他命 B1 複合劑，瑞士藥廠），与候选标题「硝弗侖陶因錠 NITROFURANTOIN TABLETS」不符。PDF 内印的許可證字號 003893 与資料集 39 该字号记录一致，即资料集把该字号的仿單連結指向了另一产品。图像层本身无版权标记，但产品身份不可信，本轮不入库；已在候选清单外单独记录，待决策人决定是否向 TFDA 反馈或改选同成分他牌。
- **7 份未目视即排除（抽取乱码）**：cand-0275、0282、0284、0307、0316、0317、0320 的页文本存在大面积字形映射错误（按 2026-09-13 对欣服寧的口径，逐页 >2% 的 IPA / 修饰符号区字符），按 SPEC §4 不能作为 gold 来源，本轮不入库；许可预判不变。其中 cand-0275 与已排除的 cand-0036 是同一 PDF（sha 9f1538…）。

## 两处需要说明的目视发现（均通过）

| 候选 | 发现 | 判断 |
| --- | --- | --- |
| cand-0301 痛搏適膠囊（celecoxib） | 末列印有製造廠 Pfizer Pharmaceuticals LLC（Vega Baja, Puerto Rico）与版本 MOH 20170731-1；400 dpi 渲染确认无 © 或 Pfizer 版权声明 | 通过：製造廠信息不是权利声明 |
| cand-0321 默菌殺點眼液（moxifloxacin） | 印刷稿样式（Front / Back 110 mm、Size 标注、PHARMACODE 读取方向） | 通过：印刷规格标注，无权利声明 |

## 逐份结果（60 份）

| 候选 | 标题 | 页数 | 结论 |
| --- | --- | ---: | --- |
| cand-0264 | 易吉妥錠10毫克（Ezzicad, ezetimibe） | 3 | 通过 |
| cand-0265 | 愛妥糖錠15公絲（Actos, pioglitazone） | 2 | 通过 |
| cand-0266 | 克糖寧錠80毫克（Glicalin, gliclazide） | 1 | 通过 |
| cand-0267 | 優理醣錠2毫克（Repade, repaglinide） | 1 | 通过 |
| cand-0268 | 泰穩壓錠40毫克（Tesaa, telmisartan） | 2 | 通过 |
| cand-0269 | 壓落敏錠25公絲（Carvedil, carvedilol） | 2 | 通过 |
| cand-0270 | 阿利平膜衣錠50毫克（Anlipin, atenolol） | 1 | 通过 |
| cand-0271 | 博能錠（Pranolol, propranolol） | 2 | 通过 |
| cand-0272 | 使能通錠50毫克（Slatone, spironolactone） | 1 | 通过 |
| cand-0273 | 優尿壓膠囊2.5公絲（Utrilix, indapamide） | 1 | 通过 |
| cand-0274 | 富必欣持續性藥效錠4毫克（Danxosin, doxazosin） | 2 | 通过 |
| cand-0276 | 心韻錠（Tempo, amiodarone） | 2 | 通过 |
| cand-0277 | 歐舒心注射劑0.01%（isosorbide） | 1 | 通过 |
| cand-0278 | 恩舒注射劑0.4毫克/毫升（nitroglycerin） | 2 | 通过 |
| cand-0279 | 潰滿定膜衣錠20公絲（Quimadine, famotidine） | 1 | 通过 |
| cand-0280 | 莫痙錠10毫克（Motin, domperidone） | 2 | 通过 |
| cand-0281 | 永胃健糖衣錠10毫克（Dringen, metoclopramide） | 1 | 通过 |
| cand-0283 | 鎮拉定膠囊（Genlatin, loperamide） | 1 | 通过 |
| cand-0285 | 利肝膽膠囊300毫克（Legan, ursodeoxycholic acid） | 1 | 通过 |
| cand-0286 | 樂寶寧膜衣錠50毫克（Lustraline, sertraline） | 3 | 通过 |
| cand-0287 | 伏鬱微粒膠囊10公絲（Flux, fluoxetine） | 2 | 通过 |
| cand-0288 | 康緒平錠37.5毫克（Calmdown, venlafaxine） | 20 | 通过 |
| cand-0289 | 憂必舒膠囊30毫克（Ulitine, duloxetine） | 26 | 通过 |
| cand-0290 | 邁慮煩膜衣錠15毫克（Minivane, mirtazapine） | 7 | 通过 |
| cand-0291 | 百適存持續性藥效錠300毫克（Bestrim XL, bupropion） | 4 | 通过 |
| cand-0292 | 杏緩妥錠50公絲（Cirzodone, trazodone） | 1 | 通过 |
| cand-0294 | 羅亞達口溶錠10毫克（Arizole, aripiprazole） | 4 | 通过 |
| cand-0295 | 鋰康膠囊300毫克（Lithcan, lithium） | 3 | 通过 |
| cand-0296 | 樂眠錠1毫克（Larpam, lorazepam） | 3 | 通过 |
| cand-0297 | 心氣寧錠（Sindilium, diazepam） | 2 | 通过 |
| cand-0299 | 普疼立寧膠囊75毫克（pregabalin） | 7 | 通过 |
| cand-0300 | 癲可停膠囊100毫克（Epileptin, phenytoin） | 3 | 通过 |
| cand-0301 | 痛搏適膠囊400毫克（Seconbrex, celecoxib） | 2 | 通过（見上表） |
| cand-0302 | 馬蓋先膜衣錠400公絲（Macsafe, ibuprofen） | 2 | 通过 |
| cand-0303 | 拿痛仙錠250毫克（Natoxen, naproxen） | 2 | 通过 |
| cand-0304 | 益妥瑞膜衣錠120毫克（Terexib, etoricoxib） | 2 | 通过 |
| cand-0305 | 蒙地卡膜衣錠10毫克（Monteka, montelukast） | 4 | 通过 |
| cand-0306 | 息舒寧液5.34毫克/毫升（Theolin, theophylline） | 2 | 通过 |
| cand-0308 | 暢適得膜衣錠5毫克（Fencare, solifenacin） | 8 | 通过 |
| cand-0309 | 虎讚膜衣錠10毫克（Zan, tadalafil） | 2 | 通过 |
| cand-0310 | 士力挺膜衣錠50毫克（Sliting, sildenafil） | 11 | 通过 |
| cand-0311 | 僕樂彼錠50毫克（Polupi, propylthiouracil） | 2 | 通过 |
| cand-0312 | 使汝健硬膠囊（prednisolone） | 1 | 通过 |
| cand-0313 | 得佳錠0.5毫克（Deca, dexamethasone） | 1 | 通过 |
| cand-0314 | 杏節挺錠（PlusDmax, alendronate） | 2 | 通过 |
| cand-0315 | 克風迅錠0.5毫克（Cofoncin, colchicine） | 1 | 通过 |
| cand-0318 | 耳循膜衣錠8毫克（Ecycle, betahistine） | 1 | 通过 |
| cand-0319 | 優樂欣注射劑（Uroxime, cefuroxime） | 2 | 通过 |
| cand-0321 | 默菌殺點眼液（Micromox, moxifloxacin） | 1 | 通过（見上表） |
| cand-0322 | 獨拉膠囊（Bistor, doxycycline） | 1 | 通过 |
| cand-0323 | 黴祐膠囊50公絲（Azol-flucon, fluconazole） | 1 | 通过 |
| cand-0324 | 敵疱治錠200公絲（Acylete, acyclovir） | 1 | 通过 |
| cand-0325 | 硝弗侖陶因錠100公絲（NITROFURANTOIN） | 1 | **排除**：PDF 实为培他旺糖衣錠（Peitaon），产品身份不符 |
| cand-0326 | 順治炎錠（Sinzuin, sulfamethoxazole/trimethoprim） | 1 | 通过 |
| cand-0327 | 瑞保清膜衣錠0.5毫克（Hepato-ease, entecavir） | 17 | 通过 |
| cand-0328 | 惠肝怡錠300毫克（Hucanon, tenofovir DF） | 36 | 通过 |
| cand-0329 | 輔適納膜衣錠2.5毫克（Letramase, letrozole） | 2 | 通过 |
| cand-0330 | 消汝妥1毫克（Arbreast, anastrozole） | 2 | 通过 |
| cand-0331 | 癌可泰膜衣錠50毫克（Bicalutamide-Acepharm） | 2 | 通过 |
| cand-0332 | 立悠克膠囊100毫克（Leukure, imatinib） | 11 | 通过 |

## 文本层辅助核对

- 60 份的页文本另做标记词扫描（©/Ⓒ/版權/著作權/Copyright/All rights reserved/保密/Confidential/商標所有/未經/不得轉載 等）：命中全部是临床正文中的「未經治療」「未經系統性評估」一类用语与 cand-0286 量表缩写中的「(c)」，无权利声明。
- 60 份的英文品名均能在各自页文本中找到；許可證字號只在部分仿單的文本层出现（8 份文本层不含字号，为版面图像），不影响判断。
