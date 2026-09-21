# MA 批次逐条审校与引用自审记录

日期：2026-09-21  |  状态：main-v1-provisional  |  审校类型：AI 内容审校＋同一审校者反向自审

**第二人工复核未完成。annotator-01 的人工确认亦未由本次 AI 审校代签。** 独立 LLM 复核尚未在本次执行。

## 1. 本轮结果与交付使用

| 项目 | 结果 |
| --- | --- |
| 输入样本 | 83 |
| 原样建议接受 | 16 |
| 修改后建议接受 | 64 |
| 建议删除当前草稿 | 3：ms-0027、ms-0028、ms-0029 |
| 建议保留 | 80 |
| 源 PDF / 引用物理页 | 24 份 / 46 页（去重） |
| 保留样本涉及 PDF / 物理页 | 23 份 / 44 页 |
| 部门 | 83 条均归 MA；未改为 PV 或 CO |
| 本地重开 PDF 后的锚点检查 | 80/80 保留样本：key 及 span 各定位一次、key 被 span 包含 |
| 规范 norm-v1 偏移 / 唯一性 | 未执行；不能以本地检查替代 |
| 源 PDF 和原始表 | 未修改 |

配套 samples_draft_MA.reviewed.md 可作为人工确认的直接编辑稿。结论 OK 表示 AI 建议接受该行当前值；对原稿的实际修改类别看本报告和 JSON 的 decision。DROP 行保留原稿以便追踪，但不得进入有答案或无答案冻结集。

| 字段 | 修改条数（可重叠） |
| --- | --- |
| key_text | 33 |
| slices | 48 |
| query | 24 |
| evidence_span | 11 |
| section | 2 |

64 条修改中，17 条仅修改切片；其余涉及问题、锚点、完整条款或章节。不能将“64 条修改”解释成64个医学事实错误。

## 2. 需要优先关注的裁决

**乱码不是无答案。** ms-0027–0029 的 Glimaryl PDF 页面能读出正常中文，但问题混有简体，key/span 是字体编码乱码，ms-0027 还存在残缺。当前草稿建议 DROP；修复页文本、重起草繁体问题并重新锚定后可再送审，不应转成 no_answer，也不应只删除告警标签。对应源文件 b1756268da31c9205cea8766181345921bdbec9c1930137428c79c5c3d8729f7.pdf，物理第1、2页。

**多要点问题必须有充分的关键证据。** ms-0020、0034 同时覆盖初始量与上限；0049 覆盖50mg起始与可增至100mg；0053 补足ACE抑制剂相关血管神经性水肿病史；0061 恢复全部QT延长药物类别及示例；0079 覆盖注射剂量和后续口服时间；0080 覆盖起始上限和追加间隔。未通过缩窄问题来遮蔽遗漏。

**三个截断 span 已处理。** ms-0022 收缩为回答起始剂量所需的首个完整独立句；ms-0039 补出“除非基于安全考量需更快减量”的例外；ms-0061 补到药物清单最后一项 Methadone 及句末。新表中保留样本不再有 Markdown 截断省略号。

**三条脆弱的“唯一锚点”已修改。** ms-0023 同页糜烂性食道炎和预防再出血均出现40mg每日一次、4周；新 key 纳入适应症。ms-0067、0075 的CABG后14天禁用在同页警示及禁忌重复；分别保留首页第2项和禁忌第7项的原编号，并限定问题的栏目。这里检查的是消除排版差异后的重复，不声称已复跑起草者的 norm-v1。

**逐字唯一不等于语义唯一。** ms-0008、0010、0011、0041、0055、0060 的问题明确相关人群、栏目或章节；尤其0011和0060存在同文档等义复述，不能只因为 key 逐字只出现一次就忽略另一回答条款。

## 3. 原工具告警裁决

| 样本 | 原告警 | 裁决 |
| --- | --- | --- |
| ms-0027 | dose_unit: no numeral+unit/frequency pattern in span | DROP；先修复乱码 |
| ms-0028 | negation: no negation/limitation word in span | DROP；先修复乱码 |
| ms-0029 | dose_unit: no numeral+unit/frequency pattern in span | DROP；先修复乱码 |
| ms-0038 | negation: no negation/limitation word in span | 保留 negation：不要 / 不适合 为真实否定，原正则漏检 |
| ms-0046 | negation: no negation/limitation word in span | 删除 negation：肯定式停药指令 |
| ms-0062 | negation: no negation/limitation word in span | 保留 negation：不要 / 不适合 为真实否定，原正则漏检 |
| ms-0064 | negation: no negation/limitation word in span | 保留 negation：不要 / 不适合 为真实否定，原正则漏检 |
| ms-0065 | negation: no negation/limitation word in span | 删除 negation：肯定式停药指令 |

## 4. 切片操作口径与统计

完整正式 SPEC.md 未取得，以下口径明确列出供统一确认，不作为已经验证 spec-m1 的声明。

| 切片 | 本轮口径 |
| --- | --- |
| drug_name_zh | query或key实际含中文药品名称；不仅因文档标题为中文而增加。 |
| mixed_zh_en | query或key实际中英混排，英文药名/医学术语算；仅拉丁剂量单位或仅span附带英文不自动算。 |
| dose_unit | 药物数量、量化调量比例或给药频次；年龄/GFR/保存温度不据此自动算。 |
| time_window | 问题或关键证据实际涉及疗程、停药窗、观察时间等；纯给药频次主要归dose_unit。 |
| negation | 按完整证据判有意义的否定、禁用、不建议、排除/例外条件；正向“应停药”不单独算。不要/不适合应识别。 |

例如：ms-0032 的GFR是肾功能阈值，不是药物剂量，删除dose_unit；ms-0048–0051只含英文商品名Losacar，删除drug_name_zh。服药频次与监测频次不混同。

| 切片 | 原稿83条 | 保留80条 |
| --- | --- | --- |
| dose_unit | 37 | 34 |
| drug_name_zh | 40 | 72 |
| mixed_zh_en | 65 | 65 |
| negation | 42 | 44 |
| time_window | 18 | 20 |

上述只是MA批次统计。全体631条、九个切片下限、每文档非派生≤8、部门/语言/孪生数量均未重新核验。删除和标签修改后，应以实际数据重跑所有主评测集门槛，不沿用起草总览数字。

## 5. 引用反向自审与剩余边界

完成编辑后重新打开24个实际PDF，重算SHA-256，检查文件名哈希、标题/商品/剂型/规格、83条指定物理页，再检查80条最终key和span。核查了每条证据的页面图像或对应裁切，另查看24份首页身份区域；跨栏与一物理页含两印刷页时使用实际物理页，未用印刷页号替代。

本地字符比较仅用于排版稳健性辅助检查：NFKC、空白折叠及明示的印刷标点统一；没有删除药品名、条件、数值或重排句子。其结果不等于 norm-v1 的逐字字符串和字符偏移验证。

PDF最新版本范围只限用户已提供、可确认属于同一文档的版本。该批映射未切换到另一PDF；哈希相同的双路径保留，已有 /sources/ 副本时优先登记该逻辑路径，只有 staging 的继续登记 /sources_staging/，不虚构迁移。没有明确日期的仿单版本/生效日期留空，不将抓取时间、打印码或上传顺序当成修订时间；本轮未核验全球现行标签。

没有取得候选JSON/完整JSON、项目norm-v1页文本、document_key manifest、正式SPEC和apply_sheet_edits.py，故未执行数据库写回、偏移重算、父子孪生联动或冻结。完整PDF及本表的条款可直接核对，但不能代替这些执行检查。

**需要项目维护的原文质量问题：** ms-0022 PDF文字层重复“起始”，肉眼页面只有一次；本表key改为连续单次“起始剂量”子串，span保留源文字层，不伪造清洗完成。下列仅为视觉转写，不是可直接覆盖norm-v1的gold：

> 建議起始劑量為服用Esomeprazole 40mg每日2次，然後再依個別情況調整劑量，並視臨床表徵決定是否需繼續治療。

ms-0051 的“今aliskiren”和 ms-0052 的“分依次”照录原文，未擅自修改为推测正确的字。标签医学内容的原文审校通过，不表示其中每项建议已经按现行医学实践重新认证。

## 6. 全部83条简表

