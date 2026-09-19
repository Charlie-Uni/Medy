# 探针集 v1 样本草稿：MA 批次（30 条，待决策人逐条确认）

> 每条请判断五件事：问题是否自然且只有这一句能回答；key_text 是否最短且页内唯一（工具已核对唯一性）；span 是否完整条款；切片标签；部门归属。
> 确认方式：在「结论」列填 OK，或直接改写 query / key_text / span / slices；改动的条目我重新计算偏移。

| ID | 文档 | 页 | 切片 | query | key_text | evidence_span | 章节 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pc-0001 | tfda-label-loformin-850mg | 1 | time_window, drug_name_zh | 美洛醣一天要吃幾次、每次幾錠？ | 每日服用二次,每次服用一錠 | 通常,每日服用二次,每次服用一錠。 | 用法用量 |OK|
| pc-0002 | tfda-label-loformin-850mg | 1 | dose_unit, mixed_zh_en | 美洛醣每日最高治療劑量是多少 | 每日最高治療劑量速效劑型:3000 mg | Metformin之每日最高治療劑量速效劑型:3000 mg;緩釋劑型: 2000mg (本品為速效劑型)。 | 用法用量 | 修改query|
| pc-0003 | tfda-label-loformin-850mg | 1 | negation, drug_name_zh | 八十歲以上的老人家可以開始用美洛醣嗎 | 不建議開始使用 | 大於80歲之老年患者不建議開始使用 Metformin治療。 | 用法用量 |修改key_text|
| pc-0004 | tfda-label-loformin-850mg | 2 | time_window, mixed_zh_en | 口服 metformin 之後大約多久達到最高血中濃度 | 約2.5小時就會達到最高血中濃度 | 【藥動學】吸收: 口服metformin hydrochloride錠劑後,約2.5小時就會達到最高血中濃度 (Tmax)。 | 藥動學 |OK|
| pc-0005 | tfda-label-loformin-850mg | 2 | time_window, drug_name_zh | 美洛醣按建議劑量服用多久後血中濃度會穩定 | 在服用後24至48小時內可達穩定血中濃度 | 在建議劑量與劑量療程之下,在服用後24至48小時內可達穩定血中濃度,且該濃度值通常低於1 ug /mL。 | 藥動學 |OK|
| pc-0006 | tfda-label-loformin-850mg | 2 | protocol_id, drug_name_zh | 美洛醣膜衣錠850毫克的許可證字號是多少 | 衛部藥製字第058257號 | "育生"美洛醣膜衣錠850毫克 Loformin Film-coated Tablets 850mg(Metformin) 衛部藥製字第058257號 本藥須由醫師處方使用| 許可證資訊 |改写key_text |

| pc-0007 | tfda-label-deurinol-300mg | 3 | dose_unit, drug_name_zh | 痛風停錠於成人及青少年的初始劑量是多少 | 抗痛風劑初始劑量:100mg,一天一次；贅瘤疾病治療：每天 600mg 至 800mg；抗尿酸結石：100mg 至 200mg，每天一次 | 一般成人及青少年劑量：
抗痛風劑（Antigout agent）—
 初始劑量：口服，100mg，一天一次，在一星期的間隔期間每天增加 100mg 直到達到所需要的血清尿酸濃度為止。不
