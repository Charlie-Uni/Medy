# 探针集 v1 样本草稿：MA 批次（30 条，待决策人逐条确认）

> 每条请判断五件事：问题是否自然且只有这一句能回答；key_text 是否最短且页内唯一（工具已核对唯一性）；span 是否完整条款；切片标签；部门归属。
> 确认方式：在「结论」列填 OK，或直接改写 query / key_text / span / slices；改动的条目我重新计算偏移。

| ID | 文档 | 页 | 切片 | query | key_text | evidence_span | 章节 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pc-0001 | tfda-label-loformin-850mg | 1 | dose_unit, drug_name_zh | 美洛醣一天要吃幾次、每次幾錠？ | 每日服用二次,每次服用一錠 | 通常,每日服用二次,每次服用一錠。 | 用法用量 | |
| pc-0002 | tfda-label-loformin-850mg | 1 | dose_unit, drug_name_zh | 美洛醣每日最高治療劑量是多少 | 每日最高治療劑量速效劑型:3000 mg | Metformin之每日最高治療劑量速效劑型:3000 mg;緩釋劑型: 2000mg (本品為速效劑型)。 | 用法用量 | |
| pc-0003 | tfda-label-loformin-850mg | 1 | negation, drug_name_zh | 超過八十歲的老人家可以開始用美洛醣嗎 | 大於80歲之老年患者不建議開始使用 | 大於80歲之老年患者不建議開始使用 Metformin治療。 | 用法用量 | |
| pc-0004 | tfda-label-loformin-850mg | 2 | time_window, mixed_zh_en | 口服 metformin 之後大約多久達到最高血中濃度 | 約2.5小時就會達到最高血中濃度 | 【藥動學】吸收: 口服metformin hydrochloride錠劑後,約2.5小時就會達到最高血中濃度 (Tmax)。 | 藥動學 | |
| pc-0005 | tfda-label-loformin-850mg | 2 | time_window, drug_name_zh, dose_unit | 美洛醣按建議劑量服用多久後血中濃度會穩定 | 服用後24至48小時內可達穩定血中濃度 | 在建議劑量與劑量療程之下,在服用後24至48小時內可達穩定血中濃度,且該濃度值通常低於1 ug /mL。 | 藥動學 | |
| pc-0006 | tfda-label-loformin-850mg | 2 | protocol_id, dose_unit, mixed_zh_en | 衛部藥製字第058257號是哪一個藥品 | 衛部藥製字第058257號 Code No. 美洛醣膜衣錠850毫克 | 衛部藥製字第058257號 Code No. 美洛醣膜衣錠850毫克 Loformin Film-coated Tablets 850mg (Metformin) | 許可證資訊 | |
| pc-0007 | tfda-label-deurinol-300mg | 3 | dose_unit, drug_name_zh, time_window, negation | 痛風停錠用於成人及青少年抗痛風的初始劑量是多少 | 初始劑量:口服,100mg,一天一次 | 一般成人及青少年劑量:抗痛風劑(Antigout agent)— 初始劑量:口服,100mg,一天一次,在一星期的間隔期間每天增加100mg 直到達到所需要的血清尿酸濃度為止。不得超過每日800mg 之最大建議劑量。 | 用法用量 | |
| pc-0008 | tfda-label-deurinol-300mg | 3 | dose_unit, negation, mixed_zh_en | allopurinol 一般成人的處方限量是多少（每一劑量與每天） | 一般成人處方限量:每一劑量300mg;每天800mg | 一般成人處方限量:每一劑量300mg;每天800mg | 用法用量 | |
| pc-0009 | tfda-label-deurinol-300mg | 2 | negation, mixed_zh_en | 痛風關節炎急性發作的時候可以用 allopurinol 嗎 | 不得使用於痛風性關節炎的急性發作 | Allopurinol沒有抗發炎的效力,它必須不得使用於痛風性關節炎的急性發作,一種抗發炎藥,最好是一種非類固醇類抗發炎劑(NSAI)或者是皮質類固醇(Corticosteroid)〔當可行時,最好是滑膜內注射(Intrasynovial injection)〕必須加以使用,以治療急性發作。 | 適應症 | |
| pc-0010 | tfda-label-deurinol-300mg | 1 | mixed_zh_en | Oxipurinol 的半衰期大約多久 | Oxipurinol,12 至30 小時 | 半衰期:Allopurinol,1 至3 小時;Oxipurinol,12 至30 小時(平均大約15 小時);有腎功能不全的病人可能會大為延長。 | 藥動學 | |
| pc-0011 | tfda-label-deurinol-300mg | 8 | dose_unit, negation, drug_name_zh | 痛風停錠單次劑量的上限是多少 | 單一劑量,都必須不得超過300 mg | 每一個單一劑量,都必須不得超過300 mg。 | 注意事項 | |
| pc-0012 | tfda-label-deurinol-300mg | 10 | protocol_id, negation | 衛署藥製字第 048564 號的藥品須由醫師處方使用嗎 | 本藥須由醫師處方使用 | 本藥須由醫師處方使用衛署藥製字第 048564 號 | 許可證資訊 | |
| pc-0013 | tfda-label-zosaa-50mg | 1 | dose_unit, drug_name_zh, time_window | 穩壓膜衣錠治療高血壓的一般起始劑量是多少 | 起始劑量及維持劑量為每次 50mg,每日一次 | 高血壓:大多數病人的一般起始劑量及維持劑量為每次 50mg,每日一次;在治療後 3~6 週可獲得最大降壓效果;有些病人在劑量增加至每次 100 mg,每日一次後,其療效更佳。 | 用法用量 | |
| pc-0014 | tfda-label-zosaa-50mg | 1 | time_window, drug_name_zh, dose_unit | 穩壓膜衣錠吃多久才會有最大的降壓效果 | 3~6 週可獲得最大降壓效果 | 高血壓:大多數病人的一般起始劑量及維持劑量為每次 50mg,每日一次;在治療後 3~6 週可獲得最大降壓效果;有些病人在劑量增加至每次 100 mg,每日一次後,其療效更佳。 | 用法用量 | |
| pc-0015 | tfda-label-zosaa-50mg | 1 | dose_unit, drug_name_zh | 高血壓且血管內體液缺乏的病人使用穩壓膜衣錠的起始劑量是多少 | 起始劑量需考慮改用每次 25mg | 對血管內體液缺乏(intravascularly volume-depleted)之患者(如以高劑量利尿劑治療者) ,其起始劑量需考慮改用每次 25mg ,每日一次(參見注意事項)。 | 用法用量 | |
| pc-0016 | tfda-label-zosaa-50mg | 1 | negation, drug_name_zh, dose_unit, mixed_zh_en | 糖尿病患者能同時使用穩壓膜衣錠和 aliskiren 嗎 | 禁忌症:合併使用本品及含 aliskiren 成分藥品於糖尿病患 | 1、禁忌症:合併使用本品及含 aliskiren 成分藥品於糖尿病患或腎功能不全患者 (GFR < 60 ml/min/1.73 m 2 )。 | 禁忌症 | |
| pc-0017 | tfda-label-zosaa-50mg | 1 | negation, mixed_zh_en | 糖尿病腎病變患者已使用 ACEI 時，可以再加用 ARB 嗎 | ACEIs 及 ARBs 不應合併使用於糖尿病腎病變患者 | 雙重阻斷腎素-血管昇壓素-醛固酮系統(renin-angiotensin-aldosterone system, RAAS):有證據顯示,合併使用 ACEIs、ARBs 或含 aliskiren 成分藥品會增加低血壓、高鉀血症及腎功能下降(包括急性腎衰竭)之風險,故不建議合併使用 ACEIs、ARBs 或含 alisk… | 注意事項 | |
| pc-0018 | tfda-label-zosaa-50mg | 1 | protocol_id, dose_unit | 衛署藥製字第 047911 號是哪個藥品 | 穩壓膜衣錠 50 毫克 | G-9053 衛署藥製字第 047911 號穩壓膜衣錠 50 毫克 Zosaa F.C. Tablets 50 mg | 許可證資訊 | |
| pc-0019 | tfda-label-cancliol-100mg | 1 | dose_unit, drug_name_zh | 高血壓患者每天用明德心壓暢錠治療用量範圍是多少 | 高血壓:每日投與 100〜200mg | 高血壓:每日投與 100〜200mg,以單一劑量於晨間口服抑或將之分成二次劑量於早、晚服用。某些情況,亦有可能需要酌增劑量或併服其他降血壓藥。 | 用法用量 | |
| pc-0020 | tfda-label-cancliol-100mg | 1 | negation, drug_name_zh | 哪些病人禁止使用明德心壓暢錠 | 房室神經傳導阻斷第二和第三期,非代償性心衰竭,心原性休克,顯著的心搏過緩等症狀者禁用此劑 | 【注意事項】一、禁忌:房室神經傳導阻斷第二和第三期,非代償性心衰竭,心原性休克,顯著的心搏過緩等症狀者禁用此劑。 | 禁忌 | |
| pc-0021 | tfda-label-cancliol-100mg | 1 | time_window, drug_name_zh | 明德心壓暢錠要怎麼停藥，可以突然停嗎 | 需逐漸停用,例如於 7〜10 天 | 二、停用本劑時需逐漸停用,例如於 7〜10 天之期間,因突然停藥會導致急性損害患者身體狀況,尤其是罹患心臟局部缺血者。 | 注意事項 | |
| pc-0022 | tfda-label-cancliol-100mg | 1 | time_window, drug_name_zh, negation | 要開刀麻醉的病人手術前多久停用心壓暢錠 | 麻醉前至少 48 小時即應停止服用 | 三、對於即將進行麻醉開刀的病患,在麻醉前至少 48 小時即應停止服用本劑。 | 注意事項 | |
| pc-0023 | tfda-label-cancliol-100mg | 2 | dose_unit, drug_name_zh, mixed_zh_en, negation | 心壓暢錠過量時，該如何急救 | 靜脈注射1〜2mg Atropine sulfate | 過量中毒時之處裡:本劑服用過量時會導致明顯的低血壓和心搏過緩。初步的急救方法,係靜脈注射1〜2mg Atropine sulfate;倘若還未能達到滿意效果時,在使用 Atropine 後可接著投與升壓劑,例如metaraminol 或 noradrenaline。此外如果任何β-blocket 過量中毒的時候,亦可投… | 過量處理 | |
| pc-0024 | tfda-label-cancliol-100mg | 1 | protocol_id, dose_unit | 衛署藥製字第 029301 號是哪個藥品 | 心壓暢錠 100 毫克 | 衛署藥製字第 029301 號 GMP-G-0462 號 "明德"心壓暢錠 100 毫克(美托普洛) CANCLIOL TABLETS 100mg (Metoprolol) "Meider" | 許可證資訊 | |
| pc-0025 | tfda-label-esomen-40mg | 1 | negation, drug_name_zh | 胃所樂腸溶膜衣錠可以嚼碎或壓碎再吃嗎 | 不可嚼破或壓破本錠劑 | 本錠劑應整粒以液體吞服,不可嚼破或壓破本錠劑。 | 用法用量 | |
| pc-0026 | tfda-label-esomen-40mg | 1 | time_window, drug_name_zh | 胃所樂泡在水裡崩散後要在多久之內喝完 | 立即或在 30 分鐘之內將水連同小藥球喝下 | 同時攪拌直到藥錠崩散,並立即或在 30 分鐘之內將水連同小藥球喝下。 | 用法用量 | |
| pc-0027 | tfda-label-esomen-40mg | 1 | dose_unit, time_window, drug_name_zh, negation | 胃所樂腸溶膜衣錠用於食道未發炎的胃食道逆流症狀治療，劑量和療程是多少 | 食道未發炎之患者 20 mg 每天 1次 | 胃食道逆流性疾病之症狀治療:對食道未發炎之患者 20 mg 每天 1次;若 4週後仍有症狀時,則應進一步檢查患者。一旦症狀獲得緩解後,可以每天 1次 20 mg 之療法來做後續的症狀控制。就成人而言,如需要時,可以給予 20 mg 每天 1次之療法。對於使用非類固醇抗發炎藥 (NSAID) 治療而有誘發胃潰瘍和十二指腸… | 用法用量 | |
| pc-0028 | tfda-label-esomen-40mg | 2 | negation, mixed_zh_en | esomeprazole 可以和 nelfinavir 一起服用嗎 | 禁止同時併用 esomeprazole 和 nelfinavir | 由於omeprazole 與 esomeprazole 的藥效學效應與藥動學性質類似,故不建議同時投予 esomeprazole 和 atazanavir ,禁止同時併用 esomeprazole 和 nelfinavir 。 | 藥物交互作用 | |
| pc-0029 | tfda-label-esomen-40mg | 3 | dose_unit, negation, mixed_zh_en | 嚴重肝功能不良的病人 esomeprazole 最高劑量是多少 | 此類病人的esomeprazole 最高劑量不可超過 20 mg | 嚴重肝功能不良的病人的 esomeprazole 代謝率降低,導致血漿濃度時間曲線下的面積加倍,因此此類病人的esomeprazole 最高劑量不可超過 20 mg 。 | 特殊族群 | |
| pc-0030 | tfda-label-esomen-40mg | 4 | protocol_id | 衛部藥製字第 058102 號藥品的製造廠址在哪裡 | 廠址:新北市土城區中央路二段 104 號 | 衛部藥製字第 058102 號 G- 12115 公司地址:台北市中山北路二段 113 號 8 樓廠址:新北市土城區中央路二段 104 號 | 許可證資訊 | |

切片计数：{'dose_unit': 17, 'drug_name_zh': 18, 'negation': 15, 'time_window': 9, 'mixed_zh_en': 10, 'protocol_id': 5}；部门：{'MA': 30}；语言：{'zh': 20, 'mixed': 10}