| ID | 裁决 | 改动字段 | PDF前12位 / 物理页 | 核心理由 |
| --- | --- | --- | --- | --- |
| ms-0001 | OK | 无 | 35ae3bb3cb14 / p.1 | 最高建议日剂量的对象、数值和单位均保留；完整独立句与所问一致。 |
| ms-0002 | REVISE | key_text,slices | 35ae3bb3cb14 / p.1 | 原 key 只有疾病名称，不能表达是否禁用；向左扩至含禁用谓语的最小连续范围，不拼接非连续文字。；补齐问题或关键证据实际涉及的切片：mixed_zh_en。 |
| ms-0003 | REVISE | query,slices | 35ae3bb3cb14 / p.3 | 保留“可能尚无症状”的不确定性，而不是把24小时解释为必然发作时间；补否定切片。；补齐问题或关键证据实际涉及的切片：negation。 |
| ms-0004 | OK | 无 | 35ae3bb3cb14 / p.1 | 初始每日1mg和控制良好时维持的条件在本段完整；不是换药规则或每日上限。 |
| ms-0005 | OK | 无 | 2b8ab3b1bfea / p.1 | 狭心症、每日100–200mg、早晚分二次完整；不混用同页高血压的可单次给药方案。 |
| ms-0006 | REVISE | slices | 2b8ab3b1bfea / p.2 | “不可与verapamil并用”有明确原文，理由句完整；不能误成可监测后常规併用。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0007 | OK | 无 | 662b69e6044e / p.1 | 只问超过75岁ST段上升急性心肌梗塞病人的预载剂量，key完整表达“不应”；span保留STEMI范围。 |
| ms-0008 | REVISE | query | 662b69e6044e / p.1 | 按“怀孕”段的“不建议”作答，不把研究资料不足改写成已证明安全；限定段落以区别同页禁忌栏。 |
| ms-0009 | REVISE | key_text,slices | 662b69e6044e / p.1 | 停药是肯定式动作，但“不希望有抗血小板作用”是实际限制条件；key保留该条件，避免把7天推广至所有手术。；补齐问题或关键证据实际涉及的切片：negation。 |
| ms-0010 | REVISE | query,key_text | 662b69e6044e / p.1 | 补上Clopidogrel对象，并将问题限定为一般每日用量，避免和急性冠状动脉症候群预载方案混淆。 |
| ms-0011 | REVISE | query | 5ef121b394cb / p.1 | 同页禁忌栏和交互作用段均有禁用信息；问题限定禁忌栏以锁定单一目标，不把key逐字唯一等同于答案条款唯一。 |
| ms-0012 | REVISE | query,slices | 5ef121b394cb / p.1 | 补商品名，锁定透析场景的2-2条。400mg日上限在同页重复，保留透析后给药作为必要区分，不借用非透析段落。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0013 | REVISE | query,slices | 5ef121b394cb / p.1 | 补商品名，锁定信诺隆仿单；60天是接触后吸入性炭疽病的总治疗期，不是所有感染的疗程。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0014 | OK | 无 | 5ef121b394cb / p.1 | 原文明确说重症肌无力患者应避免使用；不把风险表述改为已观察到一定恶化。 |
| ms-0015 | REVISE | query,slices | 8f274dc347f7 / p.1 | 去掉叙述性铺垫；明确只检查急性心衰竭病史这一项条件，避免把6周误写成全部治疗准入条件。；补齐问题或关键证据实际涉及的切片：negation, drug_name_zh。 |
| ms-0016 | REVISE | slices | 8f274dc347f7 / p.2 | 第1周的剂量行是完整表格式给药单元；保留第1周而非只留1.25mg。；补齐问题或关键证据实际涉及的切片：drug_name_zh, time_window。 |
| ms-0017 | REVISE | slices | 8f274dc347f7 / p.3 | 经验不足及不建议儿童使用在同一完整句，保留否定。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0018 | REVISE | key_text,evidence_span,slices | 8f274dc347f7 / p.2 | 该10mg上限属于高血压/狭心症，不应套用到另列的慢性心衰竭规则；span补入所属治疗标题和完整分级条款。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0019 | REVISE | key_text,evidence_span | 42f20f2b5b0e / p.2 | key补全Allopurinol先行词；原span停在逗号前，补至完整句末，保留抗炎替代处置的语境。 |
| ms-0020 | REVISE | key_text | 42f20f2b5b0e / p.3 | 问题问起始量和日上限，原key只含起始及增量；扩至同时含100mg/日与800mg上限的连续两句，不改写源文增量措辞。 |
| ms-0021 | OK | 无 | f80b904f4e2f / p.1 | “应避免同用esomeprazole和clopidogrel”与问题一致；保留源文的推荐强度及交叉引用。 |
| ms-0022 | REVISE | key_text,evidence_span | f80b904f4e2f / p.1 | 原key的“起始”重复来自重叠文字层；从最后一个“起始”取连续、唯一的“起始剂量”子串，不再携带重复词。span补至首个完整句末，保留文字层重复而不伪造norm-v1已修复；另在审校记录提供视觉转写。 |
| ms-0023 | REVISE | key_text,slices | 70d3d976a3b4 / p.1 | 原key在同页“糜烂性食道炎”和“预防再出血”两处出现；加入适应症作为最短的有效区分，不利用空格差异区分。；补齐问题或关键证据实际涉及的切片：drug_name_zh, time_window。 |
| ms-0024 | REVISE | slices | 70d3d976a3b4 / p.1 | 不可与nelfinavir併用的完整句与所问一致，不混为另一商品。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0025 | REVISE | query,key_text,slices | 70d3d976a3b4 / p.1 | 补商品名锁定怡胃适；key保留严重肝功能不良条件，而不是一般病人通用20mg上限。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0026 | REVISE | query,key_text,slices | 70d3d976a3b4 / p.1 | “通常多久之后才会”暗示确定发作时间，超出通报资料；改问这些通报中的用药时长，且key同时包含低血镁这一结局。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0027 | DROP | 无 | b1756268da31 / p.1 | PDF页面图像可读，但草稿key/span为大段字体编码乱码，部分还缺字；不在这种norm-v1表示上确认文本gold。应先修复抽取、以繁体重写问题、重锚定并复核后再入集。不能只删掉机械告警对应的标签来使样本过关。 |
| ms-0028 | DROP | 无 | b1756268da31 / p.2 | PDF页面图像可读，但草稿key/span为大段字体编码乱码，部分还缺字；不在这种norm-v1表示上确认文本gold。应先修复抽取、以繁体重写问题、重锚定并复核后再入集。不能只删掉机械告警对应的标签来使样本过关。 |
| ms-0029 | DROP | 无 | b1756268da31 / p.1 | PDF页面图像可读，但草稿key/span为大段字体编码乱码，部分还缺字；不在这种norm-v1表示上确认文本gold。应先修复抽取、以繁体重写问题、重锚定并复核后再入集。不能只删掉机械告警对应的标签来使样本过关。 |
| ms-0030 | REVISE | slices | c59161e8c6b4 / p.1 | 体液缺乏及高剂量利尿剂条件明确，25mg每日一次和“需考虑”强度正确。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0031 | REVISE | key_text | c59161e8c6b4 / p.1 | 问题只问糖尿病，key截到完整的糖尿病禁用命题即可，不必把另一分支肾功能阈值塞进key；完整span保留两分支。 |
| ms-0032 | REVISE | slices | c59161e8c6b4 / p.1 | 新生儿/儿科肾小球过滤率是适用人群条件，不是药物剂量；保留“不建议”而不是改成未限定人群的禁用。；删除不符合本轮操作口径的切片：dose_unit。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0033 | REVISE | slices | c59161e8c6b4 / p.2 | losartan及活性代谢物两者、均无法透析排除完整保留。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0034 | REVISE | key_text,slices | 8988edefb282 / p.2 | 起始量与最大量都是问题要求；key扩至源文连续两句，不能只留下800mg。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0035 | OK | 无 | 8988edefb282 / p.9 | 紧密容器、室温、避光三项保存条件完整，单位/温度未被臆造。 |
| ms-0036 | REVISE | key_text,slices | 8988edefb282 / p.2 | 补全Allopurinol先行词，完整保留缺乏抗炎效力及不用于急性发作的两句。；补齐问题或关键证据实际涉及的切片：drug_name_zh, mixed_zh_en。 |
| ms-0037 | REVISE | query,slices | 8988edefb282 / p.3 | 本段属于一般成人及青少年用量，不是儿童肿瘤高尿酸血症用量；问题明确成人，保留最好2–3天及600–800mg。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0038 | OK | 无 | ad8b0ba2d6c9 / p.2 | 机械告警为漏检：原文“不要再开始使用”是否定；未从外部资料添加本文件不存在的复药例外。 |
| ms-0039 | REVISE | key_text,evidence_span,slices | ad8b0ba2d6c9 / p.3 | Markdown截断恰好隐藏安全原因需更快减量的例外；补齐整句，key保留常规减量及例外，不能写成无条件至少2周。；补齐问题或关键证据实际涉及的切片：drug_name_zh, negation。 |
| ms-0040 | OK | 无 | ad8b0ba2d6c9 / p.4 | 过敏人群与禁止使用谓语齐全，示例及参阅括号完整。 |
| ms-0041 | REVISE | query | ad8b0ba2d6c9 / p.9 | 第9物理页8.6节与第3物理页有等义重复建议；限定8.6节而非混用印刷页。B级约50%、C级75%、依临床反应调整均保留。 |
| ms-0042 | REVISE | query,evidence_span | cb1abe12731f / p.1 | 原span截在单次剂量，遗漏非紧急/毒性风险高者分次的限定；补齐快速负荷段并避免把可单次方案说成人人适用。 |
| ms-0043 | REVISE | evidence_span | cb1abe12731f / p.2 | 当前所问可由第二个完整条件句独立回答；去除前面依赖列表标题的另一分支，避免读者将其例外错误套到本问题。 |
| ms-0044 | OK | 无 | cb1abe12731f / p.3 | 限定选择性而非急救直流电击；24小时停药句完整。 |
| ms-0045 | OK | 无 | cb1abe12731f / p.2 | 比较对象为非老年人，建议较低剂量；不从定性调整推出具体数值。 |
| ms-0046 | REVISE | slices | b6af0d88b1f0 / p.1 | 机械告警成立：应停止服药是正向动作；“非急需”是手术类型，不据此把整条当成否定用药题；不混入显影剂48小时规则。；删除不符合本轮操作口径的切片：negation。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0047 | REVISE | key_text,slices | b6af0d88b1f0 / p.1 | “通常”是一般用量限定，应保留在key内；频次二次与每次一锭完整，不用另一规格折算替换本条。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0048 | REVISE | slices | 3981295da5a6 / p.1 | 已限定高血压一般剂量；query只有英文商品名Losacar，不应因文件标题有中文就贴drug_name_zh。；删除不符合本轮操作口径的切片：drug_name_zh。 |
| ms-0049 | REVISE | query,key_text,slices | 3981295da5a6 / p.1 | key漏掉可增加至100mg的第二要点；源文未把它明确叫“绝对最大剂量”，问题改成可增加至的剂量。；删除不符合本轮操作口径的切片：drug_name_zh。 |
| ms-0050 | REVISE | query,key_text,evidence_span,slices | 3981295da5a6 / p.1 | 问题补GFR<60条件，不能推广到所有肾功能不全。原key为禁忌列表项却不含禁止谓语，加入“禁忌症”标题及中间原文以保留连续锚点。；删除不符合本轮操作口径的切片：drug_name_zh。 |
| ms-0051 | REVISE | slices | 3981295da5a6 / p.1 | 保留不建议及必要时监测的例外。源文字层“今aliskiren”不擅改为“含”；可读语义以页面为准，原字符串留作锚定。；删除不符合本轮操作口径的切片：drug_name_zh。 |
| ms-0052 | REVISE | key_text,slices | 0879f3f5e1a1 / p.1 | 只问每日范围，key截到10–40mg即可；源文“分依次”不擅自修成“一次”，保留span并标记原文疑似错字。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0053 | REVISE | key_text,slices | 0879f3f5e1a1 / p.1 | 原key只列成分过敏，漏ACE抑制剂相关血管神经性水肿病史；扩为同一完整禁忌句。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0054 | REVISE | slices | 0879f3f5e1a1 / p.4 | 药物过量场景及约6小时的不确定界限均正确，不解读为普通用药的起效时间。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0055 | REVISE | query | 4c21c14e2ced / p.2 | “初始剂量的每日最大”混淆初始100mg和逐步滴定上限；改问抗痛风治疗最大建议日量。 |
| ms-0056 | REVISE | query,key_text | 4c21c14e2ced / p.1 | key补“通常”，避免把1–2周恢复写成所有病人的必然时限；问题同步保留该限定。 |
| ms-0057 | REVISE | key_text | 4c21c14e2ced / p.2 | 补上Allopurinol先行词，避免孤立“它”而丢失药品对象；不引用痛风停或伊风柔同成分仿单替代。 |
| ms-0058 | REVISE | evidence_span | 4c21c14e2ced / p.3 | 第3页儿科/肿瘤相关高尿酸血症章节已核对；不把相邻低龄剂量引入本条，span补48小时后按反应调整的注意。 |
| ms-0059 | REVISE | slices | 6e54ef6f412d / p.1 | 老年人每日25mg和后续递增在完整段落；与成人首四天方案区分。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0060 | REVISE | query,key_text,slices | 6e54ef6f412d / p.1 | 问题问核准状态，key补本品“未核准”而不只用“不适用”来间接推导；限定第3.3节，以区别第18页8.4节的等义重复条款。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0061 | REVISE | key_text,evidence_span,slices | 6e54ef6f412d / p.7 | 原key只覆盖1A类，span在其他药物列表中途截断；保留原问题，补齐全部所列药物类别和例子，不缩题掩盖遗漏。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0062 | REVISE | slices | 6e54ef6f412d / p.18 | 机械告警为漏检：“不要餵母奶”明确否定，保留negation。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0063 | OK | 无 | 0c80faec13d3 / p.1 | 成人及十二岁（含）以上、每日两茶匙和10mg同时保留；未自行增加mL换算。 |
| ms-0064 | OK | 无 | 0c80faec13d3 / p.1 | 机械告警为漏检：“皆不適合投以本劑”明确不适用，保留negation。 |
| ms-0065 | REVISE | slices | 0c80faec13d3 / p.1 | 机械告警成立：48小时前起应停用属于正向停药指令，删除negation；保留skin test及时间。；删除不符合本轮操作口径的切片：negation。 |
| ms-0066 | REVISE | key_text | 0e8e316abd1f / p.1 | 用药方式不仅包含深部缓慢肌注，还包括左右臀部交替；key覆盖所问完整方式并保留“通常”。 |
| ms-0067 | REVISE | query,key_text,evidence_span,section | 0e8e316abd1f / p.1 | 同页有两处相同禁用文字，不能依赖空格区别。选择首页心血管栓塞警示第2项，key/span加入原项目号，问题限定该警示。 |
| ms-0068 | REVISE | query,slices | 0e8e316abd1f / p.1 | 合并重复发问；“无法口服”是不可丢失的适用条件，补否定切片。；补齐问题或关键证据实际涉及的切片：negation。 |
| ms-0069 | OK | 无 | 0e8e316abd1f / p.2 | 25°C以下和阴凉完整；储存温度不是dose_unit。 |
| ms-0070 | REVISE | query,slices | 4c2119065459 / p.1 | 原题“临床上该如何处置”可能涵盖急救等源文未答事项；限定为是否继续或再次使用本药。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0071 | REVISE | query,key_text,slices | 4c2119065459 / p.1 | 合为一问并保留药名先行词；key覆盖最早12小时和20mg每日两次，不把起始量混成后续目标量。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0072 | REVISE | key_text,slices | 4c2119065459 / p.1 | 问题及所属标题明确成人高血压，key补Valsartan对象；不引用同页心衰竭40mg每日两次方案。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0073 | REVISE | slices | 4c2119065459 / p.1 | 不建议双重阻断与必要时监测的原文完整；不把一般不建议升级为所有情形绝对禁用。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0074 | REVISE | key_text,slices | 3b1d0b7fb71d / p.1 | 只问量与频次，key缩到通常成人75mg每日一次即可；完整span仍保留注射方式及最低量最短疗程原则。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0075 | REVISE | query,key_text,evidence_span,slices,section | 3b1d0b7fb71d / p.1 | 同页第2项警示与第7项禁忌的key重复；用禁忌第7项的项目号和限定问题来明确所选锚点，不以空白差异制造唯一性。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0076 | REVISE | slices | 3b1d0b7fb71d / p.2 | 一般不建议同时使用aspirin和diclofenac，完整保留风险理由，不误用aspirin过敏禁忌句。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0077 | REVISE | query,key_text,slices | 3b1d0b7fb71d / p.1 | 源文为diclofenac长期治疗的监测警语，不授权长期使用该注射剂；改写问题避免这个预设，并将肝转氨酶对象放入key。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0078 | REVISE | key_text,slices | c96703065f14 / p.1 | key补中度或重度肝功能不全先行条件，避免孤立“这类病人”；仍使用CINV/RINV段，不换成同页PONV段。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0079 | REVISE | query,key_text,slices | c96703065f14 / p.1 | 原key仅答口服转换时间，漏初始注射8mg；扩至两句。按原文24小时之后表述，不赋予更精确、源文未写的计时零点。；补齐问题或关键证据实际涉及的切片：drug_name_zh, mixed_zh_en。 |
| ms-0080 | REVISE | key_text,slices | c96703065f14 / p.1 | 原key漏追加给药间隔；扩到完整两句，保留年满75岁、起始不超过8mg、输注超过15分钟及间隔至少4小时。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0081 | REVISE | slices | c96703065f14 / p.2 | 第一孕期而非所有孕期范围完整，原文“不应使用”保留。；补齐问题或关键证据实际涉及的切片：drug_name_zh。 |
| ms-0082 | OK | 无 | 81069adaf87d / p.1 | 本产品成分过敏与禁用匹配，未混用同页另一条aliskiren禁忌。 |
| ms-0083 | OK | 无 | 81069adaf87d / p.1 | 第II型糖尿病肾病变标题、50mg和每日一次完整，未误取高血压同剂量条款。 |