得超過每日 800mg 之最大建議劑量。
維持劑量：口服，100 至 200mg，一天二至三次，或 300mg 單一劑量，一天一次。在輕度痛風者的一般維持劑量為每
天 200 至 300mg。在適度嚴重沙石痛風（Tophaceaus gout）者的一般維持劑量為每天 400 至 600mg。
贅瘤疾病治療（Neoplastic disease therapy）—
初始劑量：口服，在化學治療或放射治療開始之前的 12 小時到 3 天（最好是 2 至 3 天），每天 600mg 至 800mg。
維持劑量：劑量必須要依據在 Allopurinol 治療開始後的 48 小時及其後的定期時間所執行之血清尿酸測定為基礎。
抗尿酸結石〔Antiurolithic（Uric acid caliculi）〕—
口服，100mg 至 200mg，每天一次。
注意—由於 Oxipurine 主要是經由腎臟排泄，所以在有腎衰竭的病人，可能會發生蓄積。在接受透析的病人，可能需
要使用一般治療劑量的 Allopurinol；不過，在未接受透析的病人則建議依下表所列的劑量減低之：肌胺酸酐清除率
（Creatinine clearance）mL/min
劑量
10 至 20 每日 200mg
3 至 10 每日不超過 100mg
＜3 100mg 超過 24 小時間隔，可能是必須的。
有些腎功能不全的病人，可能需要甚至更低劑量，或是更長的劑量間的間隔時間。某些情況下，300mg 每週兩次
或更少，可能就足夠。
一般成人處方限量：每一劑量 300mg；每天 800mg | 用法用量 | 修改key_text,evidence_span|
| pc-0008 | tfda-label-deurinol-300mg | 3 | negation, dose_unit, mixed_zh_en | allopurinol一般成人每日劑量最多多少 | 一般成人處方不能超過800mg | 一般成人處方限量：每一劑量 300mg；每天 800mg | 用法用量 |修改query，key_text，evidence_span|
| pc-0009 | tfda-label-deurinol-300mg | 2 | negation, mixed_zh_en | 痛風關節炎急性發作的時候可以用 allopurinol 嗎 | 不可以 | Allopurinol沒有抗發炎的效力,它必須不得使用於痛風性關節炎的急性發作,一種抗發炎藥,最好是一種非類固醇類抗發炎劑(NSAI)或者是皮質類固醇(Corticosteroid)〔當可行時,最好是滑膜內注射(Intrasynovial injection)〕必須加以使用,以治療急性發作。 | 適應症 | 修改key_text|
| pc-0010 | tfda-label-deurinol-300mg | 1 | time_window, mixed_zh_en | Oxipurinol 的半衰期大約多久 | Oxipurinol,12 至30 小時 | 半衰期:Allopurinol,1 至3 小時;Oxipurinol,12 至30 小時(平均大約15 小時);有腎功能不全的病人可能會大為延長。 | 藥動學 | OK|
| pc-0011 | tfda-label-deurinol-300mg | 8 | dose_unit, negation, drug_name_zh | 痛風停錠單次劑量的上限是多少 | 單一劑量不得超過300 mg | 每一個單一劑量,都必須不得超過300 mg。 | 注意事項 | 修改query，key_text|

| pc-0012 | tfda-label-deurinol-300mg | 10 | protocol_id, drug_name_zh | 痛風停錠300毫克的許可證字號 | 衛署藥製字第 048564 號 | 本藥須由醫師處方使用衛署藥製字第 048564 號 G-9485 10 | 許可證資訊 | OK|

| pc-0013 | tfda-label-zosaa-50mg | 1 | dose_unit, drug_name_zh | 穩壓膜衣錠治療高血壓的一般起始劑量是多少 | 一般起始劑量及維持劑量為每次 50mg,每日一次 | 高血壓:大多數病人的一般起始劑量及維持劑量為每次 50mg,每日一次;在治療後 3~6 週可獲得最大降壓效果;有些病人在劑量增加至每次 100 mg,每日一次後,其療效更佳。 | 用法用量 |修改query |

| pc-0014 | tfda-label-zosaa-50mg | 1 | time_window, drug_name_zh | 穩壓膜衣錠吃多久才會有最大的降壓效果 | 治療後 3~6 週可獲得最大降壓效果 | 高血壓:大多數病人的一般起始劑量及維持劑量為每次 50mg,每日一次;在治療後 3~6 週可獲得最大降壓效果;有些病人在劑量增加至每次 100 mg,每日一次後,其療效更佳。 | 用法用量 | 修改query|

| pc-0015 | tfda-label-zosaa-50mg | 1 | dose_unit, mixed_zh_en | 血管內體液缺乏的病人使用穩壓膜衣錠的起始劑量是多少 | 起始劑量每次 25mg | 對血管內體液缺乏(intravascularly volume-depleted)之患者(如以高劑量利尿劑治療者) ,其起始劑量需考慮改用每次 25mg ,每日一次(參見注意事項)。 | 用法用量 | 修改query，key_text|

| pc-0016 | tfda-label-zosaa-50mg | 1 | negation, mixed_zh_en | 糖尿病患者能同時使用穩壓膜衣錠和 aliskiren嗎 | 不可以 | １、禁忌症： 
合併使用本品及含 aliskiren 成分藥品於糖尿病患或腎功能不全患者 (GFR < 60 
ml/min/1.73 m2)。 ２、警語及注意事項： 雙重阻斷腎素－血管昇壓素－醛固酮系統（renin-angiotensin-aldosterone system, RAAS）：有證據顯示，合併使用 ACEIs、ARBs 或含 aliskiren 成分藥品會增加低血壓、高鉀血症及腎功能下降（包括急性腎衰竭）之風險，故不建議合併使用 ACEIs、ARBs或含 aliskiren 成分藥品來雙重阻斷 RAAS，若確有必要使用雙重阻斷治療，應密切監測患者之腎+A12 功能、電解質及血壓。ACEIs 及 ARBs 不應合併使用於糖尿病腎病變患者。 | 禁忌症 |修改query，key_text,evidence_span |