## 7. 源文件清单（完整绑定）

### tfda-label-amaryl-2-0-tablets

瑪爾胰 2.0 公絲錠 / Amaryl 2mg

- PDF：`35ae3bb3cb14ba859cfc2ee006aba20762f79fc80834d19e8c606badbf07dc59.pdf`
- SHA-256：`35ae3bb3cb14ba859cfc2ee006aba20762f79fc80834d19e8c606badbf07dc59`
- 主逻辑路径：`/sources_staging/35ae3bb3cb14ba859cfc2ee006aba20762f79fc80834d19e8c606badbf07dc59.pdf`
- 全部用户声明路径：`/sources_staging/35ae3bb3cb14ba859cfc2ee006aba20762f79fc80834d19e8c606badbf07dc59.pdf`
- PDF总物理页：4；本次核查页：1, 3
- 对应样本：ms-0001, ms-0002, ms-0003, ms-0004
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-cancliol-100mg

「明德」心壓暢錠 100 毫克 / CANCLIOL TABLETS 100mg

- PDF：`2b8ab3b1bfea619d8eba938864e10614313dfa92e036bdba6a8fec2cb5fd2425.pdf`
- SHA-256：`2b8ab3b1bfea619d8eba938864e10614313dfa92e036bdba6a8fec2cb5fd2425`
- 主逻辑路径：`/sources/2b8ab3b1bfea619d8eba938864e10614313dfa92e036bdba6a8fec2cb5fd2425.pdf`
- 全部用户声明路径：`/sources_staging/2b8ab3b1bfea619d8eba938864e10614313dfa92e036bdba6a8fec2cb5fd2425.pdf`；`/sources/2b8ab3b1bfea619d8eba938864e10614313dfa92e036bdba6a8fec2cb5fd2425.pdf`
- PDF总物理页：2；本次核查页：1, 2
- 对应样本：ms-0005, ms-0006
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-carvetone-f-c-tablets-75-mg

固栓宜膜衣錠 75 毫克 / Carvetone F.C. Tablets 75 mg

- PDF：`662b69e6044ed9746280815bc3bb5e45a2911c9f5edebf610a5a26aac44e95c9.pdf`
- SHA-256：`662b69e6044ed9746280815bc3bb5e45a2911c9f5edebf610a5a26aac44e95c9`
- 主逻辑路径：`/sources_staging/662b69e6044ed9746280815bc3bb5e45a2911c9f5edebf610a5a26aac44e95c9.pdf`
- 全部用户声明路径：`/sources_staging/662b69e6044ed9746280815bc3bb5e45a2911c9f5edebf610a5a26aac44e95c9.pdf`
- PDF总物理页：2；本次核查页：1
- 对应样本：ms-0007, ms-0008, ms-0009, ms-0010
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-cinolone-iv-infusion-10-mg-ml

「信東」信諾隆靜脈輸注液 2、10 毫克／毫升 / Cinolone IV Infusion

- PDF：`5ef121b394cb2d28407c17ddb29655abfbda65e030e6dee83e5ba148abfef276.pdf`
- SHA-256：`5ef121b394cb2d28407c17ddb29655abfbda65e030e6dee83e5ba148abfef276`
- 主逻辑路径：`/sources_staging/5ef121b394cb2d28407c17ddb29655abfbda65e030e6dee83e5ba148abfef276.pdf`
- 全部用户声明路径：`/sources_staging/5ef121b394cb2d28407c17ddb29655abfbda65e030e6dee83e5ba148abfef276.pdf`
- PDF总物理页：2；本次核查页：1
- 对应样本：ms-0011, ms-0012, ms-0013, ms-0014
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-concor-5

康肯 5 毫克、10 毫克 / Concor 5 / Concor 10

- PDF：`8f274dc347f717feba8b9745949dd8ef4d17ea1ff35995fbbe41848fef93c171.pdf`
- SHA-256：`8f274dc347f717feba8b9745949dd8ef4d17ea1ff35995fbbe41848fef93c171`
- 主逻辑路径：`/sources_staging/8f274dc347f717feba8b9745949dd8ef4d17ea1ff35995fbbe41848fef93c171.pdf`
- 全部用户声明路径：`/sources_staging/8f274dc347f717feba8b9745949dd8ef4d17ea1ff35995fbbe41848fef93c171.pdf`
- PDF总物理页：6；本次核查页：1, 2, 3
- 对应样本：ms-0015, ms-0016, ms-0017, ms-0018
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-deurinol-300mg

痛風停錠 300 毫克 / Deurinol Tablets 300 mg

- PDF：`42f20f2b5b0ea0ed7afe8bb709699a58b222985b70ccada6e0c470f5c3f58a7f.pdf`
- SHA-256：`42f20f2b5b0ea0ed7afe8bb709699a58b222985b70ccada6e0c470f5c3f58a7f`
- 主逻辑路径：`/sources/42f20f2b5b0ea0ed7afe8bb709699a58b222985b70ccada6e0c470f5c3f58a7f.pdf`
- 全部用户声明路径：`/sources_staging/42f20f2b5b0ea0ed7afe8bb709699a58b222985b70ccada6e0c470f5c3f58a7f.pdf`；`/sources/42f20f2b5b0ea0ed7afe8bb709699a58b222985b70ccada6e0c470f5c3f58a7f.pdf`
- PDF总物理页：10；本次核查页：2, 3
- 对应样本：ms-0019, ms-0020
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-esomen-40mg

「景德」胃所樂腸溶膜衣錠 40 毫克 / Esomen Enteric-Coated Tablets 40 mg

- PDF：`f80b904f4e2f15a59cb78fe1baed5c1c06b8b975d43dc0291217d64c43e43fbb.pdf`
- SHA-256：`f80b904f4e2f15a59cb78fe1baed5c1c06b8b975d43dc0291217d64c43e43fbb`
- 主逻辑路径：`/sources/f80b904f4e2f15a59cb78fe1baed5c1c06b8b975d43dc0291217d64c43e43fbb.pdf`
- 全部用户声明路径：`/sources_staging/f80b904f4e2f15a59cb78fe1baed5c1c06b8b975d43dc0291217d64c43e43fbb.pdf`；`/sources/f80b904f4e2f15a59cb78fe1baed5c1c06b8b975d43dc0291217d64c43e43fbb.pdf`
- PDF总物理页：4；本次核查页：1
- 对应样本：ms-0021, ms-0022
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-esomepsun-40mg-tablets-sunyet

怡胃適腸溶錠 40 毫克 / Esomepsun 40 tablets “SUNYET”

- PDF：`70d3d976a3b4ef70d192755440066618dd538d1bdf16659daa255b6f04dcaa81.pdf`
- SHA-256：`70d3d976a3b4ef70d192755440066618dd538d1bdf16659daa255b6f04dcaa81`
- 主逻辑路径：`/sources_staging/70d3d976a3b4ef70d192755440066618dd538d1bdf16659daa255b6f04dcaa81.pdf`
- 全部用户声明路径：`/sources_staging/70d3d976a3b4ef70d192755440066618dd538d1bdf16659daa255b6f04dcaa81.pdf`
- PDF总物理页：2；本次核查页：1
- 对应样本：ms-0023, ms-0024, ms-0025, ms-0026
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-glimaryl-tablets-2mg-glimepiride

Glimaryl Tablets 2mg（Glimepiride；中文文本层乱码，需查页面图像）

- PDF：`b1756268da31c9205cea8766181345921bdbec9c1930137428c79c5c3d8729f7.pdf`
- SHA-256：`b1756268da31c9205cea8766181345921bdbec9c1930137428c79c5c3d8729f7`
- 主逻辑路径：`/sources_staging/b1756268da31c9205cea8766181345921bdbec9c1930137428c79c5c3d8729f7.pdf`
- 全部用户声明路径：`/sources_staging/b1756268da31c9205cea8766181345921bdbec9c1930137428c79c5c3d8729f7.pdf`
- PDF总物理页：2；本次核查页：1, 2
- 对应样本：ms-0027, ms-0028, ms-0029
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-hetlosar-100-losartan-tablets-100mg

特釋壓膜衣錠 100 毫克 / Hetlosar 100

- PDF：`c59161e8c6b42e149351ccc8c1d5ca8337627fa490861e6fb7dceb2bbca13f36.pdf`
- SHA-256：`c59161e8c6b42e149351ccc8c1d5ca8337627fa490861e6fb7dceb2bbca13f36`
- 主逻辑路径：`/sources_staging/c59161e8c6b42e149351ccc8c1d5ca8337627fa490861e6fb7dceb2bbca13f36.pdf`
- 全部用户声明路径：`/sources_staging/c59161e8c6b42e149351ccc8c1d5ca8337627fa490861e6fb7dceb2bbca13f36.pdf`
- PDF总物理页：3；本次核查页：1, 2
- 对应样本：ms-0030, ms-0031, ms-0032, ms-0033
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-ifonol-tablets-300mg-astar

「安星」伊風柔錠 300 毫克 / Ifonol Tablets 300 mg “Astar”

- PDF：`8988edefb2825b18a9d5ebdb53b6f3bd09b7b75410d24814dd8f5ee2c8c7dfe7.pdf`
- SHA-256：`8988edefb2825b18a9d5ebdb53b6f3bd09b7b75410d24814dd8f5ee2c8c7dfe7`
- 主逻辑路径：`/sources_staging/8988edefb2825b18a9d5ebdb53b6f3bd09b7b75410d24814dd8f5ee2c8c7dfe7.pdf`
- 全部用户声明路径：`/sources_staging/8988edefb2825b18a9d5ebdb53b6f3bd09b7b75410d24814dd8f5ee2c8c7dfe7.pdf`
- PDF总物理页：9；本次核查页：2, 3, 9
- 对应样本：ms-0034, ms-0035, ms-0036, ms-0037
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-lamofree-er-tablets-25mg

樂癲活持續釋放膜衣錠 25、50、100 毫克 / Lamofree ER Tablets

- PDF：`ad8b0ba2d6c9421349f86080b4a35218088fb6895493ae13fbb3aa32f0fd7ae2.pdf`
- SHA-256：`ad8b0ba2d6c9421349f86080b4a35218088fb6895493ae13fbb3aa32f0fd7ae2`
- 主逻辑路径：`/sources_staging/ad8b0ba2d6c9421349f86080b4a35218088fb6895493ae13fbb3aa32f0fd7ae2.pdf`
- 全部用户声明路径：`/sources_staging/ad8b0ba2d6c9421349f86080b4a35218088fb6895493ae13fbb3aa32f0fd7ae2.pdf`
- PDF总物理页：15；本次核查页：2, 3, 4, 9
- 对应样本：ms-0038, ms-0039, ms-0040, ms-0041
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-lanoxin-digoxin-tablets-0-25mg-b-p

隆我心錠 / LANOXIN Digoxin Tablets 0.25mg B.P.

- PDF：`cb1abe12731f9292a0a49937fb33ba1fe79e1e775883af4be74741c5eaf978ce.pdf`
- SHA-256：`cb1abe12731f9292a0a49937fb33ba1fe79e1e775883af4be74741c5eaf978ce`
- 主逻辑路径：`/sources_staging/cb1abe12731f9292a0a49937fb33ba1fe79e1e775883af4be74741c5eaf978ce.pdf`
- 全部用户声明路径：`/sources_staging/cb1abe12731f9292a0a49937fb33ba1fe79e1e775883af4be74741c5eaf978ce.pdf`
- PDF总物理页：6；本次核查页：1, 2, 3
- 对应样本：ms-0042, ms-0043, ms-0044, ms-0045
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-loformin-850mg

「育生」美洛醣錠 500 毫克、美洛醣膜衣錠 850 毫克 / Loformin

- PDF：`b6af0d88b1f0e3b5660e6e3c6678e18c40616073bc082b6cb7214604b2f81f98.pdf`
- SHA-256：`b6af0d88b1f0e3b5660e6e3c6678e18c40616073bc082b6cb7214604b2f81f98`
- 主逻辑路径：`/sources/b6af0d88b1f0e3b5660e6e3c6678e18c40616073bc082b6cb7214604b2f81f98.pdf`
- 全部用户声明路径：`/sources/b6af0d88b1f0e3b5660e6e3c6678e18c40616073bc082b6cb7214604b2f81f98.pdf`
- PDF总物理页：2；本次核查页：1
- 对应样本：ms-0046, ms-0047
- 版本说明：未确认明确修订日期；版面代码 S0401 不解释为日期
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-losacar-100-tablets

緩壓膜衣錠 100 毫克 / Losacar 100 Tablets

- PDF：`3981295da5a68ef3bf43b30c4d7783b9ebfa351319c134bb2f5710a11ac14d5b.pdf`
- SHA-256：`3981295da5a68ef3bf43b30c4d7783b9ebfa351319c134bb2f5710a11ac14d5b`
- 主逻辑路径：`/sources_staging/3981295da5a68ef3bf43b30c4d7783b9ebfa351319c134bb2f5710a11ac14d5b.pdf`
- 全部用户声明路径：`/sources_staging/3981295da5a68ef3bf43b30c4d7783b9ebfa351319c134bb2f5710a11ac14d5b.pdf`
- PDF总物理页：2；本次核查页：1
- 对应样本：ms-0048, ms-0049, ms-0050, ms-0051
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-perisafe-tablets-10mg-enalapil

脈得服錠 10 公絲（Enalapril） / PERISAFE Tablets 10mg

- PDF：`0879f3f5e1a1b31a420dddc8510817aee8b57abe074ab656de7fc7da2afe5d4c.pdf`
- SHA-256：`0879f3f5e1a1b31a420dddc8510817aee8b57abe074ab656de7fc7da2afe5d4c`
- 主逻辑路径：`/sources_staging/0879f3f5e1a1b31a420dddc8510817aee8b57abe074ab656de7fc7da2afe5d4c.pdf`
- 全部用户声明路径：`/sources_staging/0879f3f5e1a1b31a420dddc8510817aee8b57abe074ab656de7fc7da2afe5d4c.pdf`
- PDF总物理页：4；本次核查页：1, 4
- 对应样本：ms-0052, ms-0053, ms-0054
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-purinol-tablets

「居禮」拔痛酸錠 / PURINOL Tablets “Curie”

- PDF：`4c21c14e2cedd67e401aedf2f678a9fceaf9d3935751cb19d40bf62117c89dd9.pdf`
- SHA-256：`4c21c14e2cedd67e401aedf2f678a9fceaf9d3935751cb19d40bf62117c89dd9`
- 主逻辑路径：`/sources_staging/4c21c14e2cedd67e401aedf2f678a9fceaf9d3935751cb19d40bf62117c89dd9.pdf`
- 全部用户声明路径：`/sources_staging/4c21c14e2cedd67e401aedf2f678a9fceaf9d3935751cb19d40bf62117c89dd9.pdf`
- PDF总物理页：7；本次核查页：1, 2, 3
- 对应样本：ms-0055, ms-0056, ms-0057, ms-0058
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-quetialin-f-c-tablets-100mg-quetiapine

喜樂平膜衣錠 100 毫克（Quetiapine）

- PDF：`6e54ef6f412df596ff6b2e1fe58aabbedde6264cdcb2028c322852370015f4e7.pdf`
- SHA-256：`6e54ef6f412df596ff6b2e1fe58aabbedde6264cdcb2028c322852370015f4e7`
- 主逻辑路径：`/sources_staging/6e54ef6f412df596ff6b2e1fe58aabbedde6264cdcb2028c322852370015f4e7.pdf`
- 全部用户声明路径：`/sources_staging/6e54ef6f412df596ff6b2e1fe58aabbedde6264cdcb2028c322852370015f4e7.pdf`
- PDF总物理页：24；本次核查页：1, 7, 18
- 对应样本：ms-0059, ms-0060, ms-0061, ms-0062
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-rodamine-syrup-w-p

「華盛頓」洛得敏糖漿 / Rodamine Syrup “W.P.”

- PDF：`0c80faec13d3404834be06c3212ccdf81b5e63af80064009d93106ecca47f293.pdf`
- SHA-256：`0c80faec13d3404834be06c3212ccdf81b5e63af80064009d93106ecca47f293`
- 主逻辑路径：`/sources_staging/0c80faec13d3404834be06c3212ccdf81b5e63af80064009d93106ecca47f293.pdf`
- 全部用户声明路径：`/sources_staging/0c80faec13d3404834be06c3212ccdf81b5e63af80064009d93106ecca47f293.pdf`
- PDF总物理页：1；本次核查页：1
- 对应样本：ms-0063, ms-0064, ms-0065
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-staren-injection-n-k-diclofenac

「南光」賜痛寧注射液（待克菲那） / Staren Injection

- PDF：`0e8e316abd1fcd16b0890516b340fa47311dea7e2fb8313e625db1e4fb1150d1.pdf`
- SHA-256：`0e8e316abd1fcd16b0890516b340fa47311dea7e2fb8313e625db1e4fb1150d1`
- 主逻辑路径：`/sources_staging/0e8e316abd1fcd16b0890516b340fa47311dea7e2fb8313e625db1e4fb1150d1.pdf`
- 全部用户声明路径：`/sources_staging/0e8e316abd1fcd16b0890516b340fa47311dea7e2fb8313e625db1e4fb1150d1.pdf`
- PDF总物理页：2；本次核查页：1, 2
- 对应样本：ms-0066, ms-0067, ms-0068, ms-0069
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-vaks-f-c-tablets-80mg

衛欣保膜衣錠 80 毫克、320 毫克 / Vaks F.C. Tablets

- PDF：`4c211906545934a9ea4a41ce0cdaeed1ce9d882da06b7e5fd376d50f4a94d794.pdf`
- SHA-256：`4c211906545934a9ea4a41ce0cdaeed1ce9d882da06b7e5fd376d50f4a94d794`
- 主逻辑路径：`/sources_staging/4c211906545934a9ea4a41ce0cdaeed1ce9d882da06b7e5fd376d50f4a94d794.pdf`
- 全部用户声明路径：`/sources_staging/4c211906545934a9ea4a41ce0cdaeed1ce9d882da06b7e5fd376d50f4a94d794.pdf`
- PDF总物理页：2；本次核查页：1
- 对应样本：ms-0070, ms-0071, ms-0072, ms-0073
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-venton-injection-diclofenac-lita

「利達」免痛注射液（待克菲那） / Venton Injection

- PDF：`3b1d0b7fb71d65e81493f10a46bb1640d2a5635e70621a5e6a38867d8f65aab3.pdf`
- SHA-256：`3b1d0b7fb71d65e81493f10a46bb1640d2a5635e70621a5e6a38867d8f65aab3`
- 主逻辑路径：`/sources_staging/3b1d0b7fb71d65e81493f10a46bb1640d2a5635e70621a5e6a38867d8f65aab3.pdf`
- 全部用户声明路径：`/sources_staging/3b1d0b7fb71d65e81493f10a46bb1640d2a5635e70621a5e6a38867d8f65aab3.pdf`
- PDF总物理页：2；本次核查页：1, 2
- 对应样本：ms-0074, ms-0075, ms-0076, ms-0077
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-vomiz-for-iv-injection-2mg-ml

莫尼茲靜脈注射劑 2 毫克／毫升 / Vomiz for IV Injection 2mg/ml

- PDF：`c96703065f145c812f38466a545fe62d0dbe6c566d380892d1702a720dd6c1ce.pdf`
- SHA-256：`c96703065f145c812f38466a545fe62d0dbe6c566d380892d1702a720dd6c1ce`
- 主逻辑路径：`/sources_staging/c96703065f145c812f38466a545fe62d0dbe6c566d380892d1702a720dd6c1ce.pdf`
- 全部用户声明路径：`/sources_staging/c96703065f145c812f38466a545fe62d0dbe6c566d380892d1702a720dd6c1ce.pdf`
- PDF总物理页：3；本次核查页：1, 2
- 对应样本：ms-0078, ms-0079, ms-0080, ms-0081
- 版本说明：见原始 PDF；索引不推定未明确标注的版本或生效日期。
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

### tfda-label-zosaa-50mg

穩壓膜衣錠 50 毫克 / Zosaa F.C. Tablets 50 mg

- PDF：`81069adaf87d21e640d9b5cbc83a799a59a33acbdc4ead46ed338c9ad6d06b3a.pdf`
- SHA-256：`81069adaf87d21e640d9b5cbc83a799a59a33acbdc4ead46ed338c9ad6d06b3a`
- 主逻辑路径：`/sources/81069adaf87d21e640d9b5cbc83a799a59a33acbdc4ead46ed338c9ad6d06b3a.pdf`
- 全部用户声明路径：`/sources/81069adaf87d21e640d9b5cbc83a799a59a33acbdc4ead46ed338c9ad6d06b3a.pdf`
- PDF总物理页：1；本次核查页：1
- 对应样本：ms-0082, ms-0083
- 版本说明：正式修订日期待确认；文本层另含「B 版 104.10.27.」版面标记
- 身份及哈希：已核对；此为附件内容绑定，不是已确认数据库document_key或官方最新版本。

## 8. 每条具体改动（原值 → 新值）

### ms-0001 — OK

来源：`/sources_staging/35ae3bb3cb14ba859cfc2ee006aba20762f79fc80834d19e8c606badbf07dc59.pdf`，物理第1页；章节：[說明]。

裁决理由：最高建议日剂量的对象、数值和单位均保留；完整独立句与所问一致。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0002 — REVISE

来源：`/sources_staging/35ae3bb3cb14ba859cfc2ee006aba20762f79fc80834d19e8c606badbf07dc59.pdf`，物理第1页；章节：[禁忌]。

裁决理由：原 key 只有疾病名称，不能表达是否禁用；向左扩至含禁用谓语的最小连续范围，不拼接非连续文字。 补齐问题或关键证据实际涉及的切片：mixed_zh_en。

**key_text**

原值：嚴重腎臟或肝臟功能異常

新值：下列情況禁用 Amaryl:胰島素依賴型糖尿病、糖尿性昏迷、酮酸中毒、嚴重腎臟或肝臟功能異常

**slices**

原值：negation, drug_name_zh

新值：negation, drug_name_zh, mixed_zh_en

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0003 — REVISE

来源：`/sources_staging/35ae3bb3cb14ba859cfc2ee006aba20762f79fc80834d19e8c606badbf07dc59.pdf`，物理第3页；章节：[藥物過量]。

裁决理由：保留“可能尚无症状”的不确定性，而不是把24小时解释为必然发作时间；补否定切片。 补齐问题或关键证据实际涉及的切片：negation。

**query**

原值：瑪爾胰藥物過量後,服藥多久可能仍無低血糖症狀出現?

新值：瑪爾胰過量服用後，最初多久可能仍未出現低血糖症狀？

**slices**

原值：time_window, drug_name_zh

新值：time_window, drug_name_zh, negation

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0004 — OK

来源：`/sources_staging/35ae3bb3cb14ba859cfc2ee006aba20762f79fc80834d19e8c606badbf07dc59.pdf`，物理第1页；章节：[說明]。

裁决理由：初始每日1mg和控制良好时维持的条件在本段完整；不是换药规则或每日上限。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0005 — OK

来源：`/sources/2b8ab3b1bfea619d8eba938864e10614313dfa92e036bdba6a8fec2cb5fd2425.pdf`，物理第1页；章节：【用法用量】。

裁决理由：狭心症、每日100–200mg、早晚分二次完整；不混用同页高血压的可单次给药方案。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0006 — REVISE

来源：`/sources/2b8ab3b1bfea619d8eba938864e10614313dfa92e036bdba6a8fec2cb5fd2425.pdf`，物理第2页；章节：【注意事項】。

裁决理由：“不可与verapamil并用”有明确原文，理由句完整；不能误成可监测后常规併用。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0007 — OK

来源：`/sources_staging/662b69e6044ed9746280815bc3bb5e45a2911c9f5edebf610a5a26aac44e95c9.pdf`，物理第1页；章节：劑量和用法。

裁决理由：只问超过75岁ST段上升急性心肌梗塞病人的预载剂量，key完整表达“不应”；span保留STEMI范围。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0008 — REVISE

来源：`/sources_staging/662b69e6044ed9746280815bc3bb5e45a2911c9f5edebf610a5a26aac44e95c9.pdf`，物理第1页；章节：生育能力、懷孕和授乳。

裁决理由：按“怀孕”段的“不建议”作答，不把研究资料不足改写成已证明安全；限定段落以区别同页禁忌栏。

**query**

原值：孕婦是否建議使用Carvetone（clopidogrel）？

新值：Carvetone（clopidogrel）仿單的「懷孕」段落，是否建議孕婦使用此藥？

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0009 — REVISE

来源：`/sources_staging/662b69e6044ed9746280815bc3bb5e45a2911c9f5edebf610a5a26aac44e95c9.pdf`，物理第1页；章节：警語及注意事項。