| pc-0017 | tfda-label-zosaa-50mg | 1 | negation, mixed_zh_en | 糖尿病腎病變患者能同時使用 ACEI、ARB或含 aliskiren 成分藥品嗎 | 雙重阻斷腎素－血管昇壓素－醛固酮系統（renin-angiotensin-aldosterone system, RAAS）：有證據顯示，合併使用 ACEIs、ARBs 或含 aliskiren 成分藥品會增加低血壓、高鉀血症及腎功能下降（包括急性腎衰竭）之風險，故不建議合併使用 ACEIs、ARBs或含 aliskiren 成分藥品來雙重阻斷 RAAS，若確有必要使用雙重阻斷治療，應密切監測患者之腎+A12 功能、電解質及血壓。ACEIs 及 ARBs 不應合併使用於糖尿病腎病變患者 | 注意事項 | 修改query，key_text,evidence_span|

| pc-0018 | tfda-label-zosaa-50mg | 1 | protocol_id, drug_name_zh | 穩壓膜衣錠50毫克的許可證字號是多少 | 衛署藥製字第 047911 號 | G-9053 衛署藥製字第 047911 號穩壓膜衣錠 50 毫克 Zosaa F.C. | 許可證資訊 |修改query |

| pc-0019 | tfda-label-cancliol-100mg | 1 | dose_unit, drug_name_zh | 高血壓患者每天用明德心壓暢錠治療用量範圍是多少 | 每日投與 100〜200mg，以單一劑量於晨間口服抑或將之分成二次劑量於早、晚服用| 高血壓:每日投與 100〜200mg,以單一劑量於晨間口服抑或將之分成二次劑量於早、晚服用。 | 用法用量 | 修改query，key_text|

| pc-0020 | tfda-label-cancliol-100mg | 1 | negation, drug_name_zh | 哪些病人禁止使用明德心壓暢錠 | 房室神經傳導阻斷第二和第三期，非代償性心衰竭，心原性休克，顯著的心搏過緩等症狀者禁用此劑 | 【注意事項】一、禁忌:房室神經傳導阻斷第二和第三期,非代償性心衰竭,心原性休克,顯著的心搏過緩等症狀者禁用此劑。 | 禁忌 |修改query，key_text |

| pc-0021 | tfda-label-cancliol-100mg | 1 | time_window, drug_name_zh | 停用明德心壓暢錠需要注意什麼 | 停用本劑時需逐漸停用，例如於 7〜10 天之期間| 二、停用本劑時需逐漸停用,例如於 7〜10 天之期間,因突然停藥會導致急性損害患者身體狀況,尤其是罹患心臟局部缺血者。| 注意事項 | 修改query，key_text|

| pc-0022 | tfda-label-cancliol-100mg | 1 | time_window, drug_name_zh | 要開刀麻醉的病人手術前多久停用心壓暢錠 | 麻醉前至少 48 小時即應停止服用本劑 | 三、對於即將進行麻醉開刀的病患,在麻醉前至少 48 小時即應停止服用本劑。 | 注意事項 | 修改query|

| pc-0023 | tfda-label-cancliol-100mg | 2 | dose_unit, mixed_zh_en | 心壓暢錠過量時，該如何急救 | 係靜脈注射１〜２mg Atropine sulfate；倘若還未能達到滿意效果時，在使用 Atropine 後可接著投與升壓劑，例如 metaraminol 或 noradrenaline。此外如果任何β-blocket 過量中毒的時候，亦可投與一次劑量１〜５(１０)mg 的 glucagon 施救。| 過量中毒時之處裡： 本劑服用過量時會導致明顯的低血壓和心搏過緩。初步的急救方法，係靜脈注射１〜２mgAtropine sulfate；倘若還未能達到滿意效果時，在使用 A tropine 後可接著投與升壓劑，例如 metaraminol 或 noradrenaline。此外如果任何β-blocket 過量中毒的時候，亦可投與一次劑量１〜５(１０)mg 的 glucagon 施救 | 修改query，key_text,evidence_text|