裁决理由：停药是肯定式动作，但“不希望有抗血小板作用”是实际限制条件；key保留该条件，避免把7天推广至所有手术。 补齐问题或关键证据实际涉及的切片：negation。

**key_text**

原值：應於手術進行前 7天停止使用 clopidogrel

新值：若病人選擇手術治療並且不希望在手術期間有抗血小板作用,應於手術進行前 7天停止使用 clopidogrel

**slices**

原值：time_window, mixed_zh_en

新值：time_window, mixed_zh_en, negation

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0010 — REVISE

来源：`/sources_staging/662b69e6044ed9746280815bc3bb5e45a2911c9f5edebf610a5a26aac44e95c9.pdf`，物理第1页；章节：劑量和用法。

裁决理由：补上Clopidogrel对象，并将问题限定为一般每日用量，避免和急性冠状动脉症候群预载方案混淆。

**query**

原值：成人與老年人使用Carvetone（clopidogrel）的建議劑量為何？

新值：依Carvetone（clopidogrel）仿單「成人和老年人」段落，一般建議的每日用量與服用次數為何？

**key_text**

原值：建議劑量為每天 75 mg,一天一次

新值：Clopidogrel 的建議劑量為每天 75 mg,一天一次

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0011 — REVISE

来源：`/sources_staging/5ef121b394cb2d28407c17ddb29655abfbda65e030e6dee83e5ba148abfef276.pdf`，物理第1页；章节：【禁忌】。

裁决理由：同页禁忌栏和交互作用段均有禁用信息；问题限定禁忌栏以锁定单一目标，不把key逐字唯一等同于答案条款唯一。

**query**

原值：信諾隆（ciprofloxacin）靜脈輸注液可以與Tizanidine併用嗎？

新值：信諾隆（ciprofloxacin）靜脈輸注液仿單的「禁忌」欄，對與Tizanidine併用有何規定？

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0012 — REVISE

来源：`/sources_staging/5ef121b394cb2d28407c17ddb29655abfbda65e030e6dee83e5ba148abfef276.pdf`，物理第1页；章节：用法用量-特殊族群-腎及肝功能受損的病患-2.腎功能受損且須血液透析。

裁决理由：补商品名，锁定透析场景的2-2条。400mg日上限在同页重复，保留透析后给药作为必要区分，不借用非透析段落。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：需要血液透析且creatinine清除率低於30 ml/min/1.73m2的病人，靜脈注射Ciprofloxacin的每日最大劑量為何？

新值：需要血液透析且creatinine清除率低於30 ml/min/1.73m2的病人，使用信諾隆（Ciprofloxacin）靜脈輸注液時，每日最大劑量為何？

**slices**

原值：dose_unit, mixed_zh_en

新值：dose_unit, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0013 — REVISE

来源：`/sources_staging/5ef121b394cb2d28407c17ddb29655abfbda65e030e6dee83e5ba148abfef276.pdf`，物理第1页；章节：用法用量-治療期。

裁决理由：补商品名，锁定信诺隆仿单；60天是接触后吸入性炭疽病的总治疗期，不是所有感染的疗程。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：吸入性炭疽病暴露後,使用Ciprofloxacin治療的總治療期為多久？

新值：吸入性炭疽病暴露後，信諾隆仿單所列Ciprofloxacin治療的總療程為多久？

**slices**

原值：time_window, mixed_zh_en

新值：time_window, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0014 — OK

来源：`/sources_staging/5ef121b394cb2d28407c17ddb29655abfbda65e030e6dee83e5ba148abfef276.pdf`，物理第1页；章节：警語及注意事項-肌肉骨骼系統。

裁决理由：原文明确说重症肌无力患者应避免使用；不把风险表述改为已观察到一定恶化。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0015 — REVISE

来源：`/sources_staging/8f274dc347f717feba8b9745949dd8ef4d17ea1ff35995fbbe41848fef93c171.pdf`，物理第1页；章节：治療穩定型慢性中度至重度心衰竭。

裁决理由：去掉叙述性铺垫；明确只检查急性心衰竭病史这一项条件，避免把6周误写成全部治疗准入条件。 补齐问题或关键证据实际涉及的切片：negation, drug_name_zh。

**query**

原值：醫師想確認：開始使用康肯®治療穩定型慢性中度至重度心衰竭前，病人需在過去多久內沒有發生急性心衰竭才符合治療條件？

新值：開始用康肯®治療穩定型慢性中度至重度心衰竭前，就急性心衰竭病史這項條件而言，病人須在過去多久內未曾發生急性心衰竭？

**slices**

原值：time_window

新值：time_window, negation, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0016 — REVISE

来源：`/sources_staging/8f274dc347f717feba8b9745949dd8ef4d17ea1ff35995fbbe41848fef93c171.pdf`，物理第2页；章节：治療穩定型慢性心衰竭劑量調整。

裁决理由：第1周的剂量行是完整表格式给药单元；保留第1周而非只留1.25mg。 补齐问题或关键证据实际涉及的切片：drug_name_zh, time_window。

**slices**

原值：dose_unit, mixed_zh_en

新值：dose_unit, mixed_zh_en, drug_name_zh, time_window

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0017 — REVISE

来源：`/sources_staging/8f274dc347f717feba8b9745949dd8ef4d17ea1ff35995fbbe41848fef93c171.pdf`，物理第3页；章节：特殊族群。

裁决理由：经验不足及不建议儿童使用在同一完整句，保留否定。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0018 — REVISE

来源：`/sources_staging/8f274dc347f717feba8b9745949dd8ef4d17ea1ff35995fbbe41848fef93c171.pdf`，物理第2页；章节：腎或肝功能不全的病人。

裁决理由：该10mg上限属于高血压/狭心症，不应套用到另列的慢性心衰竭规则；span补入所属治疗标题和完整分级条款。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：bisoprolol fumarate 的每日劑量不可超過 10 毫克

新值：嚴重腎功能不全(肌酐酸廓清率<20 毫升 /分鐘)及嚴重肝功能不全的病人,bisoprolol fumarate 的每日劑量不可超過 10 毫克

**evidence_span**

原值：嚴重腎功能不全(肌酐酸廓清率<20 毫升 /分鐘)及嚴重肝功能不全的病人,bisoprolol fumarate 的每日劑量不可超過 10 毫克。

新值：治療高血壓或狹心症:輕度至中度肝或腎功能不全的病人通常不需要調整劑量。嚴重腎功能不全(肌酐酸廓清率<20 毫升 /分鐘)及嚴重肝功能不全的病人,bisoprolol fumarate 的每日劑量不可超過10 毫克。

**slices**

原值：dose_unit, negation, mixed_zh_en

新值：dose_unit, negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0019 — REVISE

来源：`/sources/42f20f2b5b0ea0ed7afe8bb709699a58b222985b70ccada6e0c470f5c3f58a7f.pdf`，物理第2页；章节：適應症。

裁决理由：key补全Allopurinol先行词；原span停在逗号前，补至完整句末，保留抗炎替代处置的语境。

**key_text**

原值：它必須不得使用於痛風性關節炎的急性發作

新值：Allopurinol沒有抗發炎的效力,它必須不得使用於痛風性關節炎的急性發作

**evidence_span**

原值：Allopurinol沒有抗發炎的效力,它必須不得使用於痛風性關節炎的急性發作

新值：Allopurinol 沒有抗發炎的效力,它必須不得使用於痛風性關節炎的急性發作,一種抗發炎藥,最好是一種非類固醇類抗發炎劑(NSAI)或者是皮質類固醇 (Corticosteroid)〔當可行時,最好是滑膜內注射(Intrasynovial injection)〕必須加以使用,以治療急性發作。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0020 — REVISE

来源：`/sources/42f20f2b5b0ea0ed7afe8bb709699a58b222985b70ccada6e0c470f5c3f58a7f.pdf`，物理第3页；章节：用法用量-抗痛風劑(Antigout agent)。

裁决理由：问题问起始量和日上限，原key只含起始及增量；扩至同时含100mg/日与800mg上限的连续两句，不改写源文增量措辞。

**key_text**

原值：初始劑量:口服,100mg,一天一次,在一星期的間隔期間每天增加100mg

新值：初始劑量:口服,100mg,一天一次,在一星期的間隔期間每天增加100mg 直到達到所需要的血清尿酸濃度為止。不得超過每日800mg 之最大建議劑量

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0021 — OK

来源：`/sources/f80b904f4e2f15a59cb78fe1baed5c1c06b8b975d43dc0291217d64c43e43fbb.pdf`，物理第1页；章节：警語及注意之事項。

裁决理由：“应避免同用esomeprazole和clopidogrel”与问题一致；保留源文的推荐强度及交叉引用。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0022 — REVISE

来源：`/sources/f80b904f4e2f15a59cb78fe1baed5c1c06b8b975d43dc0291217d64c43e43fbb.pdf`，物理第1页；章节：用法用量－Zollinger Ellison Syndrome (ZES) 之治…。

裁决理由：原key的“起始”重复来自重叠文字层；从最后一个“起始”取连续、唯一的“起始剂量”子串，不再携带重复词。span补至首个完整句末，保留文字层重复而不伪造norm-v1已修复；另在审校记录提供视觉转写。

**key_text**

原值：建議起始起始起始起始劑量為服用 Esomeprazole 40mg 每日 2次

新值：起始劑量為服用 Esomeprazole 40mg 每日 2次

**evidence_span**

原值：Zollinger Ellison Syndrome (ZES) 之治療之治療之治療之治療建議起始起始起始起始劑量為服用 Esomeprazole 40mg 每日 2次,然後再依個別情況調整劑量,並視臨床表徵決定是否需繼續治療。根據臨床試驗結果所示,每日服用 80 至 160mg esomeprazole ,大部分病人…

新值：建議起始起始起始起始劑量為服用Esomeprazole 40mg 每日2 次,然後再依個別情況調整劑量,並視臨床表徵決定是否需繼續治療。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0023 — REVISE

来源：`/sources_staging/70d3d976a3b4ef70d192755440066618dd538d1bdf16659daa255b6f04dcaa81.pdf`，物理第1页；章节：【劑量及給藥法】。

裁决理由：原key在同页“糜烂性食道炎”和“预防再出血”两处出现；加入适应症作为最短的有效区分，不利用空格差异区分。 补齐问题或关键证据实际涉及的切片：drug_name_zh, time_window。

**key_text**

原值：40mg每天1次,為期4週

新值：糜爛性逆流性食道炎之治療:40mg每天1次,為期4週

**slices**

原值：dose_unit, mixed_zh_en

新值：dose_unit, mixed_zh_en, drug_name_zh, time_window

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0024 — REVISE

来源：`/sources_staging/70d3d976a3b4ef70d192755440066618dd538d1bdf16659daa255b6f04dcaa81.pdf`，物理第1页；章节：【禁忌】。

裁决理由：不可与nelfinavir併用的完整句与所问一致，不混为另一商品。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0025 — REVISE

来源：`/sources_staging/70d3d976a3b4ef70d192755440066618dd538d1bdf16659daa255b6f04dcaa81.pdf`，物理第1页；章节：【劑量及給藥法】肝功能不良。

裁决理由：补商品名锁定怡胃适；key保留严重肝功能不良条件，而不是一般病人通用20mg上限。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：esomeprazole用於肝功能嚴重不良的病人時，最高使用劑量限制為何？

新值：怡胃適腸溶錠（esomeprazole）用於肝功能嚴重不良的病人時，最高使用劑量限制為何？

**key_text**

原值：Esomeprazole的最高使用劑量不應超過20 mg

新值：肝功能嚴重不良的病人,Esomeprazole的最高使用劑量不應超過20 mg

**slices**

原值：dose_unit, negation, mixed_zh_en

新值：dose_unit, negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0026 — REVISE

来源：`/sources_staging/70d3d976a3b4ef70d192755440066618dd538d1bdf16659daa255b6f04dcaa81.pdf`，物理第1页；章节：警語及注意之事項－低血鎂症。

裁决理由：“通常多久之后才会”暗示确定发作时间，超出通报资料；改问这些通报中的用药时长，且key同时包含低血镁这一结局。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：長期使用PPI類藥品(如esomeprazole)可能出現低血鎂症，通常在使用多久之後才會出現此不良反應？

新值：怡胃適仿單提到的PPI相關低血鎂通報中，病人在使用PPI類藥品至少多久後出現反應，而大部分案件的用藥時間為多久？

**key_text**

原值：長期使用PPI類成分藥品(至少使用3個月,大部分在使用1年以上)

新值：曾有通報案件顯示,當長期使用PPI類成分藥品(至少使用3個月,大部分在使用1年以上),可能出現罕見低血鎂之不良反應

**slices**

原值：time_window, mixed_zh_en

新值：time_window, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0027 — DROP

来源：`/sources_staging/b1756268da31c9205cea8766181345921bdbec9c1930137428c79c5c3d8729f7.pdf`，物理第1页；章节：ĪϡڱĆϡณī。