| pc-0024 | tfda-label-cancliol-100mg | 1 | protocol_id, drug_name_zh | 心壓暢錠100毫克的許可證字號 | 衛署藥製字第 029301 號 | 衛署藥製字第 029301 號 GMP-G-0462 號 "明德"心壓暢錠 100 毫克(美托普洛) CANCLIOL TABLETS 100mg (Metoprolol) "Meider"  | 許可證資訊 | 修改evidence_text|

| pc-0025 | tfda-label-esomen-40mg | 1 | negation, drug_name_zh | 胃所樂腸溶膜衣錠可以嚼碎或壓碎再吃嗎 | 不可以，本錠劑應整粒以液體吞服，不可嚼破或壓破本錠劑| 
本錠劑應整粒以液體吞服，不可嚼破或壓破本錠劑。 
對於有吞嚥困難的病人，可將藥錠置入半杯非碳酸類的水中，且
不可使用他種液體，因為藥錠的腸衣膜可能因此溶解。同時攪拌
直到藥錠崩散，並立即或在 30 分鐘之內將水連同小藥球喝下。
再將半杯水加入杯中沖洗並喝下，小藥球不可咬碎或壓碎。本品
不適用於胃管給藥。 | 用法用量 | 修改query，key_text，evidence_text|

| pc-0026 | tfda-label-esomen-40mg | 1 | time_window, drug_name_zh | 胃所樂泡在水裡崩散後要在多久之內喝完 | 在 30 分鐘之內| 同時攪拌直到藥錠崩散,並立即或在 30 分鐘之內將水連同小藥球喝下。| 用法用量 | query|

| pc-0027 | tfda-label-esomen-40mg | 1 | dose_unit, time_window, mixed_zh_en |胃所樂腸溶膜衣錠治療糜爛性逆流性食道炎的服用劑量和療程 | 食道未發炎之患者 20 mg 每
天 1 次；若 4 週後仍有症狀時，則應進一步檢查患者。一旦症狀
獲得緩解後，可以每天 1 次 20 mg 之療法來做後續的症狀控制。 | 胃食道逆流性疾病之症狀治療：對食道未發炎之患者 20 mg 每天 1 次；若 4 週後仍有症狀時，則應進一步檢查患者。一旦症狀獲得緩解後，可以每天 1 次 20 mg 之療法來做後續的症狀控制。就成人而言，如需要時，可以給予 20 mg 每天 1 次之療法。對於使用非類固醇抗發炎藥(NSAID)治療而有誘發胃潰瘍和十二指
腸潰瘍危險之病患，不建議以有需要時才服藥的方式作為後續的
症狀控制。 | 用法用量 |query,key_context,evidence_text |

| pc-0028 | tfda-label-esomen-40mg | 2 | negation, mixed_zh_en | esomeprazole 可以和 nelfinavir 一起服用嗎 | 不可以 | 由於omeprazole 與 esomeprazole 的藥效學效應與藥動學性質類似,故不建議同時投予 esomeprazole 和 atazanavir ,禁止同時併用 esomeprazole 和 nelfinavir 。 | 藥物交互作用 | key_text|

| pc-0029 | tfda-label-esomen-40mg | 3 | dose_unit, negation, mixed_zh_en | 嚴重肝功能不良的病人 esomeprazole 每日最高可以用多少 | 最高劑量不可超過 20 mg | 嚴重肝功能不良的病人的 esomeprazole 代謝率降低,導致血漿濃度時間曲線下的面積加倍,因此此類病人的esomeprazole 最高劑量不可超過 20 mg 。 | 特殊族群 |ok|

| pc-0030 | tfda-label-esomen-40mg | 4 | protocol_id, drug_name_zh | 胃所樂腸溶膜衣錠40毫克的許可證字號 | 衛部藥製字第 058102 號 | 衛部藥製字第 058102 號 G- 12115 公司地址:台北市中山北路二段 113 號 8 樓廠址:新北市土城區中央路二段 104 號 | 許可證資訊 | ok|

切片计数：{'time_window': 9, 'drug_name_zh': 18, 'dose_unit': 10, 'mixed_zh_en': 12, 'negation': 10, 'protocol_id': 5}；部门：{'MA': 30}；语言：{'zh': 18, 'mixed': 12}