裁决理由：PDF页面图像可读，但草稿key/span为大段字体编码乱码，部分还缺字；不在这种norm-v1表示上确认文本gold。应先修复抽取、以繁体重写问题、重锚定并复核后再入集。不能只删掉机械告警对应的标签来使样本过关。

保留原行用于审计，但不建议进入冻结集；修复文本抽取后重新起草与锚定。

自审：PDF身份/哈希/物理页/页面图像已核查；不批准乱码gold。

### ms-0028 — DROP

来源：`/sources_staging/b1756268da31c9205cea8766181345921bdbec9c1930137428c79c5c3d8729f7.pdf`，物理第2页；章节：Ī༰ԟাī。

裁决理由：PDF页面图像可读，但草稿key/span为大段字体编码乱码，部分还缺字；不在这种norm-v1表示上确认文本gold。应先修复抽取、以繁体重写问题、重锚定并复核后再入集。不能只删掉机械告警对应的标签来使样本过关。

保留原行用于审计，但不建议进入冻结集；修复文本抽取后重新起草与锚定。

自审：PDF身份/哈希/物理页/页面图像已核查；不批准乱码gold。

### ms-0029 — DROP

来源：`/sources_staging/b1756268da31c9205cea8766181345921bdbec9c1930137428c79c5c3d8729f7.pdf`，物理第1页；章节：Īڦຍְีī。

裁决理由：PDF页面图像可读，但草稿key/span为大段字体编码乱码，部分还缺字；不在这种norm-v1表示上确认文本gold。应先修复抽取、以繁体重写问题、重锚定并复核后再入集。不能只删掉机械告警对应的标签来使样本过关。

保留原行用于审计，但不建议进入冻结集；修复文本抽取后重新起草与锚定。

自审：PDF身份/哈希/物理页/页面图像已核查；不批准乱码gold。

### ms-0030 — REVISE

来源：`/sources_staging/c59161e8c6b42e149351ccc8c1d5ca8337627fa490861e6fb7dceb2bbca13f36.pdf`，物理第1页；章节：劑量及用法。

裁决理由：体液缺乏及高剂量利尿剂条件明确，25mg每日一次和“需考虑”强度正确。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：dose_unit, mixed_zh_en

新值：dose_unit, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0031 — REVISE

来源：`/sources_staging/c59161e8c6b42e149351ccc8c1d5ca8337627fa490861e6fb7dceb2bbca13f36.pdf`，物理第1页；章节：禁忌症〈依文獻記載〉。

裁决理由：问题只问糖尿病，key截到完整的糖尿病禁用命题即可，不必把另一分支肾功能阈值塞进key；完整span保留两分支。

**key_text**

原值：Losartan potassium 與 aliskiren 不可合併使用於糖尿病病人或腎功能不全病人(GFR<60 ml/min/1.73 m²)

新值：Losartan potassium 與 aliskiren 不可合併使用於糖尿病病人

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0032 — REVISE

来源：`/sources_staging/c59161e8c6b42e149351ccc8c1d5ca8337627fa490861e6fb7dceb2bbca13f36.pdf`，物理第1页；章节：小兒之使用〈依文獻記載〉。

裁决理由：新生儿/儿科肾小球过滤率是适用人群条件，不是药物剂量；保留“不建议”而不是改成未限定人群的禁用。 删除不符合本轮操作口径的切片：dose_unit。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, dose_unit, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0033 — REVISE

来源：`/sources_staging/c59161e8c6b42e149351ccc8c1d5ca8337627fa490861e6fb7dceb2bbca13f36.pdf`，物理第2页；章节：藥物過量〈依文獻記載〉。

裁决理由：losartan及活性代谢物两者、均无法透析排除完整保留。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0034 — REVISE

来源：`/sources_staging/8988edefb2825b18a9d5ebdb53b6f3bd09b7b75410d24814dd8f5ee2c8c7dfe7.pdf`，物理第2页；章节：用法用量(一般成人及青少年劑量-抗痛風劑Antigout agent)。

裁决理由：起始量与最大量都是问题要求；key扩至源文连续两句，不能只留下800mg。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：不得超過每日 800mg 之最大建議劑量

新值：初始劑量─口服,100mg,一天一次,在一星期的間隔期間每天增加 100mg 直到達到所需要的血清尿酸濃度為止。不得超過每日 800mg 之最大建議劑量

**slices**

原值：dose_unit, negation

新值：dose_unit, negation, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0035 — OK

来源：`/sources_staging/8988edefb2825b18a9d5ebdb53b6f3bd09b7b75410d24814dd8f5ee2c8c7dfe7.pdf`，物理第9页；章节：【保存條件】。

裁决理由：紧密容器、室温、避光三项保存条件完整，单位/温度未被臆造。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0036 — REVISE

来源：`/sources_staging/8988edefb2825b18a9d5ebdb53b6f3bd09b7b75410d24814dd8f5ee2c8c7dfe7.pdf`，物理第2页；章节：【適應症】慢性痛風性關節炎(Chronic Gouty arthritis)[治…。

裁决理由：补全Allopurinol先行词，完整保留缺乏抗炎效力及不用于急性发作的两句。 补齐问题或关键证据实际涉及的切片：drug_name_zh, mixed_zh_en。

**key_text**

原值：它必須不得使用於痛風性關節炎的急性發作

新值：Allopurinol 沒有抗發炎的效力。它必須不得使用於痛風性關節炎的急性發作

**slices**

原值：negation

新值：negation, drug_name_zh, mixed_zh_en

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0037 — REVISE

来源：`/sources_staging/8988edefb2825b18a9d5ebdb53b6f3bd09b7b75410d24814dd8f5ee2c8c7dfe7.pdf`，物理第3页；章节：用法用量(贅瘤疾病治療Neoplastic disease therapy)。

裁决理由：本段属于一般成人及青少年用量，不是儿童肿瘤高尿酸血症用量；问题明确成人，保留最好2–3天及600–800mg。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：「安星」伊風柔錠300毫克用於預防化學治療或放射治療所致高尿酸血症時，應在治療開始前多久給藥，劑量為何？

新值：「安星」伊風柔錠300毫克用於成人預防化學治療或放射治療所致高尿酸血症時，應在治療開始前多久給藥，劑量為何？

**slices**

原值：dose_unit, time_window

新值：dose_unit, time_window, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0038 — OK

来源：`/sources_staging/ad8b0ba2d6c9421349f86080b4a35218088fb6895493ae13fbb3aa32f0fd7ae2.pdf`，物理第2页；章节：2.1 一般給藥的顧慮。

裁决理由：机械告警为漏检：原文“不要再开始使用”是否定；未从外部资料添加本文件不存在的复药例外。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0039 — REVISE

来源：`/sources_staging/ad8b0ba2d6c9421349f86080b4a35218088fb6895493ae13fbb3aa32f0fd7ae2.pdf`，物理第3页；章节：2.1 一般給藥的顧慮／停藥對策。

裁决理由：Markdown截断恰好隐藏安全原因需更快减量的例外；补齐整句，key保留常规减量及例外，不能写成无条件至少2周。 补齐问题或关键证据实际涉及的切片：drug_name_zh, negation。

**key_text**

原值：建議採取至少 2 周的逐步減少劑量 ( 每週將近 50%)

新值：建議採取至少2 周的逐步減少劑量( 每週將近50%),除非基於安全的考量而須採取更快速的減量

**evidence_span**

原值：如果病情控制有變化或是出現不良反應的惡化時,對於將 Lamofree ER Tablets 與其他 AEDs 合併使用治療之病人,需對其所有的 AEDs 藥物進行再次評估,假使已經決定停止使用 Lamofree ER Tablets 的話,建議採取至少 2 周的逐步減少劑量 ( 每週將近 50%),除非基於安全的考量而…

新值：如果病情控制有變化或是出現不良反應的惡化時,對於將Lamofree ER Tablets 與其他AEDs 合併使用治療之病人,需對其所有的 AEDs 藥物進行再次評估,假使已經決定停止使用Lamofree ER Tablets 的話,建議採取至少2 周的逐步減少劑量( 每週將近50%),除非基於安全的考量而須採取更快速的減量[ 參閱警告與注意事項(5.9)]。

**slices**

原值：dose_unit, time_window, mixed_zh_en

新值：dose_unit, time_window, mixed_zh_en, drug_name_zh, negation

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0040 — OK

来源：`/sources_staging/ad8b0ba2d6c9421349f86080b4a35218088fb6895493ae13fbb3aa32f0fd7ae2.pdf`，物理第4页；章节：4 禁忌症。

裁决理由：过敏人群与禁止使用谓语齐全，示例及参阅括号完整。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0041 — REVISE

来源：`/sources_staging/ad8b0ba2d6c9421349f86080b4a35218088fb6895493ae13fbb3aa32f0fd7ae2.pdf`，物理第9页；章节：8.6 肝功能不全的病患。

裁决理由：第9物理页8.6节与第3物理页有等义重复建议；限定8.6节而非混用印刷页。B级约50%、C级75%、依临床反应调整均保留。

**query**

原值：中度或重度肝功能不全(Child-Pugh Grade B/C)的病患使用樂癲活持續釋放膜衣錠時，起始及維持劑量應如何調整？

新值：依樂癲活持續釋放膜衣錠仿單第8.6節，中度或重度肝功能不全（Child-Pugh Grade B/C）病患的起始及維持劑量應如何調整？

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0042 — REVISE

来源：`/sources_staging/cb1abe12731f9292a0a49937fb33ba1fe79e1e775883af4be74741c5eaf978ce.pdf`，物理第1页；章节：用法用量。

裁决理由：原span截在单次剂量，遗漏非紧急/毒性风险高者分次的限定；补齐快速负荷段并避免把可单次方案说成人人适用。

**query**

原值：成人及10歲以上兒童使用隆我心錠進行快速口服負荷量給藥時,建議一次給予多少劑量?

新值：隆我心錠仿單在「成人及10歲以上兒童／快速口服負荷量」段落中，列出的單次給藥劑量範圍為何？

**evidence_span**

原值：成人及 10 歲以上兒童快速口服負荷量:以下列方式正確用藥,病人可快速被毛地黃化(digitalisation ):一次給藥 750 至 1500 微毫克(μg)(0.75~1.5 毫克)。

新值：成人及10 歲以上兒童快速口服負荷量: 以下列方式正確用藥,病人可快速被毛地黃化(digitalisation): 一次給藥750 至1500 微毫克(μg)(0.75~1.5 毫克)。 當情況較不緊急,或毒性危險性較高時,例如老年人,則口服負荷量應分次給藥,間隔6 小時,第一次約給予全部劑量的一半。 每再給藥一次額外劑量時,皆需評估臨床反應(參考警告與注意事項)。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0043 — REVISE

来源：`/sources_staging/cb1abe12731f9292a0a49937fb33ba1fe79e1e775883af4be74741c5eaf978ce.pdf`，物理第2页；章节：禁忌症。

裁决理由：当前所问可由第二个完整条件句独立回答；去除前面依赖列表标题的另一分支，避免读者将其例外错误套到本问题。

**evidence_span**

原值：伴有副房室路徑之上心室性心律不整,例如 Wolff-Parkinson-White 症候群,除非曾評估過該副路徑之電生理特性及 digoxin 對這類特性可能造成之有害作用。若已知或懷疑存在副路徑而無上心室性心律不整病史,同樣也禁用 LANOXIN。

新值：若已知或懷疑存在副路徑而無上心室性心律不整病史,同樣也禁用 LANOXIN。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0044 — OK

来源：`/sources_staging/cb1abe12731f9292a0a49937fb33ba1fe79e1e775883af4be74741c5eaf978ce.pdf`，物理第3页；章节：警語和注意事項-直流電心臟電擊。

裁决理由：限定选择性而非急救直流电击；24小时停药句完整。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0045 — OK

来源：`/sources_staging/cb1abe12731f9292a0a49937fb33ba1fe79e1e775883af4be74741c5eaf978ce.pdf`，物理第2页；章节：用法用量-老年人。

裁决理由：比较对象为非老年人，建议较低剂量；不从定性调整推出具体数值。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0046 — REVISE

来源：`/sources/b6af0d88b1f0e3b5660e6e3c6678e18c40616073bc082b6cb7214604b2f81f98.pdf`，物理第1页；章节：警語與注意事項。

裁决理由：机械告警成立：应停止服药是正向动作；“非急需”是手术类型，不据此把整条当成否定用药题；不混入显影剂48小时规则。 删除不符合本轮操作口径的切片：negation。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：time_window, negation, mixed_zh_en

新值：time_window, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0047 — REVISE

来源：`/sources/b6af0d88b1f0e3b5660e6e3c6678e18c40616073bc082b6cb7214604b2f81f98.pdf`，物理第1页；章节：用法用量。

裁决理由：“通常”是一般用量限定，应保留在key内；频次二次与每次一锭完整，不用另一规格折算替换本条。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：每日服用二次,每次服用一錠

新值：通常,每日服用二次,每次服用一錠

**slices**

原值：dose_unit

新值：dose_unit, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0048 — REVISE

来源：`/sources_staging/3981295da5a68ef3bf43b30c4d7783b9ebfa351319c134bb2f5710a11ac14d5b.pdf`，物理第1页；章节：劑量及用法。

裁决理由：已限定高血压一般剂量；query只有英文商品名Losacar，不应因文件标题有中文就贴drug_name_zh。 删除不符合本轮操作口径的切片：drug_name_zh。

**slices**

原值：drug_name_zh, dose_unit, mixed_zh_en

新值：dose_unit, mixed_zh_en

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0049 — REVISE

来源：`/sources_staging/3981295da5a68ef3bf43b30c4d7783b9ebfa351319c134bb2f5710a11ac14d5b.pdf`，物理第1页；章节：劑量及用法。

裁决理由：key漏掉可增加至100mg的第二要点；源文未把它明确叫“绝对最大剂量”，问题改成可增加至的剂量。 删除不符合本轮操作口径的切片：drug_name_zh。

**query**

原值：Losacar用於治療第II型糖尿病腎病變時的起始劑量及可調整之最大劑量為何?

新值：Losacar用於治療第II型糖尿病腎病變時，起始劑量為何，並可視血壓下降情形增加至多少？

**key_text**

原值：治療第 II 型糖尿病腎病變一般起始劑量為每次 50 毫克,每日一次

新值：治療第 II 型糖尿病腎病變一般起始劑量為每次 50 毫克,每日一次。視血壓下降情形,可將劑量增加至每次 100 毫克,每日一次

**slices**

原值：drug_name_zh, dose_unit, mixed_zh_en

新值：dose_unit, mixed_zh_en

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0050 — REVISE

来源：`/sources_staging/3981295da5a68ef3bf43b30c4d7783b9ebfa351319c134bb2f5710a11ac14d5b.pdf`，物理第1页；章节：禁忌症〈依文獻記載〉。

裁决理由：问题补GFR<60条件，不能推广到所有肾功能不全。原key为禁忌列表项却不含禁止谓语，加入“禁忌症”标题及中间原文以保留连续锚点。 删除不符合本轮操作口径的切片：drug_name_zh。

**query**

原值：Losacar是否禁止與含aliskiren成分藥品合併使用於糖尿病患或腎功能不全患者?

新值：Losacar仿單「禁忌症」所列的糖尿病患，或GFR低於60 ml/min/1.73 m²的腎功能不全患者，是否可合併使用含aliskiren成分的藥品？

**key_text**

原值：合併使用本品及含 aliskiren 成分藥品於糖尿病患或腎功能不全患者 (GFR<60 ml/min/1.73 m2)

新值：禁忌症〈依文獻記載〉 Losartan potassium 禁用於對本項產品任何組成過敏者。 合併使用本品及含aliskiren 成分藥品於糖尿病患或腎功能不全患者(GFR<60 ml/min/1.73 m2)

**evidence_span**

原值：Losartan potassium 禁用於對本項產品任何組成過敏者。合併使用本品及含 aliskiren 成分藥品於糖尿病患或腎功能不全患者 (GFR<60 ml/min/1.73 m2)。

新值：禁忌症〈依文獻記載〉 Losartan potassium 禁用於對本項產品任何組成過敏者。 合併使用本品及含aliskiren 成分藥品於糖尿病患或腎功能不全患者(GFR<60 ml/min/1.73 m2)。

**slices**

原值：drug_name_zh, negation, mixed_zh_en

新值：negation, mixed_zh_en

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0051 — REVISE

来源：`/sources_staging/3981295da5a68ef3bf43b30c4d7783b9ebfa351319c134bb2f5710a11ac14d5b.pdf`，物理第1页；章节：警語及注意事項〈依文獻記載〉。

裁决理由：保留不建议及必要时监测的例外。源文字层“今aliskiren”不擅改为“含”；可读语义以页面为准，原字符串留作锚定。 删除不符合本轮操作口径的切片：drug_name_zh。

**slices**

原值：drug_name_zh, negation, mixed_zh_en

新值：negation, mixed_zh_en

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0052 — REVISE

来源：`/sources_staging/0879f3f5e1a1b31a420dddc8510817aee8b57abe074ab656de7fc7da2afe5d4c.pdf`，物理第1页；章节：用法用量。

裁决理由：只问每日范围，key截到10–40mg即可；源文“分依次”不擅自修成“一次”，保留span并标记原文疑似错字。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：每日常用劑量範圍為:10~40mg,分依次或兩次服用

新值：每日常用劑量範圍為:10~40mg

**slices**

原值：dose_unit

新值：dose_unit, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0053 — REVISE

来源：`/sources_staging/0879f3f5e1a1b31a420dddc8510817aee8b57abe074ab656de7fc7da2afe5d4c.pdf`，物理第1页；章节：禁忌症。

裁决理由：原key只列成分过敏，漏ACE抑制剂相关血管神经性水肿病史；扩为同一完整禁忌句。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：PERISAFE禁用於對該品任何成分過敏的病人

新值：PERISAFE禁用於對該品任何成分過敏的病人,及以前曾有過以升壓素轉化酵素抑制劑治療而引起血管神經性水腫之病史者

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0054 — REVISE

来源：`/sources_staging/0879f3f5e1a1b31a420dddc8510817aee8b57abe074ab656de7fc7da2afe5d4c.pdf`，物理第4页；章节：藥物過量。

裁决理由：药物过量场景及约6小时的不确定界限均正确，不解读为普通用药的起效时间。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：time_window

新值：time_window, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0055 — REVISE

来源：`/sources_staging/4c21c14e2cedd67e401aedf2f678a9fceaf9d3935751cb19d40bf62117c89dd9.pdf`，物理第2页；章节：用法用量。

裁决理由：“初始剂量的每日最大”混淆初始100mg和逐步滴定上限；改问抗痛风治疗最大建议日量。

**query**

原值：拔痛酸錠(Allopurinol)作為抗痛風劑使用時,初始劑量的每日最大建議劑量是多少?不得超過多少mg?

新值：拔痛酸錠（Allopurinol）仿單的抗痛風劑起始治療條款，規定逐步調整時的每日最大建議劑量是多少？

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0056 — REVISE

来源：`/sources_staging/4c21c14e2cedd67e401aedf2f678a9fceaf9d3935751cb19d40bf62117c89dd9.pdf`，物理第1页；章节：臨床藥理。

裁决理由：key补“通常”，避免把1–2周恢复写成所有病人的必然时限；问题同步保留该限定。

**query**

原值：服用拔痛酸錠(Allopurinol)後,停止治療多久血清尿酸濃度會回復到治療前的數值?

新值：停止使用拔痛酸錠（Allopurinol）治療後，血清尿酸濃度通常多久會回復到治療前的數值？

**key_text**

原值：治療停止之後的 1 至 2 週,血清尿酸濃度會回復到治療前的數值

新值：通常在治療停止之後的 1 至 2 週,血清尿酸濃度會回復到治療前的數值

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0057 — REVISE

来源：`/sources_staging/4c21c14e2cedd67e401aedf2f678a9fceaf9d3935751cb19d40bf62117c89dd9.pdf`，物理第2页；章节：適應症。

裁决理由：补上Allopurinol先行词，避免孤立“它”而丢失药品对象；不引用痛风停或伊风柔同成分仿单替代。

**key_text**

原值：它必須不得使用於痛風性關節炎的急性發作

新值：Allopurinol 沒有抗發炎的效力。它必須不得使用於痛風性關節炎的急性發作

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0058 — REVISE

来源：`/sources_staging/4c21c14e2cedd67e401aedf2f678a9fceaf9d3935751cb19d40bf62117c89dd9.pdf`，物理第3页；章节：一般孩童劑量。

裁决理由：第3页儿科/肿瘤相关高尿酸血症章节已核对；不把相邻低龄剂量引入本条，span补48小时后按反应调整的注意。

**evidence_span**

原值：年齡 6 至 12 歲的孩童:口服,100 mg,一天三次;或 300 mg 當作一個單一劑量,一天一次。

新值：年齡6 至12 歲的孩童:口服,100 mg,一天三次;或300 mg 當作一個單一劑量,一天一次。 注意—大約在治療48 小時之後,劑量的調整可能是必需的,依病人的反應而定。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0059 — REVISE

来源：`/sources_staging/6e54ef6f412df596ff6b2e1fe58aabbedde6264cdcb2028c322852370015f4e7.pdf`，物理第1页；章节：3.2 老年人。

裁决理由：老年人每日25mg和后续递增在完整段落；与成人首四天方案区分。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：dose_unit, mixed_zh_en

新值：dose_unit, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0060 — REVISE

来源：`/sources_staging/6e54ef6f412df596ff6b2e1fe58aabbedde6264cdcb2028c322852370015f4e7.pdf`，物理第1页；章节：3.3 孩童及青少年。

裁决理由：问题问核准状态，key补本品“未核准”而不只用“不适用”来间接推导；限定第3.3节，以区别第18页8.4节的等义重复条款。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：喜樂平（Quetiapine）是否核准使用於18歲以下的兒童及青少年？

新值：依喜樂平（Quetiapine）仿單第3.3節，是否核准本品使用於18歲以下的兒童及青少年？

**key_text**

原值：Quetiapine 不適用於 18 歲以下的兒童及青少年

新值：本品未核准使用於兒童及青少年。Quetiapine 不適用於 18 歲以下的兒童及青少年

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0061 — REVISE

来源：`/sources_staging/6e54ef6f412df596ff6b2e1fe58aabbedde6264cdcb2028c322852370015f4e7.pdf`，物理第7页；章节：5.13 QT 期間延長。

裁决理由：原key只覆盖1A类，span在其他药物列表中途截断；保留原问题，补齐全部所列药物类别和例子，不缩题掩盖遗漏。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：Quetiapine 應避免與其他會延長 QT 的藥物併用,包括 1A 類抗心律不整藥

新值：Quetiapine 應避免與其他會延長 QT 的藥物併用,包括 1A 類抗心律不整藥(例如 Quinidine, Procainamide)或 III 類抗心律不整藥(例如 Amiodarone, Sotalol),抗精神病藥物(例如 Ziprasidone, Chlorpromazine, Thioridazine),抗生素(例如 Gatifloxacin, Moxifloxacin),或其他會延長 QT 期間的藥物類別(例如 Pentamidine,Levomethadyl acetate, Methadone)

**evidence_span**

原值：Quetiapine 應避免與其他會延長 QT 的藥物併用,包括 1A 類抗心律不整藥(例如 Quinidine, Procainamide)或 III 類抗心律不整藥(例如 Amiodarone, Sotalol),抗精神病藥物(例如 Ziprasidone, Chlorpromazine, Thioridazine…

新值：Quetiapine 應避免與其他會延長 QT 的藥物併用,包括 1A 類抗心律不整藥(例如 Quinidine, Procainamide)或 III 類抗心律不整藥(例如 Amiodarone, Sotalol),抗精神病藥物(例如 Ziprasidone, Chlorpromazine, Thioridazine),抗生素(例如 Gatifloxacin, Moxifloxacin),或其他會延長 QT 期間的藥物類別(例如 Pentamidine,Levomethadyl acetate, Methadone)。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0062 — REVISE

来源：`/sources_staging/6e54ef6f412df596ff6b2e1fe58aabbedde6264cdcb2028c322852370015f4e7.pdf`，物理第18页；章节：8.3 授乳婦。

裁决理由：机械告警为漏检：“不要餵母奶”明确否定，保留negation。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0063 — OK

来源：`/sources_staging/0c80faec13d3404834be06c3212ccdf81b5e63af80064009d93106ecca47f293.pdf`，物理第1页；章节：用法用量。

裁决理由：成人及十二岁（含）以上、每日两茶匙和10mg同时保留；未自行增加mL换算。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0064 — OK

来源：`/sources_staging/0c80faec13d3404834be06c3212ccdf81b5e63af80064009d93106ecca47f293.pdf`，物理第1页；章节：禁忌。

裁决理由：机械告警为漏检：“皆不適合投以本劑”明确不适用，保留negation。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0065 — REVISE

来源：`/sources_staging/0c80faec13d3404834be06c3212ccdf81b5e63af80064009d93106ecca47f293.pdf`，物理第1页；章节：藥物交互作用。

裁决理由：机械告警成立：48小时前起应停用属于正向停药指令，删除negation；保留skin test及时间。 删除不符合本轮操作口径的切片：negation。

**slices**

原值：negation, time_window, drug_name_zh, mixed_zh_en

新值：time_window, drug_name_zh, mixed_zh_en

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0066 — REVISE

来源：`/sources_staging/0e8e316abd1fcd16b0890516b340fa47311dea7e2fb8313e625db1e4fb1150d1.pdf`，物理第1页；章节：用法用量。

裁决理由：用药方式不仅包含深部缓慢肌注，还包括左右臀部交替；key覆盖所问完整方式并保留“通常”。

**key_text**

原值：成人一次 75 mg ,一日一次,行外側臀部肌肉深部緩慢注射之

新值：通常成人一次 75 mg ,一日一次,行外側臀部肌肉深部緩慢注射之,並應時常改換左右臀部注射部位

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0067 — REVISE

来源：`/sources_staging/0e8e316abd1fcd16b0890516b340fa47311dea7e2fb8313e625db1e4fb1150d1.pdf`，物理第1页；章节：首頁心血管栓塞事件警示，第2項。

裁决理由：同页有两处相同禁用文字，不能依赖空格区别。选择首页心血管栓塞警示第2项，key/span加入原项目号，问题限定该警示。

**query**

原值：賜痛寧注射液(diclofenac)在病人做完冠狀動脈繞道手術(CABG)後,術後多久內禁止使用?

新值：依賜痛寧注射液（diclofenac）仿單首頁的「心血管栓塞事件」警示，冠狀動脈繞道手術（CABG）後多久內禁用本藥？

**key_text**

原值：進行冠狀動脈繞道手術 (Coronary artery bypass graft, CABG) 之後 14 天內禁用本藥

新值：2. 進行冠狀動脈繞道手術 (Coronary artery bypass graft, CABG) 之後 14天內禁用本藥

**evidence_span**

原值：進行冠狀動脈繞道手術 (Coronary artery bypass graft, CABG) 之後 14 天內禁用本藥。

新值：2. 進行冠狀動脈繞道手術 (Coronary artery bypass graft, CABG) 之後 14天內禁用本藥。

**section**

原值：心血管栓塞事件

新值：首頁心血管栓塞事件警示，第2項

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0068 — REVISE

来源：`/sources_staging/0e8e316abd1fcd16b0890516b340fa47311dea7e2fb8313e625db1e4fb1150d1.pdf`，物理第1页；章节：適應症。

裁决理由：合并重复发问；“无法口服”是不可丢失的适用条件，补否定切片。 补齐问题或关键证据实际涉及的切片：negation。

**query**

原值：賜痛寧注射液(diclofenac)的核准適應症為何?適用於什麼情況下的病人?

新值：賜痛寧注射液（diclofenac）仿單所列的適應症及適用情況為何？

**slices**

原值：drug_name_zh, mixed_zh_en

新值：drug_name_zh, mixed_zh_en, negation

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0069 — OK

来源：`/sources_staging/0e8e316abd1fcd16b0890516b340fa47311dea7e2fb8313e625db1e4fb1150d1.pdf`，物理第2页；章节：儲藏。

裁决理由：25°C以下和阴凉完整；储存温度不是dose_unit。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0070 — REVISE

来源：`/sources_staging/4c211906545934a9ea4a41ce0cdaeed1ce9d882da06b7e5fd376d50f4a94d794.pdf`，物理第1页；章节：血管性水腫病人。

裁决理由：原题“临床上该如何处置”可能涵盖急救等源文未答事项；限定为是否继续或再次使用本药。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：衛欣保（valsartan）病人若出現血管性水腫，臨床上該如何處置？

新值：使用衛欣保（valsartan）後若出現血管性水腫，是否應繼續用藥，以及日後能否再次使用？

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0071 — REVISE

来源：`/sources_staging/4c211906545934a9ea4a41ce0cdaeed1ce9d882da06b7e5fd376d50f4a94d794.pdf`，物理第1页；章节：心肌梗塞。

裁决理由：合为一问并保留药名先行词；key覆盖最早12小时和20mg每日两次，不把起始量混成后续目标量。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：衛欣保（valsartan）用於心肌梗塞後病人，最早可於何時開始給藥？起始劑量為何？

新值：衛欣保（valsartan）仿單對心肌梗塞後用藥所列的最早開始時間與起始劑量為何？

**key_text**

原值：心肌梗塞12小時後即開始進行治療。以 20mg每日兩次的初步劑量治療

新值：Valsartan可儘早於心肌梗塞12小時後即開始進行治療。以20mg每日兩次的初步劑量治療

**slices**

原值：dose_unit, time_window, mixed_zh_en

新值：dose_unit, time_window, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0072 — REVISE

来源：`/sources_staging/4c211906545934a9ea4a41ce0cdaeed1ce9d882da06b7e5fd376d50f4a94d794.pdf`，物理第1页；章节：高血壓。

裁决理由：问题及所属标题明确成人高血压，key补Valsartan对象；不引用同页心衰竭40mg每日两次方案。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：每天一次,每次80mg或 160mg

新值：Valsartan建議使用劑量為(每天一次,每次80mg或160mg)

**slices**

原值：dose_unit, mixed_zh_en

新值：dose_unit, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0073 — REVISE

来源：`/sources_staging/4c211906545934a9ea4a41ce0cdaeed1ce9d882da06b7e5fd376d50f4a94d794.pdf`，物理第1页；章节：雙重阻斷腎素―血管昇壓素―醛固酮系統 (renin- angiotensin-a…。

裁决理由：不建议双重阻断与必要时监测的原文完整；不把一般不建议升级为所有情形绝对禁用。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0074 — REVISE

来源：`/sources_staging/3b1d0b7fb71d65e81493f10a46bb1640d2a5635e70621a5e6a38867d8f65aab3.pdf`，物理第1页；章节：用法用量。

裁决理由：只问量与频次，key缩到通常成人75mg每日一次即可；完整span仍保留注射方式及最低量最短疗程原则。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：通常成人一次 75mg,一日一次,行外側臀部肌肉深部緩慢注射之

新值：通常成人一次 75mg,一日一次

**slices**

原值：dose_unit

新值：dose_unit, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0075 — REVISE

来源：`/sources_staging/3b1d0b7fb71d65e81493f10a46bb1640d2a5635e70621a5e6a38867d8f65aab3.pdf`，物理第1页；章节：【禁忌】第7項。

裁决理由：同页第2项警示与第7项禁忌的key重复；用禁忌第7项的项目号和限定问题来明确所选锚点，不以空白差异制造唯一性。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：病人剛完成冠狀動脈繞道手術(CABG),術後多久內禁止使用免痛注射液(待克菲那)?

新值：依免痛注射液（待克菲那）仿單的「禁忌」條款，冠狀動脈繞道手術（CABG）後多久內禁止使用本藥？

**key_text**

原值：進行冠狀動脈繞道手術 (Coronary artery bypass graft, CABG) 之後 14 天內禁用本藥

新值：7.進行冠狀動脈繞道手術 (Coronary artery bypass graft, CABG) 之後14 天內禁用本藥

**evidence_span**

原值：進行冠狀動脈繞道手術 (Coronary artery bypass graft, CABG) 之後 14 天內禁用本藥。

新值：7.進行冠狀動脈繞道手術 (Coronary artery bypass graft, CABG) 之後14 天內禁用本藥。

**slices**

原值：negation, time_window, mixed_zh_en

新值：negation, time_window, mixed_zh_en, drug_name_zh

**section**

原值：禁忌

新值：【禁忌】第7項

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0076 — REVISE

来源：`/sources_staging/3b1d0b7fb71d65e81493f10a46bb1640d2a5635e70621a5e6a38867d8f65aab3.pdf`，物理第2页；章节：藥物交互作用。

裁决理由：一般不建议同时使用aspirin和diclofenac，完整保留风险理由，不误用aspirin过敏禁忌句。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0077 — REVISE

来源：`/sources_staging/3b1d0b7fb71d65e81493f10a46bb1640d2a5635e70621a5e6a38867d8f65aab3.pdf`，物理第1页；章节：警語(肝臟作用)。

裁决理由：源文为diclofenac长期治疗的监测警语，不授权长期使用该注射剂；改写问题避免这个预设，并将肝转氨酶对象放入key。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**query**

原值：長期使用免痛注射液(待克菲那,diclofenac)治療的病人,應於治療後何時檢測肝臟轉氨酶?

新值：免痛注射液仿單提到，長期接受diclofenac治療的病人，應在治療開始後哪個時間窗檢測肝臟轉氨酶？

**key_text**

原值：應於治療後的第4到第8週內進行檢測

新值：長期使用diclofenac治療的病人應定期檢測肝臟轉氨酶 (transaminase),依據臨床試驗數據和上市後經驗,應於治療後的第4到第8週內進行檢測

**slices**

原值：time_window, mixed_zh_en

新值：time_window, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0078 — REVISE

来源：`/sources_staging/c96703065f145c812f38466a545fe62d0dbe6c566d380892d1702a720dd6c1ce.pdf`，物理第1页；章节：用法、用量—化學治療或放射線治療引起之噁心及嘔吐(CINV與RINV)—肝功能不…。

裁决理由：key补中度或重度肝功能不全先行条件，避免孤立“这类病人”；仍使用CINV/RINV段，不换成同页PONV段。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：用於這類病人時,靜脈注射或口服的每日總劑量不可超過8毫克。

新值：中度或重度肝功能不全者的ondansetron 清除率顯著降低,血清半衰期顯著延長。用於這類病人時,靜脈注射或口服的每日總劑量不可超過8毫克。

**slices**

原值：dose_unit, negation, mixed_zh_en

新值：dose_unit, negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0079 — REVISE

来源：`/sources_staging/c96703065f145c812f38466a545fe62d0dbe6c566d380892d1702a720dd6c1ce.pdf`，物理第1页；章节：用法、用量—化學治療或放射線治療引起之噁心及嘔吐(CINV與RINV)—成人:致…。

裁决理由：原key仅答口服转换时间，漏初始注射8mg；扩至两句。按原文24小时之后表述，不赋予更精确、源文未写的计时零点。 补齐问题或关键证据实际涉及的切片：drug_name_zh, mixed_zh_en。

**query**

原值：成人接受致吐性化學治療時，莫尼茲注射劑靜脈或肌肉注射的建議起始劑量以及給藥後多久可改為口服給藥？

新值：莫尼茲注射劑仿單對成人「致吐性化學治療及放射線治療」所列的注射建議劑量，以及後續改用口服給藥的時間為何？

**key_text**

原值：24 小時之後,建議以口服方式給藥,以預防遲發性或長時間嘔吐。

新值：Ondansetron 的靜脈注射(IV)或肌肉注射(IM)建議劑量為 8 毫克,於即將進行治療之前緩慢注射給藥。 24 小時之後,建議以口服方式給藥,以預防遲發性或長時間嘔吐

**slices**

原值：dose_unit, time_window

新值：dose_unit, time_window, drug_name_zh, mixed_zh_en

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0080 — REVISE

来源：`/sources_staging/c96703065f145c812f38466a545fe62d0dbe6c566d380892d1702a720dd6c1ce.pdf`，物理第1页；章节：用法、用量—老年人:化學治療或放射治療引起之噁心嘔吐(CINV與RINV)。

裁决理由：原key漏追加给药间隔；扩到完整两句，保留年满75岁、起始不超过8mg、输注超过15分钟及间隔至少4小时。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**key_text**

原值：對年滿75歲或以上之病人,ondansetron 起始劑量不可超過8毫克,其輸注時間亦應超過 15分鐘。

新值：對年滿75歲或以上之病人,ondansetron 起始劑量不可超過8毫克,其輸注時間亦應超過 15分鐘。在此8 毫克之起始劑量後,可追加2 劑8毫克15分鐘以上之靜脈輸注,每劑間隔時間須至少4小時

**slices**

原值：dose_unit, negation, time_window, mixed_zh_en

新值：dose_unit, negation, time_window, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0081 — REVISE

来源：`/sources_staging/c96703065f145c812f38466a545fe62d0dbe6c566d380892d1702a720dd6c1ce.pdf`，物理第2页；章节：懷孕、泌乳、具生育能力之女性與男性—懷孕。

裁决理由：第一孕期而非所有孕期范围完整，原文“不应使用”保留。 补齐问题或关键证据实际涉及的切片：drug_name_zh。

**slices**

原值：negation, mixed_zh_en

新值：negation, mixed_zh_en, drug_name_zh

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0082 — OK

来源：`/sources/81069adaf87d21e640d9b5cbc83a799a59a33acbdc4ead46ed338c9ad6d06b3a.pdf`，物理第1页；章节：禁忌症。

裁决理由：本产品成分过敏与禁用匹配，未混用同页另一条aliskiren禁忌。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。

### ms-0083 — OK

来源：`/sources/81069adaf87d21e640d9b5cbc83a799a59a33acbdc4ead46ed338c9ad6d06b3a.pdf`，物理第1页；章节：劑量及用法。

裁决理由：第II型糖尿病肾病变标题、50mg和每日一次完整，未误取高血压同剂量条款。

query、key_text、span、切片及章节均保留。

自审：PDF身份/哈希/物理页/页面图像已核查；本地折叠 key=1、span=1，包含关系成立。norm-v1偏移仍待项目验证。
