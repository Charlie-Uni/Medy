# EN 批次逐条语言审校、父子依赖与来源自审记录

审校日期：2026-09-21  
审校身份：ChatGPT／AI辅助审校，不是 annotator-01 人工签署。  
状态：**main-v1-provisional；第二人工复核未完成。**

## 1. 结果与可交付范围

174条均已逐条检查英文问题及相关来源，并完成编辑后的反向定位自审。语言审校完成与整族可以验收是两个不同状态：**93条建议OK，76条待CO父版本确认，5条建议DROP。**

| 项目 | 结果 |
| --- | ---: |
| 输入英文孪生 | 174 |
| 英文问题更新（含展示截断重拟） | 94 |
| 英文问题保持 | 80 |
| 原英文单元格含展示省略号 | 26 |
| 与实际PV修订父快照对齐，建议OK | 93 |
| PENDING_PARENT：待父修订版本/迁移确认 | 76 |
| 建议DROP | 5 |
| 新拟中文父问题与英文配对建议（未写回） | 30 |
| PV父中文展示同步 | 35 |
| PV切片展示同步 | 34 |
| 源PDF | 46 |
| 草稿不同文档/物理页定位组合 | 159 |
| 完整PV父key/span本地定位核查 | 93 |
| 仅预览前缀定位核查（不是完整gold） | 81 |
| 实际查看的源页面图像 | 9 |
| 新增孪生ID／重挂父ID／仓库写回 | 0／0／未执行 |

94条英文更新包含对35个已修订PV父问题的同步、措辞/限定修正、来源明确及26个被截断问句的重拟，各类可能重叠，**不是原完整candidate JSON的错误率**。

### 输入版本锁定

| 输入 | SHA-256 |
| --- | --- |
| `/mnt/data/_en_work/EN_input_snapshot.txt` | `5c8d49276dd44b2da5262180c387abd5b396541181d092249abeae9f3daa8e0d` |
| `/mnt/data/samples_draft_PV.reviewed.md` | `7e08d2e3c7e3b50f3b01435e92e0c0e855cc6faa147b3a1e0e2c0f15f2ef6047` |
| `/mnt/data/PV_review_audit_2026-09-21.json` | `69759a302e15e07f49d50a04ffa1e4089df08d5e17bdade24790924c4b545727` |
| `/mnt/data/_en_work/co_original/粘贴的文本 (1).txt` | `66fbacb46f33644b11dbb96694e30596dfb96ab0e08e27522ee2b1394dc8ca1a` |
| `/mnt/data/sources_registry.json` | `e3c548d17817dfc2584a7a1bbf5f36f7f146d64b55cb47e680e1b450dccd7e67` |

PV修订Markdown与审校JSON已逐条交叉核对一致。CO上轮修订表、审校JSON及ZIP在本次运行环境中不存在，Files的会话/Library检索也未取得；已取得的是原CO草稿及原PDF。上轮可见裁决摘要可用于定位排除或迁移依赖，但不能替代完整父query/gold/slices快照。

## 2. 结论列与应用约束

**OK**：英文对齐到本次实际取得的PV父修订快照。该快照本身仍为AI建议，正式应用须人工确认并重算norm-v1。

**PENDING_PARENT**：CO最新父修订快照未取得，或父样本部门迁移尚未确认。语言修改建议和源PDF定位已完成；不意味着英文必然错误，也不意味着无答案。此状态是本审校包新增的阻断标记，不能送入未确认支持它的OK/DROP应用脚本。

**DROP**：建议在当前评测版本排除该孪生，原因见下表。不是删除源PDF，不是物理删除原表，也不是改成no_answer。

总表保留174条及9列。另有98条的` samples_draft_EN.decided.md `子表，仅包含93个OK与5个DROP，提供筛选便利，**不代表98条均可直接入库，更不是完整EN批次**。

## 3. 父样本删除与迁移的联动

| EN ID | 父样本 | 处理 | 原因 |
| --- | --- | --- | --- |
| ms-0196 | ms-0195 | DROP | 父ms-0195的Summary与Background清单跨物理18–19页；延续PV已审表的DROP。不是文档无答案。 |
| ms-0301 | ms-0300 | PENDING_PARENT | 父ms-0300此前仅建议CO→PV迁移；不得误作全局删除。本条保留英文方案，待确认父样本落入PV后整族同步。 |
| ms-0304 | ms-0303 | DROP | 父ms-0303所问完整1.4程序在物理19页仍有1.4.9；按上轮裁决及本轮原PDF重查建议排除当前单页gold。 |
| ms-0325 | ms-0324 | DROP | 父ms-0324来源为2024年12月草案，页文本有行号且原问题的设计措施跨物理11–12页；需重建父证据，而非只改英文。 |
| ms-0415 | ms-0414 | DROP | 父ms-0414与ms-0406为同文档同条款的重复问题；按上轮裁决建议排除0414及其本孪生。不自动重挂至0406。 |
| ms-0429 | ms-0428 | DROP | 上轮建议父ms-0428因与ms-0302报酬问题语义重复而排除；孪生随之建议排除。不合并、替换ICH与FDA两个不同PDF。 |

`ms-0301`特别说明：父ms-0300此前是“移出CO、转交PV”的部门归属建议，并非全局无效。将它视为DROP会误删一个可回答的ADR定义问题。本轮将其保留在待确认清单，未创建新的PV父样本或孪生ID。

`ms-0429`的去重建议不改变文档身份：ICH E6(R3)原版和FDA实施版仍是不同PDF。删除重复问题与合并源文档必须分开处理。

## 4. 重要语义修正

### EN-01 — ms-0138

补回continuous EudraVigilance monitoring、EURD及评估完成后六个月内PSUR到期条件。

核查依据：实际PV父ms-0137修订记录及对应GVP Module IX第16页。

### EN-02 — ms-0188, ms-0198, ms-0210, ms-0253, ms-0267, ms-0375

保留紧急例外、e.g.示例、most、usually、unless、appear等限定，不将建议强化成绝对结论。

核查依据：PV修订表及CO原PDF。

### EN-03 — ms-0192, ms-0216

移除ENS或GVP Module VIII直接给出所问答案的提示；同步父问题的真实任务。

核查依据：PV父ms-0191、0215已修订问题。

### EN-04 — ms-0158, ms-0224, ms-0251, ms-0411

补全多部分信息请求及起算点；不把创建ICSR当作报告时限的新起点。

核查依据：PV父修订记录；GVP VI物理103页表VI.6；ICH E19物理11页。

### EN-05 — ms-0312

wards of the state不是病房儿童；恢复advocate关联限制及IRB/advocate身份例外。中文配对稿待父版本确认。

核查依据：FDA informed consent物理50页。

### EN-06 — ms-0367

不能只问降压药约1500人标准；补慢性用药一般规模、时长及对降压药可能偏小的限制。

核查依据：ICH E12A物理8页。

### EN-07 — ms-0377

明确绝对QTc间期阈值，而非相对基线的增量；中文配对稿待确认。

核查依据：ICH E14物理14页及图像。

### EN-08 — ms-0409

原二元许可问题不能由单一剂量因素直接回答；拟改为一般剂量/频率比较原则，需父题成对批准。

核查依据：ICH E19物理6页单因素不决定、7页第7因素。

### EN-09 — ms-0196, ms-0304, ms-0325, ms-0415, ms-0429

延续并核查父样本排除依赖；不是判作无答案。

核查依据：PV修订表、CO上轮可见裁决及对应原PDF。

### EN-10 — ms-0301

CO→PV只是部门迁移建议，不是全局删除；待父样本恢复/迁移后整族处理。

核查依据：上轮CO裁决与FDA E6物理77页。

## 5. 继承字段处理规则

PV孪生：父中文、切片及key预览仅复制实际PV修订快照；完整key/span在审校JSON中以`inherited_gold_snapshot`保存，逐字与父快照一致。本轮没有独立替换EN的gold或切片。

CO孪生：总表保留原草稿的文档、页码、切片、父中文及key预览。30个涉及条件或任务结构的中文改写仅作为新拟的成对建议列在依赖表中；它们不是上轮CO修订原文，也没有写回CO。先比对真实父修订版本，再批准中文与英文配对。

所有英文问题均有完整建议值；key列刻意仍是预览。预览中的省略号不是最终gold的一部分，不可用来重算偏移。

## 6. 来源与版本边界

本轮使用已登记的实际PDF。相同SHA-256的/sources副本优先于/sources_staging路径；仅有staging副本的保持staging归属。没有网络下载、版本替换或用户电脑目录变更。

历史/草案标识继续保留：GVP Annex I Rev 4注明已失效历史版；FDA方案偏离文件是2024年12月草案；E12A是Principle Document，不冒充通常ICH Step 4指南；FDA研究者安全报告的doc_id含2021，但实际PDF封面为2025年12月。

FDA E6(R3)为2025年9月实施版，ICH E6(R3)为2025年1月原版，分别定位。E11(R1)合订文件中的原始E11第2.5节与R1新增条款区分记录。未将“上传较晚”当作“内容更现行”。

### 实际源PDF索引

下面页数来自本轮重新打开文件的计数。完整哈希为文件名去掉.pdf后的字符串，另存JSON；每行已重算并与登记哈希核对。

| 文档标识 | 版本 | 源路径 | 实际物理页数 |
| --- | --- | --- | --- |
| ema-gvp-annex-i-rev4 | EMA/876333/2011 Rev 4；9 October 2017 | /sources_staging/93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf | 33 |
| ema-gvp-module-i | EMA/541760/2011；22 June 2012 | /sources_staging/197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf | 25 |
| ema-gvp-module-ii-rev2 | EMA/816573/2011 Rev 2；28 March 2017 | /sources_staging/14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf | 20 |
| ema-gvp-module-iii-rev2 | EMA/119871/2012 Rev 2；4 September 2026 | /sources_staging/d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf | 19 |
| ema-gvp-module-iv-rev1 | EMA/228028/2012 Rev 1；3 August 2015 | /sources_staging/d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf | 12 |
| ema-gvp-module-ix-addendum-i | EMA/209012/2015；9 October 2017 | /sources_staging/7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf | 10 |
| ema-gvp-module-ix-rev1 | EMA/827661/2011 Rev 1；9 October 2017 | /sources/801755430dbf3ac68dfed481afc642937b9dbb3c73e38a83e8cd767dc165d1b5.pdf | 25 |
| ema-gvp-module-v-rev2 | EMA/838713/2011 Rev 2；28 March 2017 | /sources_staging/85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf | 36 |
| ema-gvp-module-vi-addendum-i | EMA/405655/2016；28 July 2017 | /sources_staging/4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf | 19 |
| ema-gvp-module-vi-addendum-ii | EMA/178902/2025；22 July 2025 | /sources_staging/53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf | 14 |
| ema-gvp-module-vi-rev2 | EMA/873138/2011 Rev 2；28 July 2017 | /sources/f27a7f0d678b17f2d6374946ae03d0b59db18217ed0fabae0b2f8a9111513b9e.pdf | 144 |
| ema-gvp-module-vii-rev1 | EMA/816292/2011 Rev 1；9 December 2013 | /sources_staging/49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf | 68 |
| ema-gvp-module-viii-rev3 | EMA/813938/2011 Rev 3；9 October 2017 | /sources_staging/847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf | 28 |
| ema-gvp-module-x | EMA/169546/2012；19 April 2013 | /sources_staging/15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf | 9 |
| ema-gvp-module-xv-rev1 | EMA/118465/2012 Rev 1；9 October 2017 | /sources_staging/790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf | 20 |
| ema-gvp-module-xvi-rev3 | EMA/204715/2012 Rev 3；26 July 2024 | /sources_staging/9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf | 43 |
| ema-gvp-pp-i | EMA/488220/2012 Corr；9 December 2013 | /sources_staging/0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf | 25 |
| ema-gvp-pp-iii | EMA/653036/2019 corr 1；2 February 2026 | /sources_staging/fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf | 28 |
| ema-gvp-pp-iv | EMA/572054/2016；25 October 2018 | /sources_staging/e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf | 17 |
| fda-e6r3-gcp-2025 | September 2025 | /sources_staging/e57e9fc0134abebec409d7144aed6e3047c0939d1bd758163fea4e1169472109.pdf | 86 |
| fda-informed-consent-2023 | August 2023 | /sources_staging/96b26b2edb06e20ee2872ca59f4ec7c04cde8a8b1adf98bc150764e3d52f906a.pdf | 66 |
| fda-investigator-responsibilities-2009 | October 2009 | /sources_staging/140b612e6fe3e830256fc9c47794cdf5708b28f2df5d7abe146e14dfd0efadfc.pdf | 18 |
| fda-investigator-safety-reporting-2021 | December 2025 | /sources_staging/c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf | 14 |
| fda-protocol-deviations-draft-2024 | December 2024；DRAFT GUIDANCE；Draft — Not for Implementation | /sources/3b172d83fd5310029d0933a2efdb821c31d77c31d874e292dff7fb7da9abd42f.pdf | 13 |
| fda-rbm-qa-2023 | April 2023 | /sources_staging/2c0d04faa13f3cfd95bb3b4c5359f699ede4f48dcb055ad2d0ae89d3aa9c423c.pdf | 13 |
| fda-risk-based-monitoring-2013 | August 2013 | /sources_staging/76556b1dcf148a1929f110bb1bfdf17d554630b665d23ad2b885473c5e8f2561.pdf | 22 |
| fda-sponsor-safety-reporting-2025 | December 2025 | /sources/7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac.pdf | 43 |
| ich-e10-step4-2000 | Current Step 4 version dated 20 July 2000 | /sources_staging/034b29a6d1b565e4f466fd17df8b6506a7b65508328701b14b11fc42ed0c1881.pdf | 35 |
| ich-e11-r1-step4-2017 | Final version Adopted on 18 August 2017 | /sources_staging/be9f56e84b67bb2d726c24da0096340e2788e92d7197bbd0f2d4f72972299763.pdf | 25 |
| ich-e12a-principle-2000 | Current Principle Document dated 2 March 2000 | /sources_staging/d09627c2d02dc3c6675be445232a7312e0aa295f6b1748da68fc9d771405a9ac.pdf | 10 |
| ich-e14-step4-2005 | Current Step 4 version dated 12 May 2005 | /sources_staging/6199a1a27063c31e6d935e062ad0b581618f123473b13a854fe61eea5ffe0a5c.pdf | 18 |
| ich-e15-step4-2007 | Current Step 4 version dated 1 November 2007 | /sources_staging/40516566c939436147ade1b076a2e46d716755d3062c1102732ae394cf8e02fc.pdf | 10 |
| ich-e17-step4-2017 | Final version Adopted on 16 November 2017 | /sources_staging/e67211a8358fa94236ef0a0dd0a76538271584ab93a71b9f9bf841d94d3f5371.pdf | 29 |
| ich-e18-step4-2017 | Current Step 4 version dated 3 August 2017 | /sources_staging/5dbb1b7247cf7ac1fd9629e3545e20df95b648785dfa50b0024fae96b49eb418.pdf | 11 |
| ich-e19-step4-2022 | Final version Adopted on 27 September 2022 | /sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf | 15 |
| ich-e2a-step4-1994 | Current Step 4 version dated 27 October 1994 | /sources/1c095d80419287187bf5b2db5eba83864adccebf07b9c593bf5925b4ab6f7cf7.pdf | 12 |
| ich-e2c-r2-step4-2012 | Current Step 4 version dated 17 December 2012 | /sources_staging/0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf | 41 |
| ich-e2d-step4-2003 | Current Step 4 version dated 12 November 2003 | /sources_staging/c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf | 15 |
| ich-e2e-step4-2004 | Current Step 4 version dated 18 November 2004 | /sources_staging/8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf | 20 |
| ich-e2f-step4-2010 | Current Step 4 version dated 17 August 2010 | /sources/7912d4d0f2b5fa407a5e8fe3908a7e8262e4034c23409cd903e3646c5b7a693b.pdf | 35 |
| ich-e3-step4-1995 | Current Step 4 version dated 30 November 1995 | /sources_staging/032d53bb6d693151b64bdc87aa4cf42b90e096db6e52dad73c2093cd62ffa24d.pdf | 49 |
| ich-e6-r3-step4-2025 | Final version Adopted on 06 January 2025 | /sources/e6ce19e36ce7d2e294f89ee89492b9e035178c3cca48984392bbd92eec9b002c.pdf | 86 |
| ich-e7-step4-1993 | Current Step 4 version dated 24 June 1993 | /sources_staging/cbe681cf342eeefb477c1a30770d12798fadcf2d00079faa0aa66047ce4ca330.pdf | 6 |
| ich-e8-r1-step4-2021 | Final version Adopted on 6 October 2021 | /sources/99d56638828c823bb603ff3ef451fcfafc607de8a5b3926136d64980f27baa13.pdf | 29 |
| ich-e9-r1-step4-2019 | Final version Adopted on 20 November 2019 | /sources_staging/f7471f411f1c87ee76783d5b2b9faaeca31d01d530213f71b50d136b39e3b0d9.pdf | 22 |
| ich-e9-step4-1998 | Current Step 4 version dated 5 February 1998 | /sources_staging/0c0ddc93cb427a70265dbcb0e7c25bfc9a3f7b52e178212b3630ea2408ad9c7e.pdf | 39 |

## 7. 编辑后的第二遍自审

已从生成后的表格读取每条最终ID/父ID/文档/页码，并重新打开46份源PDF，核对哈希、页数、首页文本及174个锚点。没有只复用第一遍的“通过”布尔值。

93条采用完整PV父key和完整span，重新确认本地页内各出现一次且key包含于span；其余81条仅用预览前缀确认文件及物理页。后者**绝不记作完整gold通过**。

定位采用本地compact规则：Unicode NFKC、移除U+00AD/U+FFFE、移除空白。它与项目norm-v1不是同一个坐标系，因此未输出可直接应用的norm-v1偏移。

源图像检查范围：

| 文档 | 物理页 | 实际检查内容 |
| --- | ---: | --- |
| ich-e14-step4-2005 | 14 | 原PDF页面图像；绝对QTc与相对基线变化分栏/列表核对。 |
| fda-e6r3-gcp-2025 | 18 | Files未返回图像后用PyMuPDF渲染并查看；核对1.4.1–1.4.8边界。 |
| fda-e6r3-gcp-2025 | 19 | 用PyMuPDF渲染并查看；确认1.4.9跨页续项。 |
| fda-protocol-deviations-draft-2024 | 11 | 查看原PDF图像；确认行号不是正文，以及措施段落。 |
| fda-protocol-deviations-draft-2024 | 12 | 查看原PDF图像；确认设计/风险缓解措施续文。 |
| ema-gvp-module-xv-rev1 | 18 | 查看原PDF图像；确认DHPC Summary/Background。 |
| ema-gvp-module-xv-rev1 | 19 | 查看原PDF图像；确认Background最后续项在Call for reporting前。 |
| ema-gvp-module-vi-rev2 | 103 | 用PyMuPDF渲染并查看；Table VI.6第4步格式/期限/地区分支，不借用第2步重置时钟。 |
| ema-gvp-module-vi-addendum-i | 18 | 用PyMuPDF渲染并查看；第9步2017-11-22边界与接收方。 |

输出结构检查：174个唯一ID、9列、父ID无重挂；93 OK／76 PENDING_PARENT／5 DROP；英文问题无展示截断；22组关键限定词守卫检查通过。

全部输入快照的SHA-256在处理后保持不变。部分PDF抽取时出现MuPDF图层配置告警；实际文本读取及定位成功，未把告警等同于文件损坏，也未隐去其存在。具体告警保存在审校JSON。

这次自审仍由同一AI完成，不是第二位人工复核或独立模型复核。

## 8. 逐条审校记录

每条的英文语言结论与整族结论分开。若英文原值被截断，其尾部并未被当作已知内容；建议值是重新拟定的完整问句。

### ms-0085 ← ms-0084 — OK

语言建议：`REVISE_QUERY`。与已修订父问题的五个要点对齐；限定为Annex I Rev 4引述，未将历史文件说成现行法律。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Annex I Rev 4 所引 Directive 2001/20/EC Art 2(c)，非干预性试验（non-interventional trial）在处方、治疗分配、入组决定、额外检查和数据分析方面须满足哪些条件？

原英文：What is the legal definition of a non-interventional trial under Directive 2001/20/EC Art 2(c), and does it require additional diagnostic or monitoring procedures?

建议英文：According to Directive 2001/20/EC Article 2(c), as cited in GVP Annex I Rev 4, what conditions must a non-interventional trial meet regarding prescribing, treatment allocation, the decision to enrol patients, additional examinations, and data analysis?

引用：`/sources_staging/93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第20页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0087 ← ms-0086 — OK

语言建议：`REVISE_QUERY`。保留总体药用年限与欧盟境内年限两部分，补足父问题指定的历史引述来源。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Annex I Rev 4 所引 Directive 2001/83/EC Art 16c(1)(c)，传统草药药品（traditional herbal medicinal product）的传统药用年限须达到多久，其中欧盟境内须达到多久？

原英文：According to Directive 2001/83/EC Art 16c(1)(c), how long must a traditional herbal medicinal product have been in medicinal use to qualify, including the required period within the EU?

建议英文：According to Directive 2001/83/EC Article 16c(1)(c), as cited in GVP Annex I Rev 4, how long must a traditional herbal medicinal product have been in medicinal use, including the required period within the EU?

引用：`/sources_staging/93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第30页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0089 ← ms-0088 — OK

语言建议：`REVISE_QUERY`。父问题已扩为先查清单、提出日期及取得监管同意；不能继续只用笼统问法。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：上市许可持有人查不到产品实际国际诞生日（IBD）时，应先查什么；若仍查不到，应如何提出日期并取得确认？

原英文：If a marketing authorisation holder has no information on the actual international birth date (IBD) of a product, how should the IBD be determined?

建议英文：If a marketing authorisation holder cannot establish a product's actual international birth date (IBD), what should it consult first, and, if the date remains unavailable, how should it propose a date and obtain agreement?

引用：`/sources_staging/93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第17页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0091 ← ms-0090 — OK

语言建议：`REVISE_QUERY`。补回before release as a finished product，避免把排除范围扩大到整个生产链。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Annex I 的职业暴露（occupational exposure）定义，在成品放行前的生产过程中接触药品成分，是否属于该定义的报告范围？

原英文：Does the definition of occupational exposure to a medicinal product include exposure to an ingredient during the manufacturing process?

建议英文：Under the definition of occupational exposure in GVP Annex I, is exposure to an ingredient during manufacturing, before release as a finished product, within the reporting scope of that definition?

引用：`/sources_staging/93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第21页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0093 ← ms-0092 — OK

语言建议：`REVISE_QUERY`。问核心信息列示及当地修改例外，不要求各国所有安全性信息绝对相同。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按公司核心安全性信息（CCSI）的定义，核心安全性信息在各销售国的列示要求是什么，何时允许按当地要求修改？

原英文：Does the company core safety information (CCSI) require identical safety information to be listed in all countries where the product is marketed, and are there any exceptions?

建议英文：Under the definition of company core safety information (CCSI), what safety information must be listed in countries where the product is marketed, and when may it be modified to meet local requirements?

引用：`/sources_staging/93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe.pdf`，物理第10页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0095 ← ms-0094 — OK

语言建议：`REVISE_QUERY`。英文展示被截断；重拟完整句，终止对象为药物警戒系统，不是产品撤市或任意文件终止。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：MAH 的药物警戒系统主档案（PSMF）最少要素，在系统正式终止后需要保留多久？

原英文：According to GVP Module I, for how long must the minimum elements of the marketing authorisation holder's pharmacovigilance system master file (PSMF) be retained after the pharmacovigilance system has…

建议英文：According to GVP Module I, for how long must the minimum elements of a marketing authorisation holder's pharmacovigilance system master file (PSMF) be retained after that holder formally terminates the pharmacovigilance system?

引用：`/sources_staging/197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`，物理第18页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0097 ← ms-0096 — OK

语言建议：`REVISE_QUERY`。补全截断部分及全部责任相对方，保留不取代法律责任这一判断问题。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在互认或分散程序下，参考成员国协调与MAH沟通的安排，是否可以取代持有人对各成员国主管当局和EMA的法律责任？

原英文：Under the mutual recognition or decentralised procedure, do the coordination arrangements of the Reference Member State replace the marketing authorisation holder's legal responsibilities towards indi…

建议英文：Under the mutual recognition or decentralised procedure, do the Reference Member State's arrangements for coordinating communication with the MAH replace the holder's legal responsibilities towards the competent authorities of individual Member States and EMA?

引用：`/sources_staging/197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`，物理第20页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0099 ← ms-0098 — OK

语言建议：`KEEP_QUERY`。IR Art 10(2)、QPPV职责和文件载体三个要素一致；没有在英文提前给出job description答案。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据 IR Art 10(2)，QPPV 的职责应记录在什么文件中？

保留英文：According to IR Art 10(2), in what document must the duties of the QPPV be defined?

引用：`/sources_staging/197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`，物理第14页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0101 ← ms-0100 — OK

语言建议：`KEEP_QUERY`。报告对象为质量稽核结果，问发送给谁；未误译为稽核执行人员。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据 IR Art 13(2)，MAH 药物警戒系统质量稽核结果的报告应发送给谁？

保留英文：According to IR Art 13(2), to whom must the report on the results of a quality audit of the marketing authorisation holder's pharmacovigilance system be sent?

引用：`/sources_staging/197de2bc0cfb6bdafe8d322934ece6e9bd4c5901651a5a828e74076470d7ff59.pdf`，物理第13页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0103 ← ms-0102 — OK

语言建议：`KEEP_QUERY`。QPPV或PSMF位置变更、Article 57更新及最迟时限一致；gold保留立即更新而不只是30天。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据 GVP Module II，MAH 在 QPPV 详细信息或 PSMF 位置发生变更后，最迟须在多长时间内更新 Article 57 数据库中的相关信息？

保留英文：According to GVP Module II, how soon at the latest must the MAH update the Article 57 database following a change in QPPV details or PSMF location?

引用：`/sources_staging/14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf`，物理第6页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0105 ← ms-0104 — OK

语言建议：`KEEP_QUERY`。保留NCA请求、收到请求起算及副本提交，未自行添加工作日或日历日。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：MAH 在收到国家主管机关就 PSMF 提出的请求后，最迟须在多少天内提交 PSMF 副本？

保留英文：After receiving a request from a national competent authority for the PSMF, within how many days at the latest must the MAH submit the copy?

引用：`/sources_staging/14f23bbae2e09a1d0c3925922492afeefef83e5fc67501ea217d68bcbe0647d1.pdf`，物理第20页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0109 ← ms-0108 — OK

语言建议：`REVISE_QUERY`。原英文仅问固定周期；补足首次检查、后续周期和持续风险评估调整。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Module III Rev 2，对集中程序获批产品的上市许可持有人，首次常规药物警戒检查及之后的基准检查周期如何安排，能否依据持续风险评估调整？

原英文：What is the standard inspection cycle for routine pharmacovigilance inspections of centrally authorised products?

建议英文：According to GVP Module III Rev 2, how should the first routine pharmacovigilance inspection and the subsequent baseline inspection cycle be scheduled for an MAH of centrally authorised products, and can the schedule be adjusted on the basis of ongoing risk assessment?

引用：`/sources_staging/d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`，物理第18页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0111 ← ms-0110 — OK

语言建议：`KEEP_QUERY`。mandatory的否定判断与父问题一致；并未把非强制推成禁止开展检查。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：上市前药物警戒检查(pre-authorisation inspection)对于新的上市许可申请是否属于强制性要求?

保留英文：Are pre-authorisation pharmacovigilance inspections mandatory for new marketing authorisation applications?

引用：`/sources_staging/d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`，物理第6页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0113 ← ms-0112 — OK

语言建议：`KEEP_QUERY`。进一步分包的主体、第三方与检查安排一致；条号没有变更。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据IR Art 6(3),当一个已被分包的第三方将药物警戒任务进一步分包给另一第三方时,检查安排应当如何处理?

保留英文：Under IR Art 6(3), when a subcontracted third party further subcontracts pharmacovigilance tasks to another third party, how should inspection arrangements be handled?

引用：`/sources_staging/d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`，物理第3页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0115 ← ms-0114 — OK

语言建议：`KEEP_QUERY`。未遵守药物警戒义务的条件及相关成员国通知哪些机构保持一致。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：若检查结果显示上市许可持有人未遵守药物警戒义务,依据DIR Art 111(8),相关成员国应通知哪些机构?

保留英文：If an inspection finds that a marketing authorisation holder does not comply with pharmacovigilance obligations, under DIR Art 111(8) which bodies must the concerned Member State inform?

引用：`/sources_staging/d4b744c043ea16938c3e53fab9cf3344b3ffd3aa66df0b25277878897b0d1b64.pdf`，物理第4页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0117 ← ms-0116 — OK

语言建议：`KEEP_QUERY`。定义对象是major审计发现，而不是major adverse event；英文自然。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP Module IV审计发现分级标准，'major'（重大）级别的审计发现应如何定义？

保留英文：According to the audit finding grading system in GVP Module IV, how is a 'major' finding defined?

引用：`/sources_staging/d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第8页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0119 ← ms-0118 — OK

语言建议：`KEEP_QUERY`。限定首次公开EMA药物警戒任务报告，不误问成员国报告或后续三年周期。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP Module IV，欧盟委员会最迟应于何时首次公开有关欧洲药品管理局（EMA）药物警戒任务执行情况的报告？

保留英文：According to GVP Module IV, by when must the European Commission first make public its report on the performance of pharmacovigilance tasks by the Agency (EMA)?

引用：`/sources_staging/d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第12页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0121 ← ms-0120 — OK

语言建议：`KEEP_QUERY`。EU MAH、DIR Art 104(2)及审计义务保持一致；完整gold包括质量体系范围。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据DIR Art 104(2)，欧盟上市许可持有人（MAH）对其药物警戒系统负有什么审计义务？

保留英文：Under DIR Art 104(2), what audit obligation does an EU marketing authorisation holder (MAH) have regarding its pharmacovigilance system?

引用：`/sources_staging/d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第10页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0123 ← ms-0122 — OK

语言建议：`KEEP_QUERY`。PRAC mandate与药物警戒审计的联系及REG Art 61a(6)相同。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据REG Art 61a(6)，PRAC（药物警戒风险评估委员会）的职责范围与药物警戒审计有何关联？

保留英文：Under REG Art 61a(6), how does the mandate of the Pharmacovigilance Risk Assessment Committee (PRAC) relate to pharmacovigilance audits?

引用：`/sources_staging/d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第11页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0125 ← ms-0124 — OK

语言建议：`KEEP_QUERY`。同时询问critical/major/minor三级和每一级定义；没有仅问其中一个等级。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据 GVP Module IV,药物警戒审计发现(audit findings)应如何分级为 critical、major、minor 三个等级?每个等级的具体定义是什么?

保留英文：According to GVP Module IV, how should pharmacovigilance audit findings be graded as critical, major, or minor, and what is the specific definition of each grade?

引用：`/sources_staging/d0e530f1b15c00987e77a97eb2c310c3267c13a3351a42b9143fee4f899293e8.pdf`，物理第8页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0127 ← ms-0126 — OK

语言建议：`REVISE_QUERY`。将should be used改为has been shown，保留常规统计信号检测适用范围，不把性能描述变为唯一强制层级。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在常规自发报告统计信号检测中，GVP Module IX Addendum I 指出，哪一级 MedDRA 术语粒度在灵敏度与阳性预测值方面表现良好？

原英文：According to EMA GVP Module IX Addendum I, which level of MedDRA term granularity should be used for screening in signal detection to achieve good sensitivity and positive predictive value?

建议英文：According to GVP Module IX Addendum I, which level of MedDRA term granularity has been shown to perform well in terms of sensitivity and positive predictive value in routine statistical signal detection from spontaneous reports?

引用：`/sources_staging/7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第5页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0129 ← ms-0128 — OK

语言建议：`REVISE_QUERY`。删除无依据的typically；问题是验证研究考察过的间隔，不是固定监管频次。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP Module IX Addendum I 提到，信号检测方法的验证研究曾考察相邻两次数据汇总（data summaries）之间多长的间隔？

原英文：According to GVP Module IX Addendum I, what time interval between consecutive data summaries has typically been investigated in validation studies for signal detection methods?

建议英文：According to GVP Module IX Addendum I, what interval between consecutive data summaries has been investigated in validation studies of signal detection methods?

引用：`/sources_staging/7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第6页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0131 ← ms-0130 — OK

语言建议：`REVISE_QUERY`。与修订父问题的判断式问法对齐；保留seriousness而不误用severity。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Module IX Addendum I，自发 ICSR 中事件的严重性（seriousness）能否直接说明该事件与药物存在因果关系的可能性？

原英文：According to GVP Module IX Addendum I, how does the seriousness of adverse events reported in spontaneous ICSRs relate to the probability of a causal relationship with the medicine?

建议英文：According to GVP Module IX Addendum I, does the seriousness of an event in a spontaneous ICSR directly indicate the probability that it is causally related to the medicine?

引用：`/sources_staging/7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第8页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0133 ← ms-0132 — OK

语言建议：`KEEP_QUERY`。问题明确520/2012的条款，不将答案Article 19 and 23泄露到问题。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：EMA GVP Module IX Addendum I所依据的Commission Implementing Regulation (EU) No 520/2012具体对应该法规的哪几条?

保留英文：Which specific articles of Commission Implementing Regulation (EU) No 520/2012 does the guidance in EMA GVP Module IX Addendum I relate to?

引用：`/sources_staging/7a649643af0a390cfb0246714325cb1adf11ebc1d6980b6039c8b643a2f5d674.pdf`，物理第3页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0136 ← ms-0135 — OK

语言建议：`REVISE_QUERY`。恢复完整问句、书面通知、工作日和全部接收方；使用should，不将指南建议无条件强化为must。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：MAH发现某信号符合emerging safety issue定义后，最迟应在多少个工作日内以书面形式通知相关成员国主管机关及EMA？

原英文：After a marketing authorisation holder determines that a signal meets the definition of an emerging safety issue, within how many working days must it notify the competent authority and EMA in writing…

建议英文：After an MAH determines that a signal meets the definition of an emerging safety issue, within how many working days at the latest should it notify EMA and the competent authorities of the relevant Member States in writing?

引用：`/sources/801755430dbf3ac68dfed481afc642937b9dbb3c73e38a83e8cd767dc165d1b5.pdf`，物理第12页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0138 ← ms-0137 — OK

语言建议：`REVISE_QUERY`。补足continuous EudraVigilance monitoring及评估完成后六个月到期提交条件。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：MAH 对通过持续 EudraVigilance 监测发现的信号完成评估后，若该活性物质已列入 EURD 清单，且 PSUR 在评估完成后6个月内到期提交，是否还需单独提交 standalone signal notification？

原英文：If a substance is on the EURD list and its PSUR is due within 6 months of completing a signal assessment, does the MAH still need to submit a standalone signal notification?

建议英文：If an MAH completes its assessment of a signal detected through continuous EudraVigilance monitoring, the active substance is on the EURD list, and a PSUR is due within six months of completion of the assessment, is a separate standalone signal notification still required?

引用：`/sources/801755430dbf3ac68dfed481afc642937b9dbb3c73e38a83e8cd767dc165d1b5.pdf`，物理第16页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0140 ← ms-0139 — OK

语言建议：`KEEP_QUERY`。未被EMA/NCA要求的研究是否纳入RMP药物警戒计划；没有推成其发现可免于报告。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：如果某项研究并非受EMA或国家主管当局要求进行，该研究是否应纳入RMP的药物警戒计划中？

保留英文：Under GVP Module V, should a study that is not required by the EMA or a national competent authority be included in the pharmacovigilance plan of the RMP?

引用：`/sources_staging/85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf`，物理第21页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0142 ← ms-0141 — OK

语言建议：`KEEP_QUERY`。新上市申请随附文件的提问与父问题一致；答案须包含RMP及摘要，英文未排除摘要。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据 DIR Art 8(3)(iaa)，所有新上市许可申请人在提交申请时应随附提交什么文件？

保留英文：Under DIR Art 8(3)(iaa), what document must all new marketing authorisation applicants submit together with their application?

引用：`/sources_staging/85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf`，物理第29页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0144 ← ms-0143 — OK

语言建议：`REVISE_QUERY`。单数article改为复数articles；对应107m-q范围，保留两类触发条件。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：非干预性 PASS 被作为上市许可条件或特定义务实施时，GVP Module V 指明其监督适用 DIR 的哪些条款？

原英文：When a non-interventional PASS is imposed as a condition of the marketing authorisation or a specific obligation, which DIR article governs its supervision?

建议英文：When a non-interventional PASS is imposed as a condition of marketing authorisation or a specific obligation, which articles of the Directive does GVP Module V identify as governing its supervision?

引用：`/sources_staging/85f6186f5981799864df2a2f1a4a2b0c8bc73bec777f92605c2ef5afe51e6125.pdf`，物理第21页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0146 ← ms-0145 — OK

语言建议：`REVISE_QUERY`。保留on or after含当日，并补上修订父问题的是否仍送原NCA。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：某病例原报告在2017年11月22日前已发送给成员国主管机关（NCA），其最新版本在该日期当日或之后发送时，应送往何处，还应送给原 NCA 吗？

原英文：If a case was sent to an NCA before 22 Nov 2017 but its latest version is to be sent on or after that date, to whom should it be sent?

建议英文：If the original case report was sent to an NCA before 22 November 2017 and the latest version is to be sent on or after that date, where should it be sent, and should it also be sent to the original NCA?

引用：`/sources_staging/4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf`，物理第18页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0148 ← ms-0147 — OK

语言建议：`REVISE_QUERY`。与父问题的合作对象对应，而非泛问全部合作义务。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP Module VI Addendum I 引用的 Directive 2001/83/EC 第107(5)条，要求上市许可持有人与哪些机构合作检测重复疑似不良反应报告？

原英文：Under Article 107(5) of Directive 2001/83/EC, what collaboration obligation do marketing authorisation holders have in the detection of duplicate suspected adverse reaction reports?

建议英文：Under Article 107(5) of Directive 2001/83/EC, as cited in GVP Module VI Addendum I, with which bodies must MAHs collaborate to detect duplicate reports of suspected adverse reactions?

引用：`/sources_staging/4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf`，物理第3页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0150 ← ms-0149 — OK

语言建议：`REVISE_QUERY`。补回共同要素但彼此独立的病例条件；不混淆Linked reports与Report duplicates字段。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在 ICH-E2B(R2) 的 Linked reports 字段 A.1.12 中，应如何填写具有共同要素但彼此独立的病例，以帮助确认它们并非重复报告？

原英文：In ICH-E2B(R2) reports, how can the 'Linked reports' field (data field A.1.12) be used to confirm that cases are not duplicates of one another?

建议英文：In an ICH-E2B(R2) report, how should the Linked reports field A.1.12 be populated for cases that share common elements but are distinct, to help confirm that they are not duplicates?

引用：`/sources_staging/4993d9f6a6a6cb8828a36f604743c8dd8724b0c40d9c2082f2a4d1158b14a9b6.pdf`，物理第8页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0152 ← ms-0151 — OK

语言建议：`KEEP_QUERY`。所问仍是主模块关于数据保护的章节；this Addendum II在该文档限定下不改变问题。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP Module VI Addendum II 这份附录补充了主模块中关于数据保护法律的哪一节？

保留英文：What section of GVP Module VI on data protection laws does this Addendum II complement?

引用：`/sources_staging/53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf`，物理第3页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0154 ← ms-0153 — OK

语言建议：`KEEP_QUERY`。5(1)条、安全评估成员国及筛查评估信息保持一致；gold覆盖SUSAR与annual reports。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据 Commission Implementing Regulation (EU) 2022/20 第5(1)条,负责安全评估的成员国 (safety assessing Member State) 需要筛查评估哪些信息?

保留英文：According to Article 5(1) of Commission Implementing Regulation (EU) 2022/20, what information must the safety assessing Member State screen and assess?

引用：`/sources_staging/53bb1c46db481ae94009a302ca87cb44325cf1a82e7908c41e33c01649878b4c.pdf`，物理第4页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0158 ← ms-0157 — OK

语言建议：`REVISE_QUERY`。恢复被截断英文并覆盖格式、适用时限及非EEA非严重病例；删除以创建报告时刻起算的暗示。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Module VI 的 Table VI.6 第4步，有效 ICSR 应以何种格式、在何种适用时限内提交至 EudraVigilance，非严重的非 EEA 病例如何处理？

原英文：In the GVP Module VI ICSR submission process (Table VI.6), within what timeframe should the NCA/MAH submit a valid ICSR to EudraVigilance after creating it, and do non-serious non-EEA ICSRs need to be…

建议英文：Under Step 4 of Table VI.6 in GVP Module VI, in what format and within which applicable timeframes should a valid ICSR be submitted to EudraVigilance, and how should non-serious non-EEA ICSRs be handled?

引用：`/sources/f27a7f0d678b17f2d6374946ae03d0b59db18217ed0fabae0b2f8a9111513b9e.pdf`，物理第103页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0160 ← ms-0159 — OK

语言建议：`REVISE_QUERY`。补全截断问句，必须同时保留原始报告者明确排除与机构同意两个条件。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：若原始报告者明确声明疑似药品与不良事件之间不存在因果关系，且主管机关或 MAH 也认同该判断，这份报告是否构成有效 ICSR？

原英文：If the primary source explicitly states that a causal relationship between the suspect medicinal product and the adverse event has been excluded, and the competent authority or MAH agrees with this as…

建议英文：If the primary source explicitly excludes a causal relationship between the suspect medicinal product and the reported adverse event, and the competent authority or MAH agrees with that assessment, does the report qualify as a valid ICSR?

引用：`/sources/f27a7f0d678b17f2d6374946ae03d0b59db18217ed0fabae0b2f8a9111513b9e.pdf`，物理第15页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0162 ← ms-0161 — OK

语言建议：`KEEP_QUERY`。保留up to 12 months及exactly 12 months；日历日与原文对应。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：EMA GVP Module VII规定,涵盖时间不超过12个月(含恰好12个月)的PSUR,应在数据锁定点后多少天内提交?

保留英文：According to EMA GVP Module VII, within how many calendar days of the data lock point must a PSUR covering an interval of up to 12 months (including exactly 12 months) be submitted?

引用：`/sources_staging/49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第5页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0164 ← ms-0163 — OK

语言建议：`KEEP_QUERY`。solely for preparing a PSUR准确限定解盲目的，未误禁所有安全理由解盲。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP Module VII是否允许申办方或MAH仅为撰写PSUR而对临床试验数据进行破盲?

保留英文：Under GVP Module VII, are clinical trial sponsors or marketing authorisation holders allowed to unblind data solely for the purpose of preparing a PSUR?

引用：`/sources_staging/49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第18页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0166 ← ms-0165 — OK

语言建议：`KEEP_QUERY`。四类药品及general exemption的例外保持一致，homeopathic术语正确。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Module VII 所引 DIR Art 107b(3)，仿制药、已确立使用（well-established use）、顺势疗法和传统草药药品，在哪些例外情况下仍须提交 PSUR？

保留英文：Under DIR Art 107b(3), in which circumstances are generic, well-established use, homeopathic and traditional herbal medicinal products still required to submit a PSUR despite the general exemption?

引用：`/sources_staging/49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第40页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0168 ← ms-0167 — OK

语言建议：`REVISE_QUERY`。随父问题删除Day 105提示，保留收到评论这一相对起算点。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在 PSUR 单一评估程序中，PRAC 报告员或负责成员国收到评论后，应在多少天内完成更新评估报告？

原英文：In the PSUR single assessment procedure, within how many days after receiving comments must the PRAC Rapporteur/Member State prepare the updated assessment report (i.e. by Day 105)?

建议英文：In the PSUR single assessment procedure, within how many days after receiving comments must the PRAC Rapporteur or responsible Member State prepare an updated assessment report?

引用：`/sources_staging/49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第53页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0170 ← ms-0169 — OK

语言建议：`REVISE_QUERY`。补全被截断英文并保留父问题指定子章节，包含汇总表所有考虑要点。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在撰写PSUR VII.B.5.6.2子章节“Cumulative summary tabulations of serious adverse events from clinical trials”时,MAH在准备该临床试验严重不良事件累积汇总表(tabulation)时应考虑哪些要点?

原英文：When preparing the PSUR sub-section on cumulative summary tabulations of serious adverse events from clinical trials, what points should the marketing authorisation holder consider regarding the tabul…

建议英文：When preparing the cumulative summary tabulations of serious adverse events from clinical trials in PSUR sub-section VII.B.5.6.2, what points should the MAH consider?

引用：`/sources_staging/49c5e574e9296c38a5a1ddcb6cf7903a4b91c3b28bd98088c839eea50f0a23a8.pdf`，物理第18页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0172 ← ms-0171 — OK

语言建议：`REVISE_QUERY`。对齐修订父问题的章节与一般期限，不把另有豁免情形写成绝对无例外。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP Module VIII 的 VIII.B.4.3.2 对欧盟主管当局强制要求开展的非干预性 PASS，给出的最终研究报告一般提交时限是数据收集结束后多久？

原英文：For a non-interventional PASS conducted pursuant to an obligation imposed by an EU competent authority, within what timeframe after the end of data collection must the final study report be submitted?

建议英文：Under Section VIII.B.4.3.2 of GVP Module VIII, what is the general deadline after the end of data collection for submitting the final study report of a non-interventional PASS imposed by an EU competent authority?

引用：`/sources_staging/847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`，物理第13页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0174 ← ms-0173 — OK

语言建议：`REVISE_QUERY`。恢复截断部分、waiver对象、书面形式及相对报告到期日；should不强化为must。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：当PRAC负责监督某项non-interventional PASS时，MAH应至少提前多久向Agency书面申请final study report的waiver？

原英文：When the PRAC is responsible for supervision of a non-interventional PASS, how far in advance of the due date must the marketing authorisation holder submit a written waiver request to the Agency for …

建议英文：When PRAC supervises a non-interventional PASS, how far before the final study report's submission deadline should the MAH request a waiver in writing from the Agency?

引用：`/sources_staging/847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`，物理第20页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0176 ← ms-0175 — OK

语言建议：`KEEP_QUERY`。secondary use of data与ICSR形式报告保持一致，不扩成无需任何安全分析或汇总报告。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：对于基于二手数据（secondary use of data）设计的非干预性PASS，是否需要以individual case safety report（ICSR）形式报告疑似不良反应？

保留英文：For a non-interventional PASS based on secondary use of data, is reporting of suspected adverse reactions in the form of individual case safety reports (ICSRs) required?

引用：`/sources_staging/847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`，物理第11页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0178 ← ms-0177 — OK

语言建议：`KEEP_QUERY`。may准确表达申请书面意见的权利而非必须提出申请，条款与起算点一致。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 REG Art 10a(2) 和 DIR Art 22a(2)，MAH 希望针对被施加的义务陈述书面意见时，应在收到书面通知后多久内提出这一请求？

保留英文：Under REG Art 10a(2) and DIR Art 22a(2), within how many days of receiving written notification of an imposed obligation may the marketing authorisation holder request to present written observations?

引用：`/sources_staging/847b0c095bc647e02aa577e2116a03b14ff237982af6b850d88e77fcc69e343e.pdf`，物理第19页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0180 ← ms-0179 — OK

语言建议：`REVISE_QUERY`。恢复截断；明确on 1 January而非无日期的previously，保留已在EU获准产品条件。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Module X 所引 Regulation (EC) No 726/2004 Article 23(1)，一款在欧盟获准的药品所含新活性物质，在2011年1月1日尚未包含于任何欧盟已批准药品中，是否属于必须纳入额外监测清单的类别？

原英文：Under GVP Module X mandatory scope (Article 23(1)), must a medicinal product be included in the additional monitoring list if it contains a new active substance not previously contained in any medicin…

建议英文：Under Article 23(1) of Regulation (EC) No 726/2004, as cited in GVP Module X, must an EU-authorised medicinal product be included in the additional monitoring list if it contains a new active substance that, on 1 January 2011, was not contained in any medicinal product authorised in the EU?

引用：`/sources_staging/15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`，物理第5页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0182 ← ms-0181 — OK

语言建议：`REVISE_QUERY`。补回起算日期这一父问题新增要点；不得将URD自动当作任意国家批准日。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP Module X 对2011年1月1日后获批、含新活性物质的药品及生物药品，规定额外监测清单初始纳入期从哪个日期起算、持续多久？

原英文：For new active substances or biological medicinal products approved after 1 January 2011, what is the initial period for inclusion in the additional monitoring list under GVP Module X?

建议英文：Under GVP Module X, from which date is the initial inclusion period in the additional monitoring list measured for medicinal products containing new active substances and biological medicinal products approved after 1 January 2011, and how long does that period last?

引用：`/sources_staging/15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`，物理第6页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0184 ← ms-0183 — OK

语言建议：`REVISE_QUERY`。补完截断部分并按源条款采用should；不自行添加日类型。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在互认或分散上市许可程序下，成员国主管机关须在国家层面批准上市许可后多久内通知EMA以便将该产品列入additional monitoring list？

原英文：Under mutual recognition or decentralised procedures, within how many days must a national competent authority inform the Agency after granting a national marketing authorisation, for inclusion in the…

建议英文：Under mutual recognition or decentralised marketing authorisation procedures, how soon after granting a national marketing authorisation should the competent authority notify EMA so that the product can be included in the additional monitoring list?

引用：`/sources_staging/15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`，物理第8页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0186 ← ms-0185 — OK

语言建议：`REVISE_QUERY`。补全截断英文，所问是PRAC职责而不是其单独直接批准入列。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP Module X, PRAC在Article 23(2) of Regulation (EC) 726/2004所述附条件药品的清单纳入问题上承担什么职责？

原英文：Under GVP Module X, what is the PRAC's role regarding medicinal products subject to conditions under Article 23(2) of Regulation (EC) 726/2004 with respect to inclusion in the additional monitoring li…

建议英文：Under GVP Module X, what is PRAC's role in deciding whether medicinal products subject to the conditions in Article 23(2) of Regulation (EC) No 726/2004 should be included in the additional monitoring list?

引用：`/sources_staging/15eb6d4ef94b955204fbe276f11a98f08e712a19d9f0e1b6599f8d11d2e55baf.pdf`，物理第7页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0188 ← ms-0187 — OK

语言建议：`REVISE_QUERY`。新增父问题的紧急公共卫生例外，不让24小时成为无条件绝对要求。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Module XV 所引 DIR Art 106a(2)，成员国、EMA 与欧盟委员会发布安全公告前互相通知的一般提前时限是什么，何种紧急情况可例外？

原英文：According to GVP Module XV, how far in advance must Member States, the Agency and the European Commission notify each other before publishing a safety announcement, per DIR Art 106a(2)?

建议英文：Under DIR Article 106a(2), as cited in GVP Module XV, how far in advance must Member States, EMA and the European Commission generally notify each other of a safety announcement, and what urgent circumstance permits an exception?

引用：`/sources_staging/790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第11页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0190 ← ms-0189 — OK

语言建议：`KEEP_QUERY`。保留national tailoring与EU已议定核心信息不得冲突的关系。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP Module XV，各成员国在对core EU DHPC进行本国化调整（national tailoring）时，是否可以与EU层面已议定的核心信息相冲突？

保留英文：According to GVP Module XV, when national tailoring is applied to a core EU DHPC, can it conflict with the core messages already agreed at EU level?

引用：`/sources_staging/790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第15页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0192 ← ms-0191 — OK

语言建议：`REVISE_QUERY`。删除原英文(ENS)直接泄露所问系统答案的问题；与修订父问题一致。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP Module XV，欧盟监管网络应通过哪个系统交流和协调安全公告？

原英文：According to GVP Module XV, which system (ENS) should be used for the exchange and coordination of safety announcements within the EU regulatory network?

建议英文：According to GVP Module XV, which system should the EU regulatory network use to exchange and coordinate safety announcements?

引用：`/sources_staging/790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第12页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0194 ← ms-0193 — OK

语言建议：`KEEP_QUERY`。问最长语言审核时限，不混淆4-5工作日上限与理想48小时目标。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP Module XV，成员国对DHPC翻译文本进行语言审阅的期限最长不得超过多久？

保留英文：According to GVP Module XV, what is the maximum timeframe within which Member States should complete the language review of DHPC translations?

引用：`/sources_staging/790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第16页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0196 ← ms-0195 — DROP

语言建议：`KEEP_QUERY`。英文两栏目问题本身自然且与原父问题一致；但父样本跨页gold已建议DROP，不能仅凭翻译合格放行。

父版本状态：父ms-0195的Summary与Background清单跨物理18–19页；延续PV已审表的DROP。不是文档无答案。

比较基准中文：根据 GVP Module XV Annex II 的 DHPC (Direct Healthcare Professional Communication) 信件模板，正文中 Summary 部分与 Background on the safety concern 部分分别应包含哪些具体内容要素？

保留英文：According to the DHPC template in GVP Module XV Annex II, what specific content elements should the 'Summary' section and the 'Background on the safety concern' section of a DHPC letter include?

引用：`/sources_staging/790ce9ffdcf7a785c9de90904e295f4e228bdd0b0974c40c3d51cd13659af53a.pdf`，物理第18页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0198 ← ms-0197 — OK

语言建议：`REVISE_QUERY`。按修订父问题改为商定计划时应考虑的时间点；不将初评e.g. 12-24个月写成强制固定截止。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP Module XVI 对 MAH 与主管机关商定 RMM 有效性评价计划提出了哪些初步评价和总体评价时间点？

原英文：According to GVP Module XVI, at what timepoints after regulatory implementation should marketing authorisation holders conduct the initial and overall effectiveness evaluation of a risk minimisation m…

建议英文：What timepoints does GVP Module XVI identify for MAHs to consider when agreeing with competent authorities on schedules for the initial and overall effectiveness evaluations of risk minimisation measures?

引用：`/sources_staging/9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第19页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0200 ← ms-0199 — OK

语言建议：`KEEP_QUERY`。非干预性PASS被禁止开展的情形、法条及来源一致；不扩成任何研究均禁止。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP Module XVI, 依据DIR Art 107m(3), 非介入性上市后安全性研究(PASS)在什么情况下不得进行？

保留英文：Under DIR Art 107m(3) as referenced in GVP Module XVI, in what situation must a non-interventional post-authorisation safety study (PASS) not be performed?

引用：`/sources_staging/9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第11页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0202 ← ms-0201 — OK

语言建议：`KEEP_QUERY`。问题要求完整处方药分类条件，未仅问某一给药途径；shall与引述条文一致。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据DIR Art 71(1), GVP Module XVI中列出了哪些情况下药品须归类为处方药(subject to medical prescription)？

保留英文：Under DIR Art 71(1) as cited in GVP Module XVI, under what circumstances shall a medicinal product be classified as subject to medical prescription?

引用：`/sources_staging/9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第38页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0204 ← ms-0203 — OK

语言建议：`REVISE_QUERY`。恢复两个雇主类别及for the purposes of this Module的特定定义范围。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP Module XVI对'healthcare professional'的定义，受雇于上市许可持有人或主管机关的具备医事资格人员是否包含在内？

原英文：According to the definition of 'healthcare professional' in GVP Module XVI, does the term include individuals qualified as healthcare professionals who work as employees of a marketing authorisation h…

建议英文：For the purposes of GVP Module XVI, does 'healthcare professional' include qualified healthcare professionals employed by an MAH or a competent authority?

引用：`/sources_staging/9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第7页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0206 ← ms-0205 — OK

语言建议：`REVISE_QUERY`。补全截断的第二个问题；保留各SmPC章节及4.4额外信息，不仅询问材料是否存在。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP Module XVI，SmPC(产品特性概要)各相关章节应呈现哪些与风险最小化措施(RMM)相关的信息，如果该药品配有额外RMM材料，SmPC 4.4节又应额外说明什么？

原英文：According to GVP Module XVI, what RMM-relevant information should be presented in the various SmPC sections, and if a medicinal product has additional RMM materials, what should SmPC section 4.4 addit…

建议英文：According to GVP Module XVI, what information relevant to risk minimisation measures (RMM) should the relevant SmPC sections contain, and what additional information should Section 4.4 include when additional RMM materials are provided?

引用：`/sources_staging/9f4ae57fdfa9aba723fdb41b134889e259ec9919d4ba0f363f4d3df35d18fe1b.pdf`，物理第36页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0208 ← ms-0207 — OK

语言建议：`KEEP_QUERY`。疫苗失败按缺乏疗效上报与时限提问一致；没有自行添加未写明的起算事件。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：疫苗接种失败(vaccination failure)病例应在多少天内作为缺乏疗效(lack of therapeutic efficacy)病例上报?

保留英文：Within how many days should cases of vaccination failure be reported as cases of lack of therapeutic efficacy?

引用：`/sources_staging/0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第24页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0210 ← ms-0209 — OK

语言建议：`REVISE_QUERY`。保留most而不是所有活疫苗，同时增加父问题中的原因。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP P.I 如何概括大多数活减毒疫苗（live attenuated vaccines）在妊娠期的禁忌情况及其原因？

原英文：Are live attenuated vaccines contraindicated for use during pregnancy?

建议英文：How does GVP P.I describe the contraindication of most live attenuated vaccines during pregnancy, and what reason does it give?

引用：`/sources_staging/0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第8页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0212 ← ms-0211 — OK

语言建议：`KEEP_QUERY`。no associated adverse reaction条件及ICSR形式一致；不扩成无需在PSUR等途径考虑。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：未伴随不良反应的疫苗接种错误(vaccination error)是否应作为个案安全性报告(ICSR)提交?

保留英文：Should vaccination errors with no associated adverse reaction be submitted as individual case safety reports (ICSRs)?

引用：`/sources_staging/0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第24页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0214 ← ms-0213 — OK

语言建议：`REVISE_QUERY`。实际来源为P.I的疫苗RMP条款，VI为交叉引用；补回产品识别与制造变更可追溯性两个要点。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP P.I，疫苗 RMP 的常规药物警戒活动部分应如何描述批次相关不良反应的产品识别及制造变更可追溯性？

原英文：According to GVP Module VI, how should routine pharmacovigilance activities in the RMP address traceability of batch-related adverse reactions?

建议英文：According to GVP P.I, how should the routine pharmacovigilance section of a vaccine RMP describe product identification and the traceability of manufacturing changes for batch-related adverse reactions?

引用：`/sources_staging/0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第11页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0216 ← ms-0215 — OK

语言建议：`REVISE_QUERY`。删除开头直接给出Module VIII的答案泄漏；保留P.I为实际来源。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP P.I 指定疫苗上市后安全性研究（PASS）的目标、方法和程序应遵循哪个 GVP 模块？

原英文：According to GVP Module VIII, what should the objectives, methods and procedures for post-authorisation safety studies (PASS) of vaccines follow?

建议英文：Which GVP module does GVP P.I specify should be followed for the objectives, methods and procedures of post-authorisation safety studies of vaccines?

引用：`/sources_staging/0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412.pdf`，物理第14页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0218 ← ms-0217 — OK

语言建议：`KEEP_QUERY`。保留因不构成疑似反应而不提交ICSR的妊娠报告范围；问句并不缩为正常结局一类。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据GVP P.III脚注引用的GVP Module VI规定，哪些妊娠相关报告不应作为ICSR提交，因为不构成疑似不良反应？

保留英文：According to GVP Module VI as cited in GVP P.III, which pregnancy-related reports should not be submitted as ICSRs because they do not constitute a suspected adverse reaction?

引用：`/sources_staging/fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`，物理第9页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0220 ← ms-0219 — OK

语言建议：`KEEP_QUERY`。问的是出生时体重界限，非药物剂量；切片只从已修订父表继承。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP P.III中，新生儿“低出生体重（low birth weight）”的定义体重界限是多少？

保留英文：According to GVP P.III, what is the weight threshold defining 'low birth weight' in a neonate?

引用：`/sources_staging/fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`，物理第7页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0222 ← ms-0221 — OK

语言建议：`KEEP_QUERY`。most recognised EU definition及妊娠周界限保持一致，未声称全球统一定义。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP P.III中，欧盟对流产（miscarriage）最常用定义所依据的妊娠周数界限是多少？

保留英文：According to GVP P.III, what gestational week cut-off defines the most recognised EU definition of miscarriage?

引用：`/sources_staging/fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`，物理第6页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0224 ← ms-0223 — OK

语言建议：`REVISE_QUERY`。补回Reaction/event的MedDRA术语这一父问题要点，不只问途径。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP P.III，母乳喂养造成的药物暴露在 ICH-E2B(R3) 中，应如何填写给药途径和 Reaction/event 部分的 MedDRA 术语？

原英文：According to GVP P.III, how should the route of administration be coded in an ICH-E2B(R3) report for exposure during breastfeeding?

建议英文：According to GVP P.III, how should an ICH-E2B(R3) report record the route-of-administration code and the MedDRA term in the Reaction/event section for exposure through breastfeeding?

引用：`/sources_staging/fab70a9f661fa38f9deef967096f7fc92fcf9730e084a700a4116eba1d273edd.pdf`，物理第9页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0226 ← ms-0225 — OK

语言建议：`KEEP_QUERY`。replace或add requirements的两种否定范围均与父问题一致。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：GVP P.IV 关于儿科人群的指南章节是否会取代或在现有 GVP Module I 至 XVI 所涵盖的监管要求之外再新增要求？

保留英文：Does the GVP P.IV chapter on the paediatric population replace, or add new regulatory requirements beyond, those already covered in GVP Modules I to XVI?

引用：`/sources_staging/e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第4页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0228 ← ms-0227 — OK

语言建议：`KEEP_QUERY`。确切年龄或出生日期无法取得时的替代信息相同，未把二者都未知误成仅缺一项。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在儿科 ICSR 报告中，如果无法获得患儿的确切年龄或出生日期，应改为记录什么信息以替代？

保留英文：In a paediatric ICSR, what information should be recorded instead if the exact age or date of birth cannot be obtained?

引用：`/sources_staging/e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第9页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0230 ← ms-0229 — OK

语言建议：`REVISE_QUERY`。保留豁免理由并采用源文should，不将持续监测建议无条件强化为must。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：药品已获批儿科适应症后，在没有豁免理由的情况下，是否仍需通过 PSUR 持续监测该适应症的风险获益平衡？

原英文：Once a medicine has been granted a paediatric indication, must the risk-benefit balance for that indication continue to be monitored via PSURs unless exemption is justified?

建议英文：Once a paediatric indication has been granted, should its risk-benefit balance continue to be monitored through PSURs unless an exemption from PSUR submission is justified?

引用：`/sources_staging/e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第10页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0232 ← ms-0231 — OK

语言建议：`KEEP_QUERY`。问完整signal定义，非只问信号验证动作；引述法条一致。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据 IR 520/2012 Art 19(1)，什么样的信息可以被认定为一个‘信号’(signal)?

保留英文：According to IR 520/2012 Art 19(1), what information qualifies as a 'signal'?

引用：`/sources_staging/e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第12页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0234 ← ms-0233 — OK

语言建议：`REVISE_QUERY`。随修订父问题覆盖年龄/亚组、缺失处理、发育、父母暴露、出生史，保留相关且可获得限定。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 GVP P.IV 的 P.IV.B.2.1，儿科 ICSR 应怎样记录年龄或年龄亚组、处理年龄资料缺失，并在相关且可获得时补充哪些发育、父母用药暴露及出生史信息？

原英文：According to GVP P.IV, besides the patient's age itself, what specific age-related information should be collected and reported as completely as possible in paediatric ICSRs?

建议英文：Under Section P.IV.B.2.1 of GVP P.IV, how should paediatric ICSRs record age or age group and address missing age information, and what developmental, parental medicine-exposure and birth-history information should be added when relevant and available?

引用：`/sources_staging/e5225fabe9ae7fb363bbfc683e2c7e802ba909d102c56e1c222f48dcf24f4cd4.pdf`，物理第9页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0236 ← ms-0235 — OK

语言建议：`REVISE_QUERY`。保留一般上限与FDA预期，不将初始信息与完成所有随访信息混为一谈。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：对于严重不良事件(SAE)的首次报告,FDA建议研究者向申办者提交初始信息的时限一般不应超过多久?

原英文：For serious adverse events (SAEs), what time frame does FDA recommend for investigators to submit initial SAE information to the sponsor?

建议英文：For an investigator's initial report of a serious adverse event to the sponsor, what general upper time limit does FDA anticipate for submission of the initial information?

引用：`/sources_staging/c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第10页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0238 ← ms-0237 — OK

语言建议：`KEEP_QUERY`。UADE、IDE、首次获知起算及申办者与审查IRB接收对象全部一致。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在IDE研究中,研究者首次获知UADE(unanticipated adverse device effect)后,最迟须在多长时间内向申办者和审查IRB提交报告?

保留英文：In IDE studies, what is the latest deadline for the investigator to submit a UADE report to the sponsor and reviewing IRB after first learning of the effect?

引用：`/sources_staging/c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第12页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0240 ← ms-0239 — OK

语言建议：`KEEP_QUERY`。under §312.64(b)只问该条法规是否要求因果评估；已修订父gold保留申办者可在方案另行要求，未扩大问句。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：依据§ 312.64(b),研究者是否必须对非严重不良事件(nonserious adverse event)进行因果关系评估?

保留英文：Under § 312.64(b), is the investigator required to assess causality for nonserious adverse events?

引用：`/sources_staging/c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第11页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0242 ← ms-0241 — OK

语言建议：`KEEP_QUERY`。判定reasonable possibility的示例提问覆盖全部类别；继承父表已取消long_context，不独立调标。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：依据IND安全报告法规§ 312.32(c)(1)(i)所举实例,判定药物与不良事件之间存在'合理可能性'(reasonable possibility)因果关系时可参考哪些示例情形?

保留英文：According to the examples provided under § 312.32(c)(1)(i) for IND safety reporting, what examples illustrate a 'reasonable possibility' of a causal relationship between a drug and an adverse event?

引用：`/sources_staging/c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第7页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0244 ← ms-0243 — OK

语言建议：`REVISE_QUERY`。补全截断与原父问题的举例要求；不将所有无报告义务事件都扩大成须报IRB。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在IND研究中,除IND安全报告和BA/BE研究中的SAE外,哪些其他类型的事件即使不符合IND安全报告标准,仍必须作为涉及受试者风险的意外问题(unanticipated problem)报告给IRB,请举例说明?

原英文：In IND studies, aside from IND safety reports and SAEs from BA/BE studies, what other types of events must still be reported to the IRB as unanticipated problems involving risk to participants even th…

建议英文：In IND studies, apart from IND safety reports and premarket SAEs from BA/BE studies, what other events must be reported to the IRB as unanticipated problems involving risk to participants even when they do not meet IND safety-reporting criteria? Give examples.

引用：`/sources_staging/c597c1d15d048c48d94be46710658eebdff9c8017f82ec3f04ebd54ad16e577c.pdf`，物理第12页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0246 ← ms-0245 — OK

语言建议：`REVISE_QUERY`。补上父问题明确的2025年12月文件快照；初次收信息起算，避免after information in an IND的歧义。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按所供 FDA《Sponsor Responsibilities》2025年12月版，非预期的致命或危及生命的可疑不良反应应最迟在申办者初次收到信息后多久向 FDA 报告？

原英文：Under this FDA guidance, what is the deadline for a sponsor to report an unexpected fatal or life-threatening suspected adverse reaction to FDA after initial receipt of the information in an IND?

建议英文：According to the supplied December 2025 FDA Sponsor Responsibilities guidance, what is the latest deadline for reporting an unexpected fatal or life-threatening suspected adverse reaction to FDA after the sponsor first receives the information?

引用：`/sources/7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac.pdf`，物理第37页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0248 ← ms-0247 — OK

语言建议：`KEEP_QUERY`。保留IND豁免与境外开展两个同时成立的条件；未误推为境外研究AE信息不入NDA/ANDA。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据FDA该指南,§320.31(d)(3)项下的BA/BE研究安全性报告要求是否适用于豁免IND要求且在美国境外进行的人体BA/BE研究?

保留英文：Under this FDA guidance, do the safety reporting requirements under § 320.31(d)(3) apply to human BA/BE studies that are exempt from IND requirements and conducted outside the United States?

引用：`/sources/7124849af0417893a1c5d93fa6ccf2c4b4c67d5945e09060ae3977f6e0646bac.pdf`，物理第40页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0251 ← ms-0250 — OK

语言建议：`REVISE_QUERY`。对齐修订父问题两个时限：首次通知与额外补交，不只问7日。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 ICH E2A，临床试验中出现符合快速报告条件的致命或危及生命的非预期 ADR，申办者首次获知符合条件后最迟多久通知监管机构，之后多久补交尽可能完整的报告？

原英文：According to ICH E2A, within how many days must a sponsor notify regulatory authorities after first knowledge of a fatal or life-threatening unexpected ADR in a clinical investigation?

建议英文：According to ICH E2A, after a sponsor first learns that a fatal or life-threatening unexpected ADR in a clinical investigation qualifies for expedited reporting, what is the latest deadline for notifying regulators, and how much additional time is allowed for a report that is as complete as possible?

引用：`/sources/1c095d80419287187bf5b2db5eba83864adccebf07b9c593bf5925b4ab6f7cf7.pdf`，物理第7页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0253 ← ms-0252 — OK

语言建议：`REVISE_QUERY`。修正expedited reported不自然搭配并保留usually；不把通常不符合改成绝无例外。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 ICH E2A，安慰剂相关事件通常是否满足 ADR 及快速报告的标准？

原英文：According to ICH E2A, do adverse events associated with placebo treatment need to be expedited reported as ADRs?

建议英文：According to ICH E2A, do events associated with placebo usually meet the criteria for an ADR and, consequently, for expedited reporting?

引用：`/sources/1c095d80419287187bf5b2db5eba83864adccebf07b9c593bf5925b4ab6f7cf7.pdf`，物理第9页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0255 ← ms-0254 — OK

语言建议：`REVISE_QUERY`。保持两个报告区间和DLP；使用should，不将指南提交安排再强化为普遍must。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：PBRER 涵盖 6 个月或 12 个月的报告区间时，应在数据锁定点(DLP)后多少天内完成提交？

原英文：For a PBRER covering a 6-month or 12-month interval, within how many calendar days after the Data Lock Point (DLP) must it be submitted?

建议英文：For a PBRER covering a six- or twelve-month reporting interval, within how many calendar days after the data lock point should it be submitted?

引用：`/sources_staging/0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf`，物理第13页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0257 ← ms-0256 — OK

语言建议：`KEEP_QUERY`。specifically for that purpose准确保留专为撰写PBRER解盲的禁止范围。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在准备 PBRER 时，申办方/药品上市许可持有人(MAH)是否可以为了撰写该报告而专门对临床试验数据解盲？

保留英文：When preparing the PBRER, are sponsors/MAHs permitted to unblind clinical trial data specifically for that purpose?

引用：`/sources_staging/0f883c2e4804d8da84883b205755e7795d4e928e69624fafd2cdaa86db73eada.pdf`，物理第18页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0261 ← ms-0260 — OK

语言建议：`REVISE_QUERY`。补上最低资料及报告条件并保留一般时限，避免将不完整线索收到日无条件当day0。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 ICH E2D，对已满足最低资料和快速报告标准的严重且非预期 ADR，MAH 初次收到信息后的一般最迟快速报告时限是多少？

原英文：For a serious and unexpected ADR, what is the maximum number of days after the MAH's initial receipt of information within which expedited reporting must be completed?

建议英文：According to ICH E2D, for a serious and unexpected ADR that already meets the minimum information and expedited-reporting criteria, what is the general latest reporting deadline after the MAH first receives the information?

引用：`/sources_staging/c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`，物理第10页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0263 ← ms-0262 — OK

语言建议：`KEEP_QUERY`。无伴随不良结果过量事件是否作为反应报告，与父问题完全同义；没有免除收集信息义务。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据ICH E2D，如果药物过量(overdose)但没有伴随不良结果，是否需要作为不良反应报告？

保留英文：Under ICH E2D, if an overdose occurs with no associated adverse outcome, should it be reported as an adverse reaction?

引用：`/sources_staging/c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`，物理第9页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0265 ← ms-0264 — OK

语言建议：`KEEP_QUERY`。daily dose单位示例问题一致；不将整个regimen一并变成新信息请求。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据ICH E2D附件建议的关键数据要素，报告日剂量(Daily dose)时应注明哪些单位示例？

保留英文：According to the ICH E2D attachment's recommended key data elements, what example units should be specified when reporting the daily dose?

引用：`/sources_staging/c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`，物理第14页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0267 ← ms-0266 — OK

语言建议：`REVISE_QUERY`。补回当地/区域说明书明确死亡结局的例外，避免绝对归类。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：按 ICH E2D，预期 ADR 若出现致死结局，何时应按非预期处理，药品当地或区域说明书有何例外？

原英文：If an expected ADR results in a fatal outcome, should it still be considered unexpected?

建议英文：According to ICH E2D, when should an expected ADR with a fatal outcome be treated as unexpected, and what exception depends on the local or regional product labelling?

引用：`/sources_staging/c8a076cc8567c9eb1154f798e1e83aa495f2629c17fcc7bb5c1378eabda0719d.pdf`，物理第6页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0269 ← ms-0268 — OK

语言建议：`KEEP_QUERY`。data mining用于潜在信号发现与量化风险大小的区别保持；例示PRR没有引入新结论。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据ICH E2E，在评估spontaneous reports时使用的data mining技术（如比例报告比）能否用来量化某药物风险的大小？

保留英文：According to ICH E2E, can data mining techniques (e.g., proportional reporting ratios) used to evaluate spontaneous reports be used to quantify the magnitude of a drug's risk?

引用：`/sources_staging/8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`，物理第13页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0271 ← ms-0270 — OK

语言建议：`KEEP_QUERY`。CTD多个章节与Safety Specification问题一致；沿用父问题自带的示例，不单独改写父基线。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据ICH E2E，撰写Safety Specification时，安全性问题的认定应以CTD的哪些具体章节（如Overview of Safety等）为基础？

保留英文：According to ICH E2E, on which specific CTD sections (e.g., Overview of Safety) should the identification of safety issues in the Safety Specification be based?

引用：`/sources_staging/8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`，物理第7页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0273 ← ms-0272 — OK

语言建议：`KEEP_QUERY`。明确问ICH指南及节号两项，非只问某个指南名称。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：ICH E2E参考文献中，关于spontaneous report定义所引用的是哪一份ICH指南及其具体章节编号？

保留英文：In the references of ICH E2E, which ICH guideline and specific section number is cited for the definition of a spontaneous report?

引用：`/sources_staging/8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`，物理第19页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0275 ← ms-0274 — OK

语言建议：`KEEP_QUERY`。Pharmacological Class Effects内容与父问题一致。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：根据ICH E2E，Safety Specification中关于Pharmacological Class Effects的部分应说明什么内容？

保留英文：According to ICH E2E, what should the Pharmacological Class Effects section of the Safety Specification address?

引用：`/sources_staging/8b5ee323558888ad4c3846f85736636c942fb7a84612acde37f7dfadcecfbbb7.pdf`，物理第9页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0277 ← ms-0276 — OK

语言建议：`KEEP_QUERY`。DSUR SAE汇总表是否纳入non-serious events保持，与study report不混淆。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：在DSUR的严重不良事件（SAE）汇总列表（Summary Tabulations）中，是否可以纳入非严重不良事件？

保留英文：In the DSUR's summary tabulations of serious adverse events (SAEs), should non-serious events be included?

引用：`/sources/7912d4d0f2b5fa407a5e8fe3908a7e8262e4034c23409cd903e3646c5b7a693b.pdf`，物理第16页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0279 ← ms-0278 — OK

语言建议：`KEEP_QUERY`。所问定义依据的ICH文件与父问题相同，未将DSUR本身当定义源头。

父版本状态：英文已对齐实际取得的PV修订快照；仍非人工确认及仓库应用结果。

比较基准中文：DSUR文件中的serious adverse reaction、serious adverse event与adverse drug reaction这些术语的定义参照的是哪份ICH指南？

保留英文：In the DSUR, which ICH guideline defines the terms 'serious adverse reaction', 'serious adverse event', and 'adverse drug reaction'?

引用：`/sources/7912d4d0f2b5fa407a5e8fe3908a7e8262e4034c23409cd903e3646c5b7a693b.pdf`，物理第7页。

来源检查范围：`full_revised_parent_key`；本地锚点次数=1。完整PV父span次数=1，key包含于span；第二遍一致。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0301 ← ms-0300 — PENDING_PARENT

语言建议：`REVISE_QUERY`。英文定义对象正确；注明FDA实施版。父样本前轮建议CO转PV，保留语言建议并暂缓，不把部门迁移当作全局删除。

父版本状态：父ms-0300此前仅建议CO→PV迁移；不得误作全局删除。本条保留英文方案，待确认父样本落入PV后整族同步。

比较基准中文：根据ICH E6(R3)术语表并参照ICH E2A,已上市药品的不良药物反应(ADR)应如何定义?

原英文：According to the ICH E6(R3) glossary, referencing ICH E2A, how is an adverse drug reaction (ADR) defined for marketed medicinal products?

建议英文：According to the glossary in FDA's September 2025 E6(R3) guidance, which refers to ICH E2A, how is an adverse drug reaction (ADR) defined for marketed medicinal products?

引用：`/sources_staging/e57e9fc0134abebec409d7144aed6e3047c0939d1bd758163fea4e1169472109.pdf`，物理第77页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0304 ← ms-0303 — DROP

语言建议：`KEEP_QUERY`。英文询问整个1.4程序清单且与父草稿一致；1.4.9跨到物理19页，按前轮裁决排除当前单页样本。

父版本状态：父ms-0303所问完整1.4程序在物理19页仍有1.4.9；按上轮裁决及本轮原PDF重查建议排除当前单页gold。

比较基准中文：根据ICH E6(R3)指南,IRB/IEC应建立、记录并遵循的书面程序(Procedures,1.4)应包含哪些具体事项?

保留英文：According to ICH E6(R3), what specific items should the IRB/IEC's established, documented procedures (section 1.4) include?

引用：`/sources_staging/e57e9fc0134abebec409d7144aed6e3047c0939d1bd758163fea4e1169472109.pdf`，物理第18页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0306 ← ms-0305 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补回appear to waive；原父中文将legal rights缩成法律追责权利，应成对修订。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据21 CFR 50.20，知情同意文件能否包含使受试者放弃、或看似放弃其法律权利的免责语言？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：Under 21 CFR 50.20, can informed consent documents include exculpatory language that makes the subject waive legal rights?

建议英文：Under 21 CFR 50.20, may an informed consent document contain exculpatory language that makes a subject waive, or appear to waive, the subject's legal rights?

引用：`/sources_staging/96b26b2edb06e20ee2872ca59f4ec7c04cde8a8b1adf98bc150764e3d52f906a.pdf`，物理第10页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0308 ← ms-0307 — PENDING_PARENT

语言建议：`KEEP_QUERY`。英文on or after准确包含2012-03-07当天；父草稿‘以后’需明确为‘当日或之后’，本项需父版确认。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：对于2012年3月7日当日或之后启动的适用临床试验，知情同意书中要求的ClinicalTrials.gov声明能否被修改？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

保留英文：For applicable clinical trials initiated on or after March 7, 2012, can the required ClinicalTrials.gov statement in the informed consent form be modified?

引用：`/sources_staging/96b26b2edb06e20ee2872ca59f4ec7c04cde8a8b1adf98bc150764e3d52f906a.pdf`，物理第29页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0310 ← ms-0309 — PENDING_PARENT

语言建议：`KEEP_QUERY`。written documentation required条件与telephone alone限制完全对应；并未排除有书面/电子签署的远程同意。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：当研究要求书面记录知情同意时,能否仅通过电话口头方式获得并记录受试者的知情同意?

保留英文：When written documentation of informed consent is required, can informed consent be obtained and documented solely by oral communication over the telephone?

引用：`/sources_staging/96b26b2edb06e20ee2872ca59f4ec7c04cde8a8b1adf98bc150764e3d52f906a.pdf`，物理第31页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0312 ← ms-0311 — PENDING_PARENT

语言建议：`REVISE_QUERY`。恢复截断问句；wards不是病房儿童，advocate不是刑事辩护律师。显式保留独立性例外，需与中文父问题成对确认。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据21 CFR 50.56(b)(4)，为受国家等机构监护的儿童受试者指定的advocate，与临床试验、研究者或监护机构的关联受到哪些限制，有何角色例外？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：Under 21 CFR 50.56(b)(4), can an individual appointed as an advocate for a ward-of-the-state child subject be associated with the clinical investigation, the investigator, or the guardian organization…

建议英文：Under 21 CFR 50.56(b)(4), what restrictions and exceptions apply to an advocate's association with the clinical investigation, investigators, or guardian organisation when representing a child who is a ward of the state?

引用：`/sources_staging/96b26b2edb06e20ee2872ca59f4ec7c04cde8a8b1adf98bc150764e3d52f906a.pdf`，物理第50页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0315 ← ms-0314 — PENDING_PARENT

语言建议：`KEEP_QUERY`。device供给、未经授权接收人和21 CFR 812.110一致。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据21 CFR 812.110,研究者可否将试验用医疗器械提供给未经授权接收该器械的人?

保留英文：Under 21 CFR 812.110, can an investigator supply an investigational device to a person not authorized to receive it?

引用：`/sources_staging/140b612e6fe3e830256fc9c47794cdf5708b28f2df5d7abe146e14dfd0efadfc.pdf`，物理第16页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0317 ← ms-0316 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补上first learning起算事件，不能将发生日或确认因果日默认为起点。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：依据21 CFR 812.150，研究者首次获知意外器械不良效应后，最迟须在多少个工作日内向申办者和IRB报告？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：Under 21 CFR 812.150, within how many working days must an investigator report an unanticipated adverse device effect to the sponsor and IRB?

建议英文：Under 21 CFR 812.150, within how many working days after first learning of an unanticipated adverse device effect must an investigator report it to the sponsor and IRB?

引用：`/sources_staging/140b612e6fe3e830256fc9c47794cdf5708b28f2df5d7abe146e14dfd0efadfc.pdf`，物理第17页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0319 ← ms-0318 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留未经知情同意的使用及after that use起算；不改为获知后。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：若研究者在未取得知情同意的情况下使用试验器械，依据21 CFR 812.150须在该次使用后多少个工作日内报告？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：If an investigator uses an investigational device without obtaining informed consent, within how many working days must this be reported under 21 CFR 812.150?

建议英文：If an investigator uses an investigational device without obtaining informed consent, within how many working days after that use must the investigator report it under 21 CFR 812.150?

引用：`/sources_staging/140b612e6fe3e830256fc9c47794cdf5708b28f2df5d7abe146e14dfd0efadfc.pdf`，物理第17页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0321 ← ms-0320 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补全展示截断；州法许可不能取代方案规定的资格这一比较没有反转。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据21 CFR 312.23(a)(6)和312.40(a)(1),当方案规定执行特定任务人员的资格时,是否可依当地法律以不同资格人员代替?

原英文：Under 21 CFR 312.23(a)(6) and 312.40(a)(1), if the protocol specifies the qualifications required to perform a task, may individuals with different qualifications permitted under state law perform it …

建议英文：Under 21 CFR 312.23(a)(6) and 312.40(a)(1), if a protocol specifies the qualifications required for a task, may a person with different qualifications perform it instead merely because state law permits this?

引用：`/sources_staging/140b612e6fe3e830256fc9c47794cdf5708b28f2df5d7abe146e14dfd0efadfc.pdf`，物理第6页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0323 ← ms-0322 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保持同时送申办者和IRB的第1组报告；不将第2组仅送申办者的撤回IRB批准报告误归两方。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据21 CFR 812.150,研究者在重大风险医疗器械临床试验中,必须向申办者和IRB提交哪些报告及其提交时限?

原英文：Under 21 CFR 812.150, what reports must an investigator submit to the sponsor and IRB during a significant risk device investigation, and within what time frames?

建议英文：Under the 21 CFR 812.150 reporting list in FDA's Investigator Responsibilities guidance, which reports must an investigator in a significant-risk device investigation submit to both the sponsor and IRB, and what deadlines apply?

引用：`/sources_staging/140b612e6fe3e830256fc9c47794cdf5708b28f2df5d7abe146e14dfd0efadfc.pdf`，物理第17页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0325 ← ms-0324 — DROP

语言建议：`REVISE_QUERY`。原英文漏important且未说明草案；修订语言仅供重建参考，父样本跨页与行号污染阻塞仍保留。

父版本状态：父ms-0324来源为2024年12月草案，页文本有行号且原问题的设计措施跨物理11–12页；需重建父证据，而非只改英文。

比较基准中文：临床试验方案设计阶段，为了从源头降低重要方案偏离（protocol deviation）发生的风险，申办者（sponsor）可以采取哪些具体做法？

原英文：During protocol design, what specific steps can sponsors take to minimize the risk of protocol deviations occurring in a clinical investigation?

建议英文：During protocol design, what specific steps does FDA's December 2024 draft guidance suggest that sponsors can take to reduce the risk of important protocol deviations?

引用：`/sources/3b172d83fd5310029d0933a2efdb821c31d77c31d874e292dff7fb7da9abd42f.pdf`，物理第11页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0327 ← ms-0326 — PENDING_PARENT

语言建议：`REVISE_QUERY`。恢复截断，保留only及initial assessment，未变成只问新增风险。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据FDA的《A Risk-Based Approach to Monitoring of Clinical Investigations Questions and Answers》(April 2023)指南,申办方是否应当只监测在最初风险评估中被认定为重要且可能发生的风险?

原英文：According to FDA's guidance A Risk-Based Approach to Monitoring of Clinical Investigations: Questions and Answers (April 2023), should sponsors monitor only the risks identified as important and likel…

建议英文：According to FDA's April 2023 risk-based monitoring questions-and-answers guidance, should sponsors monitor only risks identified as important and likely to occur during the initial risk assessment?

引用：`/sources_staging/2c0d04faa13f3cfd95bb3b4c5359f699ede4f48dcb055ad2d0ae89d3aa9c423c.pdf`，物理第7页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0329 ← ms-0328 — PENDING_PARENT

语言建议：`REVISE_QUERY`。明确实际依据的2023问答文件，避免同一法条在2013文件出现时引用混淆；仍问原两个义务。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据21 CFR 312.50,申办方对临床试验负有哪些具体的监测与合规义务?

原英文：According to 21 CFR 312.50, what specific monitoring and compliance obligations does a sponsor have for a clinical investigation?

建议英文：According to the passage quoting 21 CFR 312.50 in FDA's April 2023 risk-based monitoring questions-and-answers guidance, what monitoring and compliance obligations does a sponsor have?

引用：`/sources_staging/2c0d04faa13f3cfd95bb3b4c5359f699ede4f48dcb055ad2d0ae89d3aa9c423c.pdf`，物理第5页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0331 ← ms-0330 — PENDING_PARENT

语言建议：`REVISE_QUERY`。恢复截断的SDV，保留all sites与extensive；没有把not necessarily转为完全不许现场监查。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据这份FDA风险监测指南,采用以风险为基础的监测方法是否意味着申办方必须对所有临床试验机构进行频繁的常规巡查和广泛的源数据核实(SDV)?

原英文：According to this FDA risk-based monitoring guidance, does adopting a risk-based monitoring approach mean sponsors must conduct frequent routine visits to all clinical sites and extensive source data …

建议英文：According to FDA's risk-based monitoring guidance, does a risk-based approach require frequent routine visits to all clinical sites and extensive source data verification (SDV)?

引用：`/sources_staging/2c0d04faa13f3cfd95bb3b4c5359f699ede4f48dcb055ad2d0ae89d3aa9c423c.pdf`，物理第9页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0333 ← ms-0332 — PENDING_PARENT

语言建议：`KEEP_QUERY`。问centralized monitoring支持哪些具体活动，未缩为是否现场审查；完整列表需从父gold继承。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据这份FDA指南,集中监测(centralized monitoring)可以帮助申办方开展哪些具体活动?

保留英文：According to this FDA guidance, what specific activities can centralized monitoring help sponsors carry out?

引用：`/sources_staging/2c0d04faa13f3cfd95bb3b4c5359f699ede4f48dcb055ad2d0ae89d3aa9c423c.pdf`，物理第10页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0335 ← ms-0334 — PENDING_PARENT

语言建议：`REVISE_QUERY`。恢复后半句的沟通对象，明确corrective and preventive两类行动；需父完整gold确认全覆盖。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据这份FDA监查指南,申办方在监查(monitoring)中发现重大问题(significant issue)后,应如何开展根本原因分析(root cause analysis)与整改,并将结果沟通给哪些相关方(parties)?

原英文：According to this FDA monitoring guidance, how should sponsors conduct a root cause analysis and corrective actions after significant issues are identified through monitoring, and to which parties sho…

建议英文：According to FDA's monitoring guidance, how should sponsors investigate root causes and take corrective and preventive action after identifying significant issues through monitoring, and to which parties should the issues and actions be communicated?

引用：`/sources_staging/2c0d04faa13f3cfd95bb3b4c5359f699ede4f48dcb055ad2d0ae89d3aa9c423c.pdf`，物理第12页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0337 ← ms-0336 — PENDING_PARENT

语言建议：`REVISE_QUERY`。明确2013原指南为来源，与2023问答不同PDF不互换；不单凭重复条文合并文档。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据21 CFR 312.50，申办者对临床试验监查负有哪些具体职责？

原英文：According to 21 CFR 312.50, what specific monitoring responsibilities does a sponsor have for a clinical investigation?

建议英文：According to the passage quoting 21 CFR 312.50 in FDA's August 2013 risk-based monitoring guidance, what specific monitoring responsibilities does a sponsor have for a clinical investigation?

引用：`/sources_staging/76556b1dcf148a1929f110bb1bfdf17d554630b665d23ad2b885473c5e8f2561.pdf`，物理第5页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0339 ← ms-0338 — PENDING_PARENT

语言建议：`REVISE_QUERY`。限定历史讨论，问exceptional circumstances，不把旧版ICH E6表述冒充2025 R3当前规则。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：按照FDA 2013年指南对ICH E6及ISO 14155:2011的讨论，在什么情况下可以完全依赖集中监查而不进行现场监查？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E6 and ISO 14155:2011, is it acceptable to rely entirely on centralized monitoring with no on-site monitoring at all?

建议英文：According to FDA's 2013 discussion of ICH E6 and ISO 14155:2011, under what circumstances is it appropriate to rely entirely on centralised monitoring without on-site monitoring?

引用：`/sources_staging/76556b1dcf148a1929f110bb1bfdf17d554630b665d23ad2b885473c5e8f2561.pdf`，物理第7页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0341 ← ms-0340 — PENDING_PARENT

语言建议：`REVISE_QUERY`。将业界历史实践和approximately保留，避免被读成当前强制监查周期。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在FDA 2013年指南描述的业界实践中，主要疗效试验的现场监查访视通常约间隔多久？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：For major efficacy trials, at what interval do companies typically schedule on-site monitoring visits?

建议英文：In the industry practices described in FDA's 2013 guidance, at approximately what intervals did companies typically conduct on-site monitoring visits for major efficacy trials?

引用：`/sources_staging/76556b1dcf148a1929f110bb1bfdf17d554630b665d23ad2b885473c5e8f2561.pdf`，物理第6页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0343 ← ms-0342 — PENDING_PARENT

语言建议：`KEEP_QUERY`。可能无法远程访问EHR的理由对应隐私、安全及技术挑战；未把可能性写成绝对禁令。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：为什么申办者可能无法远程访问医院、大学等机构保存的电子病历？

保留英文：Why might sponsors not have remote access to electronic health records maintained by hospitals, universities, and other institutions?

引用：`/sources_staging/76556b1dcf148a1929f110bb1bfdf17d554630b665d23ad2b885473c5e8f2561.pdf`，物理第12页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0345 ← ms-0344 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补全截断并保留新疗法、外部对照、戏剧性疗效希望和可信证明疗效条件；完整理由需要父span含后续说明。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在评估某个新疗法是否值得以外部对照(externally controlled)试验的方式提前测试时，为什么不能仅因为渴望出现戏剧性疗效，就开展没有现实机会可信证明该疗法疗效的试验？

原英文：When considering whether to test a promising new therapy early using an externally controlled design, why is it not acceptable to conduct a trial that has no realistic chance of credibly demonstrating…

建议英文：When considering an externally controlled trial of a promising new therapy, why should hopes of a dramatic benefit not justify a study with no realistic chance of credibly demonstrating efficacy?

引用：`/sources_staging/034b29a6d1b565e4f466fd17df8b6506a7b65508328701b14b11fc42ed0c1881.pdf`，物理第32页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0347 ← ms-0346 — PENDING_PARENT

语言建议：`REVISE_QUERY`。实际gold源文件为E10，E9为交叉引用，不能声称已直接读取E9对应条款。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：按照ICH E10引用ICH E9的说明，在非劣效性或等效性试验中，活性对照治疗应满足什么条件？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E9, what condition must the active control drug satisfy in a non-inferiority or equivalence active-controlled trial?

建议英文：According to ICH E10's discussion citing ICH E9, what condition must an active control treatment meet in a non-inferiority or equivalence trial?

引用：`/sources_staging/034b29a6d1b565e4f466fd17df8b6506a7b65508328701b14b11fc42ed0c1881.pdf`，物理第28页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0349 ← ms-0348 — PENDING_PARENT

语言建议：`KEEP_QUERY`。相对安慰剂最小疗效与非劣效界值的关系保持，英文未把所有有效药物概括成无法估计。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：为什么在某些药物即使被证实有效，也难以可靠地确定其相对安慰剂的最小疗效，从而难以设定非劣效性(non-inferiority)试验的边界(margin)？

保留英文：Why is it difficult to reliably determine the minimum effect size of certain effective drugs relative to placebo, making it hard to set a non-inferiority margin?

引用：`/sources_staging/034b29a6d1b565e4f466fd17df8b6506a7b65508328701b14b11fc42ed0c1881.pdf`，物理第16页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0351 ← ms-0350 — PENDING_PARENT

语言建议：`REVISE_QUERY`。源选句直接给伦理判断，不独立给完整原因；改为判断式问法，需父中文成对改写，不以医学常识补gold。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E10，在急性心肌梗死患者中开展血栓溶解剂的安慰剂对照试验，是否被认为合乎伦理？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E10, why would it not be considered ethical to conduct a placebo-controlled trial of a thrombolytic agent in patients with acute myocardial infarction?

建议英文：According to ICH E10, would a placebo-controlled trial of a thrombolytic agent in patients with acute myocardial infarction be considered ethical?

引用：`/sources_staging/034b29a6d1b565e4f466fd17df8b6506a7b65508328701b14b11fc42ed0c1881.pdf`，物理第25页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0353 ← ms-0352 — PENDING_PARENT

语言建议：`REVISE_QUERY`。原under what condition can将必要条件误读为充分许可；保留necessary前提，不宣称满足即足以入组。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E11(R1)的伦理原则,除非满足什么条件,否则不应将儿童纳入临床试验?

原英文：According to ICH E11(R1) ethical principles, under what condition can children be enrolled in a clinical trial, and when should they not be?

建议英文：Under the ethical principles in ICH E11(R1), what necessary condition must be met before children should be enrolled in a clinical study?

引用：`/sources_staging/be9f56e84b67bb2d726c24da0096340e2788e92d7197bbd0f2d4f72972299763.pdf`，物理第16页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0355 ← ms-0354 — PENDING_PARENT

语言建议：`KEEP_QUERY`。仅问term newborn neonatal period；未误用早产儿预产期加27天规则。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E11(R1) Section 4,足月新生儿(term newborn infant)的新生儿期(neonatal period)如何界定?

保留英文：According to ICH E11(R1) Section 4, how is the neonatal period defined for term newborn infants?

引用：`/sources_staging/be9f56e84b67bb2d726c24da0096340e2788e92d7197bbd0f2d4f72972299763.pdf`，物理第18页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0357 ← ms-0356 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留may be necessary和发育亚组，避免将所有亚组一律要求不同终点。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：ICH E11(R1)第6.2节引用E11(2000)第2.4.2节时，对特定年龄及发育亚组可能需要不同终点作了什么说明？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：What does ICH E11(2000) Section 2.4.2, as cited in ICH E11(R1) Section 6.2, state about endpoints for pediatric age subgroups?

建议英文：What does ICH E11 (2000) Section 2.4.2, as cited in ICH E11(R1) Section 6.2, say about the possible need for different endpoints for specific paediatric age and developmental subgroups?

引用：`/sources_staging/be9f56e84b67bb2d726c24da0096340e2788e92d7197bbd0f2d4f72972299763.pdf`，物理第22页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0359 ← ms-0358 — PENDING_PARENT

语言建议：`REVISE_QUERY`。条款位于原始E11部分而非R1新增条款；may/many和成人比较保留，不将mg/kg自行纠正为另一单位。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：按E11(R1)合订文件中原始ICH E11第2.5.3节，到1至2岁时，许多药物按mg/kg基础表达的清除率可能与成人值有何关系？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E11(R1), how does drug clearance on a mg/kg basis typically change by 1 to 2 years of age in infants and toddlers?

建议英文：According to Section 2.5.3 of the original ICH E11 text included with E11(R1), how may the clearance of many drugs, expressed on a mg/kg basis, compare with adult values by one to two years of age?

引用：`/sources_staging/be9f56e84b67bb2d726c24da0096340e2788e92d7197bbd0f2d4f72972299763.pdf`，物理第12页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0361 ← ms-0360 — PENDING_PARENT

语言建议：`REVISE_QUERY`。区分原始E11特征清单与R1新增部分；不将important features自动扩展为全部研究设计问题。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：按照E11(R1)合订文件中原始ICH E11第2.5.1节，制定早产新生儿临床研究方案时，应考虑该人群哪些重要特征？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E11(R1), what important features should be considered when designing clinical trial protocols for preterm newborn infants?

建议英文：According to Section 2.5.1 of the original ICH E11 text included with E11(R1), what important characteristics of preterm newborn infants should be considered when developing a clinical study protocol?

引用：`/sources_staging/be9f56e84b67bb2d726c24da0096340e2788e92d7197bbd0f2d4f72972299763.pdf`，物理第11页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0363 ← ms-0362 — PENDING_PARENT

语言建议：`KEEP_QUERY`。short-term duration与剂量反应表征一致；不将4-12周擅自变为所有降压药全疗程。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在评估新降压药物血压反应与剂量关系时，短期研究通常应持续多长时间？

保留英文：How long should short-term studies typically last when characterizing the blood pressure response and dose relationship for a new antihypertensive drug?

引用：`/sources_staging/d09627c2d02dc3c6675be445232a7312e0aa295f6b1748da68fc9d771405a9ac.pdf`，物理第6页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0365 ← ms-0364 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留e.g.例示性质，不把>90 mmHg写成普适无应答定义。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在ICH E12A第6.2节评估固定复方降压药的示例中，列举了什么舒张压值来说明患者对某单一成分无应答？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：In non-responder trial designs for fixed-dose combination antihypertensive products, what diastolic blood pressure threshold defines failure to respond to a single component?

建议英文：In the example in Section 6.2 of ICH E12A, what diastolic blood pressure value illustrates a failure to respond to an individual component when studying a fixed combination of antihypertensive drugs?

引用：`/sources_staging/d09627c2d02dc3c6675be445232a7312e0aa295f6b1748da68fc9d771405a9ac.pdf`，物理第9页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0367 ← ms-0366 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补回慢性用药一般规模、暴露时长及降压药人群可能偏小的限定；实际引述源为E12A。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：ICH E12A引用ICH E1时，给出的慢性用药一般患者暴露数据库规模及暴露时长是什么，对降压药的适用性又有何限制？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E1, what patient exposure database size is generally recommended for assessing the safety of a new antihypertensive drug?

建议英文：What general patient-exposure database size and exposure durations does ICH E12A cite from ICH E1 for chronically administered drugs, and what limitation does it note for antihypertensive drugs?

引用：`/sources_staging/d09627c2d02dc3c6675be445232a7312e0aa295f6b1748da68fc9d771405a9ac.pdf`，物理第8页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0369 ← ms-0368 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保持三个剂量点这一任务，清楚区分E12A实际引用PDF与E4交叉引用。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：按照ICH E12A引用ICH E4的说明，剂量-反应研究应识别曲线上的哪些关键剂量点？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E4, which critical dose points on the D/R curve should be identified in dose-response studies?

建议英文：According to ICH E12A's discussion referring to ICH E4, which critical dose points should dose-response studies identify on the dose-response curve?

引用：`/sources_staging/d09627c2d02dc3c6675be445232a7312e0aa295f6b1748da68fc9d771405a9ac.pdf`，物理第8页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0371 ← ms-0370 — PENDING_PARENT

语言建议：`KEEP_QUERY`。问本文件所列E1主题，未将其展开成实际安全性暴露人数。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在本文件引用的相关ICH指南列表中，ICH E1对应的主题是什么？

保留英文：According to the list of related ICH guidelines cited in this document, what topic does ICH E1 correspond to?

引用：`/sources_staging/d09627c2d02dc3c6675be445232a7312e0aa295f6b1748da68fc9d771405a9ac.pdf`，物理第5页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0373 ← ms-0372 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补全截断；明确基线重复测量、ms、建议示例，不视为单次测量绝对禁入阈值。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在药物对QT/QTc的影响尚未明确时，ICH E14列举何种反复测得的基线QTc毫秒值作为建议排除受试者的示例？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E14, before the effect of a drug on the QT/QTc interval has been characterized, what repeated baseline QTc interval value is suggested as an exclusion criterion for subject enrollment…

建议英文：Before a drug's effect on the QT/QTc interval has been characterised, what repeated baseline QTc value, in milliseconds, does ICH E14 give as an example supporting exclusion from a trial?

引用：`/sources_staging/6199a1a27063c31e6d935e062ad0b581618f123473b13a854fe61eea5ffe0a5c.pdf`，物理第6页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0375 ← ms-0374 — PENDING_PARENT

语言建议：`REVISE_QUERY`。加入appear保留证据不确定性，不能把do not appear to cause改成绝不导致TdP。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：按照ICH E14对thorough QT/QTc研究的解读，使平均QT/QTc延长约5 ms或更少的药物，是否看起来会引起TdP？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：Under ICH E14's interpretation of the 'thorough QT/QTc study', if a drug prolongs the mean QT/QTc interval by around 5 ms or less, does it cause TdP?

建议英文：Under ICH E14's interpretation of the thorough QT/QTc study, do drugs that prolong the mean QT/QTc interval by around 5 ms or less appear to cause TdP?

引用：`/sources_staging/6199a1a27063c31e6d935e062ad0b581618f123473b13a854fe61eea5ffe0a5c.pdf`，物理第9页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0377 ← ms-0376 — PENDING_PARENT

语言建议：`REVISE_QUERY`。明确absolute QTc value，避免读为相对基线增加500 ms；不是药物剂量单位。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在ICH E14的分类分析讨论中，治疗期间QTc绝对间期超过多少毫秒被视为特别关注？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E14's provisions on categorical analysis of the QT/QTc interval, what QTc prolongation threshold (in ms) during clinical trials is considered of particular concern?

建议英文：In ICH E14's discussion of categorical analyses, above what absolute QTc interval value, in milliseconds, during treatment is particular concern noted?

引用：`/sources_staging/6199a1a27063c31e6d935e062ad0b581618f123473b13a854fe61eea5ffe0a5c.pdf`，物理第14页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0379 ← ms-0378 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补足ECG及其他临床资料已引起怀疑的条件，保留sufficient否定范围。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E14，若ECG及其他临床资料已提示潜在致心律失常风险，药物申请数据库未观察到TdP是否足以排除该风险？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E14, if no episode of TdP is observed in a drug application safety database, can the possible arrhythmogenic risk of the drug be dismissed on that basis?

建议英文：According to ICH E14, when ECG and other clinical data suggest possible arrhythmogenic risk, is the absence of TdP episodes in a drug application database sufficient to dismiss that risk?

引用：`/sources_staging/6199a1a27063c31e6d935e062ad0b581618f123473b13a854fe61eea5ffe0a5c.pdf`，物理第15页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0381 ← ms-0380 — PENDING_PARENT

语言建议：`KEEP_QUERY`。genomic biomarker定义问题一致；不用proteomic概念替代DNA/RNA。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E15指南，基因组生物标志物（genomic biomarker）的定义是什么？

保留英文：According to the ICH E15 guideline, what is the definition of a genomic biomarker?

引用：`/sources_staging/40516566c939436147ade1b076a2e46d716755d3062c1102732ae394cf8e02fc.pdf`，物理第5页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0383 ← ms-0382 — PENDING_PARENT

语言建议：`KEEP_QUERY`。pharmacogenetics(PGt)与pharmacogenomics(PGx)区分正确。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E15，药物遗传学（Pharmacogenetics, PGt）的定义是什么？

保留英文：According to ICH E15, how is pharmacogenetics (PGt) defined?

引用：`/sources_staging/40516566c939436147ade1b076a2e46d716755d3062c1102732ae394cf8e02fc.pdf`，物理第6页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0385 ← ms-0384 — PENDING_PARENT

语言建议：`KEEP_QUERY`。identified数据/样本及generally保留，不误换成coded或anonymised。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E15，已识别（identified）数据和样本是否一般被认为适合用于药物开发的临床试验？

保留英文：According to ICH E15, are identified data and samples generally considered appropriate for use in clinical trials in drug development?

引用：`/sources_staging/40516566c939436147ade1b076a2e46d716755d3062c1102732ae394cf8e02fc.pdf`，物理第7页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0387 ← ms-0386 — PENDING_PARENT

语言建议：`KEEP_QUERY`。保留anonymised类别及clinical monitoring/subject follow-up，未误称anonymous。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E15，匿名化（anonymised）数据和样本是否可以用于对受试者进行临床监测或随访？

保留英文：According to ICH E15, can anonymised data and samples be used for clinical monitoring or subject follow-up?

引用：`/sources_staging/40516566c939436147ade1b076a2e46d716755d3062c1102732ae394cf8e02fc.pdf`，物理第8页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0389 ← ms-0388 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留some instances和examples，不能把年龄/胆固醇示例误当所有匿名样本必需字段。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：ICH E15对某些情况下匿名基因组样本可关联的有限临床数据，列举了哪些示例？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E15, what limited clinical data can be associated with anonymous genomic samples in some instances?

建议英文：What examples does ICH E15 give of the limited clinical data that may be associated with anonymous genomic samples in some instances?

引用：`/sources_staging/40516566c939436147ade1b076a2e46d716755d3062c1102732ae394cf8e02fc.pdf`，物理第8页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0391 ← ms-0390 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补回doses，原英文只问药物；需中文父问题成对包含剂量。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：按照ICH E17，MRCT方案对允许及不允许的合并用药及其剂量应作什么规定？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：How should an MRCT protocol distinguish between allowable and not allowable concomitant medications?

建议英文：According to ICH E17, what should an MRCT protocol specify about allowable and non-allowable concomitant medications and their doses?

引用：`/sources_staging/e67211a8358fa94236ef0a0dd0a76538271584ab93a71b9f9bf841d94d3f5371.pdf`，物理第28页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0393 ← ms-0392 — PENDING_PARENT

语言建议：`KEEP_QUERY`。所有地区和中心遵守E6 GCP及监管检查均与父问题一致。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：MRCT的所有参与地区和场所应如何符合ICH E6 GCP标准,并配合哪些监管检查?

保留英文：How should all regions and sites participating in an MRCT comply with ICH E6 GCP standards and what regulatory inspections should they accommodate?

引用：`/sources_staging/e67211a8358fa94236ef0a0dd0a76538271584ab93a71b9f9bf841d94d3f5371.pdf`，物理第9页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0395 ← ms-0394 — PENDING_PARENT

语言建议：`KEEP_QUERY`。一个/部分地区已有终点经验、采纳前条件一致；未将各区域有经验当先决事实。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：如果MRCT的主要终点仅在少数地区有既往应用经验,该终点的采纳需要满足什么条件?

保留英文：If prior experience with a primary endpoint exists only in a subset of regions in an MRCT, what is required before it can be adopted?

引用：`/sources_staging/e67211a8358fa94236ef0a0dd0a76538271584ab93a71b9f9bf841d94d3f5371.pdf`，物理第15页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0397 ← ms-0396 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留may、疾病流行率差异和监管讨论；新增讨论要点须中文父题同步，不独立扩大孪生。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在罕见病或传染病暴发的MRCT中，各地区疾病流行率差异很大时可如何分配招募，计划阶段应与谁讨论该策略？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：For MRCTs in rare diseases or infectious disease outbreaks, how should sample size allocation be handled when disease prevalence differs substantially across regions?

建议英文：For an MRCT involving a rare disease or an infectious disease outbreak, how may recruitment be allocated when disease prevalence differs substantially across regions, and with whom should the recruitment strategy be discussed during planning?

引用：`/sources_staging/e67211a8358fa94236ef0a0dd0a76538271584ab93a71b9f9bf841d94d3f5371.pdf`，物理第21页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0399 ← ms-0398 — PENDING_PARENT

语言建议：`KEEP_QUERY`。总留存期受知情同意限制；英文没有把推荐长期存储当作无限期限。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E18,基因组样本的储存时间是否可以超过知情同意书所载明的留存期限?

保留英文：According to ICH E18, can genomic samples be stored longer than the retention period specified in the informed consent document?

引用：`/sources_staging/5dbb1b7247cf7ac1fd9629e3545e20df95b648785dfa50b0024fae96b49eb418.pdf`，物理第8页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0401 ← ms-0400 — PENDING_PARENT

语言建议：`REVISE_QUERY`。区分种系序列相对稳定与肿瘤DNA/RNA所获信息受来源、方法及时间影响；不保证所有DNA不变。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E18，计划样本采集时，种系DNA的时间稳定性与影响肿瘤DNA/RNA所获信息的因素有何不同？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E18, how does temporal stability differ between germline DNA and tumor DNA/RNA when selecting specimen collection timing?

建议英文：According to ICH E18, how do the temporal stability of germline DNA and the factors affecting information from tumour DNA and RNA differ when specimen collection is planned?

引用：`/sources_staging/5dbb1b7247cf7ac1fd9629e3545e20df95b648785dfa50b0024fae96b49eb418.pdf`，物理第6页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0403 ← ms-0402 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补回whole-genome sequencing，原英文遗漏父题指定的检测方法。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E18,BRCA1基因突变等意外发现(incidental findings)是否可能在并非以癌症风险为研究目的的全基因组测序中被识别?

原英文：According to ICH E18, can BRCA1 mutations be identified as incidental findings even when the research was not intended to investigate cancer risk?

建议英文：According to ICH E18, can whole-genome sequencing identify incidental findings such as BRCA1 mutations even when the research is not intended to investigate cancer risk?

引用：`/sources_staging/5dbb1b7247cf7ac1fd9629e3545e20df95b648785dfa50b0024fae96b49eb418.pdf`，物理第11页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0405 ← ms-0404 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留for each stage，不能只理解为整个分析完成后统一定阈值。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E18,基因组数据分析流程中的QC质控标准应在进入下一阶段分析前如何锁定?

原英文：According to ICH E18, when should QC procedures and thresholds for genomic data analysis be fixed relative to proceeding to downstream analyses?

建议英文：According to ICH E18, when should QC procedures and thresholds be fixed for each stage of a genomic analysis workflow relative to proceeding to downstream analyses?

引用：`/sources_staging/5dbb1b7247cf7ac1fd9629e3545e20df95b648785dfa50b0024fae96b49eb418.pdf`，物理第9页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0407 ← ms-0406 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补全截断并保留generally；不能把非穷尽清单翻成全部必收要素且无例外。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在ICH E19下，采用选择性安全性数据收集方法时，临床试验通常仍应收集哪些安全性相关数据（如严重不良事件、重要医学事件等）？

原英文：Under ICH E19, when a selective safety data collection approach is used, what safety-related data (e.g., serious adverse events, important medical events) should generally still be collected in a clin…

建议英文：Under ICH E19, what safety-related data, such as serious adverse events and important medical events, should generally still be collected when a selective safety data collection approach is used in a clinical trial?

引用：`/sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf`，物理第8页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0409 ← ms-0408 — PENDING_PARENT

语言建议：`REVISE_QUERY`。原二元问法超出单一因素条款；2.2说明单个因素不决定可否采用。改问一般比较原则，需父中文同步，不能用not exceed证明绝对禁止。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E19，考虑选择性安全性数据收集时，拟定剂量及给药频率通常应与既往用于明确药物安全性的试验如何比较？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E19, if the planned dose or dosing frequency in a proposed trial exceeds that used in previous trials that characterised the drug's safety, can selective safety data collection still …

建议英文：Under ICH E19, how should the planned dose and dosing frequency generally compare with those used in previous trials that characterised the drug's safety when selective safety data collection is being considered?

引用：`/sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf`，物理第7页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0411 ← ms-0410 — PENDING_PARENT

语言建议：`REVISE_QUERY`。恢复三组数据、接种后时间起点及pre-specified AESI；答案中保留e.g./approximately/at least。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E19中预防性疫苗(preventive vaccine)选择性安全性数据收集示例，方案中对征集性体征症状、非征集性不良事件及严重不良事件/AESI分别设定了多长的数据收集时间窗？

原英文：In the ICH E19 example of a preventive vaccine trial using selective safety data collection, what time windows are specified for collecting solicited signs/symptoms, unsolicited adverse events, and se…

建议英文：In ICH E19's preventive-vaccine example, what post-vaccination collection windows are described for solicited signs and symptoms, unsolicited adverse events, and serious adverse events and pre-specified AESIs?

引用：`/sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf`，物理第11页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0413 ← ms-0412 — PENDING_PARENT

语言建议：`KEEP_QUERY`。基因治疗是否在本指南适用范围内一致，不延伸成所有可选择性收集方法理论上均不适用。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E19，选择性安全性数据收集的原则是否适用于基因治疗(gene therapy)临床试验？

保留英文：According to ICH E19, does the selective safety data collection approach apply to gene therapy clinical trials?

引用：`/sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf`，物理第6页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0415 ← ms-0414 — DROP

语言建议：`KEEP_QUERY`。英文和父问题同义，但父0414已因与0406重复建议排除；不创建新的父ID或自动重挂到0406。

父版本状态：父ms-0414与ms-0406为同文档同条款的重复问题；按上轮裁决建议排除0414及其本孪生。不自动重挂至0406。

比较基准中文：根据ICH E19,在临床试验中采用选择性安全性数据收集(selective safety data collection)方法时,通常仍应收集哪些安全性数据要素?

保留英文：According to ICH E19, what safety data elements should generally still be collected when a selective safety data collection approach is used in a clinical trial?

引用：`/sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf`，物理第8页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0417 ← ms-0416 — PENDING_PARENT

语言建议：`REVISE_QUERY`。问可接受的剂量表达方式，不要求原文未给出的单位换算公式；使用may及where appropriate。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在ICH E3临床研究报告的暴露程度部分，剂量可以采用哪些表达方式，包括何时可按mg/kg或mg/m²表达？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：In the Extent of Exposure section of an ICH E3 clinical study report, how should dosage be expressed, e.g., as mg/kg or mg/m²?

建议英文：In the Extent of Exposure section of an ICH E3 clinical study report, in what ways may dosage be expressed, including on a mg/kg or mg/m² basis where appropriate?

引用：`/sources_staging/032d53bb6d693151b64bdc87aa4cf42b90e096db6e52dad73c2093cd62ffa24d.pdf`，物理第28页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0419 ← ms-0418 — PENDING_PARENT

语言建议：`KEEP_QUERY`。控制篇幅与过量使用符号的关系一致，不禁止合理缩略语。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E3,临床研究报告中的数据列表为控制篇幅,是否可以过度使用符号代替文字说明?

保留英文：According to ICH E3, can data listings in a clinical study report overuse symbols instead of words merely to control size?

引用：`/sources_staging/032d53bb6d693151b64bdc87aa4cf42b90e096db6e52dad73c2093cd62ffa24d.pdf`，物理第10页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0421 ← ms-0420 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补足置信区间与预设不可接受劣效程度的关系；不是只要求给出某个区间；父题需明确这两个要点。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：依ICH E3第11.4.2.7节，旨在显示等效性的主动对照试验应呈现关键终点的何种置信区间比较，以及该区间与预设不可接受劣效程度的什么关系？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：What does ICH E3 Section 11.4.2.7 require regarding the confidence interval analysis for active-control equivalence trials?

建议英文：In an active-control study intended to show equivalence, what should the analysis show about the confidence interval for critical endpoints and its relation to the pre-specified unacceptable degree of inferiority under ICH E3 Section 11.4.2.7?

引用：`/sources_staging/032d53bb6d693151b64bdc87aa4cf42b90e096db6e52dad73c2093cd62ffa24d.pdf`，物理第25页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0423 ← ms-0422 — PENDING_PARENT

语言建议：`KEEP_QUERY`。every adverse event及rigorous statistical evaluation范围一致，未误成不用任何安全性分析。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E3,是否要求对每一个不良事件都进行严格的统计学评估?

保留英文：According to ICH E3, is it required that every adverse event be subjected to rigorous statistical evaluation?

引用：`/sources_staging/032d53bb6d693151b64bdc87aa4cf42b90e096db6e52dad73c2093cd62ffa24d.pdf`，物理第30页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0425 ← ms-0424 — PENDING_PARENT

语言建议：`KEEP_QUERY`。individual patient laboratory changes by treatment group而非只比较组均值；英文自然，继承标签待CO父版核验。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E3第12.4.2.2节,在分析个别病人化验数值随治疗组别的变化(individual patient changes)时,可以采用哪些具体分析方法?

保留英文：According to ICH E3 Section 12.4.2.2, what specific approaches can be used to analyze individual patient changes in laboratory values by treatment group?

引用：`/sources_staging/032d53bb6d693151b64bdc87aa4cf42b90e096db6e52dad73c2093cd62ffa24d.pdf`，物理第34页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0427 ← ms-0426 — PENDING_PARENT

语言建议：`KEEP_QUERY`。来源为ICH原版而非FDA实施版；documented approval/favourable opinion与入组前提对应。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E6(R3)，在IRB/IEC作出书面批准（approval/favourable opinion）之前，能否将受试者纳入临床试验？

保留英文：Under ICH E6(R3), can a participant be enrolled in a trial before the IRB/IEC issues its documented approval/favourable opinion?

引用：`/sources/e6ce19e36ce7d2e294f89ee89492b9e035178c3cca48984392bbd92eec9b002c.pdf`，物理第17页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0429 ← ms-0428 — DROP

语言建议：`KEEP_QUERY`。英文语言正确；父0428前轮建议因重复排除，保留原ICH PDF路径而不换到FDA文件。

父版本状态：上轮建议父ms-0428因与ms-0302报酬问题语义重复而排除；孪生随之建议排除。不合并、替换ICH与FDA两个不同PDF。

比较基准中文：根据ICH E6(R3)，受试者获得的试验相关报酬能否完全取决于其是否完成整个试验？

保留英文：Under ICH E6(R3), can a trial participant's payment be wholly contingent on completing the entire trial?

引用：`/sources/e6ce19e36ce7d2e294f89ee89492b9e035178c3cca48984392bbd92eec9b002c.pdf`，物理第16页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0431 ← ms-0430 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留unnecessarily而非禁止一切合并症排除；避免绝对化。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E7，老年患者试验方案是否应不必要地排除有合并疾病的患者？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E7, should patients with concomitant illnesses be excluded from geriatric clinical trial protocols?

建议英文：According to ICH E7, should geriatric trial protocols unnecessarily exclude patients because they have concomitant illnesses?

引用：`/sources_staging/cbe681cf342eeefb477c1a30770d12798fadcf2d00079faa0aa66047ce4ca330.pdf`，物理第4页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0433 ← ms-0432 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补回specific reason to expect条件，不能只因说明书未涵盖就无条件适用。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E7，已有药品的新剂型或新复方若有具体理由预期会遇到说明书尚未处理的老年人常见状况，是否也适用本指南？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E7, does the guideline apply to new formulations or combinations of established drugs when conditions common in the elderly are not already addressed in current labelling?

建议英文：According to ICH E7, does the guideline also apply to new formulations or combinations of established medicines when there is a specific reason to expect conditions common in older patients that are not already addressed in current labelling?

引用：`/sources_staging/cbe681cf342eeefb477c1a30770d12798fadcf2d00079faa0aa66047ce4ca330.pdf`，物理第3页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0435 ← ms-0434 — PENDING_PARENT

语言建议：`KEEP_QUERY`。all relevant age groups与有重要用途的相关年龄范围一致，未扩大为每个不相关年龄组。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E7的一般原则,新药临床试验是否应涵盖包括老年人在内的所有相关年龄组?

保留英文：According to the General Principle of ICH E7, should new drugs be studied in all relevant age groups, including the elderly?

引用：`/sources_staging/cbe681cf342eeefb477c1a30770d12798fadcf2d00079faa0aa66047ce4ca330.pdf`，物理第3页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0437 ← ms-0436 — PENDING_PARENT

语言建议：`KEEP_QUERY`。替代单独老年PK评价的方法提问一致；完整答案应包括结合主要III期及可选II期，不只说screen。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E7,申办方若不单独进行老年人药代动力学评价,可以采用什么替代方法?

保留英文：According to ICH E7, what alternative approach can sponsors use instead of conducting a separate pharmacokinetic evaluation in the elderly?

引用：`/sources_staging/cbe681cf342eeefb477c1a30770d12798fadcf2d00079faa0aa66047ce4ca330.pdf`，物理第5页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0439 ← ms-0438 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留special planning及best accomplished，不把较适宜独立开展写成必须独立试验。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E7，认知功能等评估是否需要特别规划，以及是否更适合在独立研究中开展？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to ICH E7, should assessments such as cognitive function studies be conducted as separate trials rather than combined with the main studies?

建议英文：According to ICH E7, do assessments such as cognitive function studies require special planning, and are they best carried out in separate studies?

引用：`/sources_staging/cbe681cf342eeefb477c1a30770d12798fadcf2d00079faa0aa66047ce4ca330.pdf`，物理第4页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0441 ← ms-0440 — PENDING_PARENT

语言建议：`REVISE_QUERY`。把一律常规开展改成具体情形考虑、逐案决定且通常推荐；完整gold仍需保留PK筛查已排除的重要相互作用例外。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E7，在什么情况下应考虑具体的药物相互作用研究，针对老年患者用药又通常推荐哪些研究类型？

上句为本轮新拟的中文配对建议，未写回父样本，不能冒充上轮CO修订原文。

原英文：According to the ICH E7 guideline, under what circumstances are drug-drug interaction studies ordinarily recommended for geriatric patients, and what specific types of studies should be included?

建议英文：According to ICH E7, in what circumstances should specific drug-drug interaction studies be considered, and which types are ordinarily recommended in the context of drug use in older patients?

引用：`/sources_staging/cbe681cf342eeefb477c1a30770d12798fadcf2d00079faa0aa66047ce4ca330.pdf`，物理第6页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0443 ← ms-0442 — PENDING_PARENT

语言建议：`KEEP_QUERY`。次要事项源于扩展性次要目标，与原文minor issues相同；非一概排除所有次要终点。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在临床试验方案设计中，关键质量因子(critical to quality factors)是否应纳入因扩展性次要目标而产生的次要问题？

保留英文：When designing a clinical trial protocol, should critical to quality factors include minor issues arising from extensive secondary objectives?

引用：`/sources/99d56638828c823bb603ff3ef451fcfafc607de8a5b3926136d64980f27baa13.pdf`，物理第11页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0445 ← ms-0444 — PENDING_PARENT

语言建议：`KEEP_QUERY`。二次数据未记载不等于没发生；没有把缺失当作肯定证据。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在使用外部/次要数据来源(secondary data use)开展临床研究时，若某疾病或事件在数据中未被记录，能否因此判定该事件未曾发生？

保留英文：When using secondary/external data sources in a clinical study, does the absence of recorded information about a condition or event mean that it did not occur?

引用：`/sources/99d56638828c823bb603ff3ef451fcfafc607de8a5b3926136d64980f27baa13.pdf`，物理第23页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0447 ← ms-0446 — PENDING_PARENT

语言建议：`REVISE_QUERY`。保留in general及terminal intercurrent events；没有声称所有临床变量在死亡后均无法定义。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E9(R1)附录A.3.2.对treatment policy strategy的说明，为什么这一策略不能用于处理terminal events（如死亡）这类intercurrent event？

原英文：According to the description of the treatment policy strategy in ICH E9(R1) Addendum Section A.3.2., why can this strategy not be implemented for terminal intercurrent events such as death?

建议英文：According to ICH E9(R1) Section A.3.2, why can the treatment policy strategy generally not be implemented for terminal intercurrent events such as death?

引用：`/sources_staging/f7471f411f1c87ee76783d5b2b9faaeca31d01d530213f71b50d136b39e3b0d9.pdf`，物理第9页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0449 ← ms-0448 — PENDING_PARENT

语言建议：`KEEP_QUERY`。保留两个假设：不发生AE或虽AE仍继续治疗；不误作真实可执行治疗方案。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在ICH E9(R1)关于hypothetical strategies的举例中，对于因不良事件而中止治疗的受试者，设想了哪两种假设情境？

保留英文：In the ICH E9(R1) example under hypothetical strategies, what two hypothetical scenarios are envisaged for a subject who discontinues treatment because of an adverse event?

引用：`/sources_staging/f7471f411f1c87ee76783d5b2b9faaeca31d01d530213f71b50d136b39e3b0d9.pdf`，物理第10页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0451 ← ms-0450 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补完整个被截断比较及all patients；principal stratum不是实际PPS人群。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在ICH E9(R1)讨论discontinuation of treatment这一intercurrent event时，能否把基于principal stratum的效应或continued treatment期间的效应解释为‘假如所有病人都能继续治疗’时的效应？

原英文：When ICH E9(R1) discusses discontinuation of treatment as an intercurrent event, can either the principal-stratum-based effect or the effect during continued treatment be interpreted as the effect if …

建议英文：When ICH E9(R1) discusses treatment discontinuation, can either the effect in the principal stratum of patients who could continue on the test treatment or the effect during continued treatment be interpreted as the effect if all patients could continue treatment?

引用：`/sources_staging/f7471f411f1c87ee76783d5b2b9faaeca31d01d530213f71b50d136b39e3b0d9.pdf`，物理第14页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0453 ← ms-0452 — PENDING_PARENT

语言建议：`KEEP_QUERY`。PPS与任何principal stratum估计的区别一致，why保留，需要父gold包含不同治疗组人群不可比的原因。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E9(R1)附录A.5.3.关于supplementary analysis的说明，为什么Per Protocol Set (PPS)分析不能达到估计任何principal stratum效应的目标？

保留英文：According to ICH E9(R1) Addendum Section A.5.3. on supplementary analysis, why does analysis of the Per Protocol Set (PPS) not achieve the goal of estimating the effect in any principal stratum?

引用：`/sources_staging/f7471f411f1c87ee76783d5b2b9faaeca31d01d530213f71b50d136b39e3b0d9.pdf`，物理第20页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0455 ← ms-0454 — PENDING_PARENT

语言建议：`REVISE_QUERY`。按原文描述的双盲做法提问，不自行增加所有包装其他标识都被禁止的强制要求。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在双盲临床试验中，为什么药品包装标签只标示受试者编号和治疗期，而不使用代码字母等其他识别方式？

原英文：In a double-blind clinical trial, why should drug packaging be labelled only with the subject number and treatment period rather than using a code letter or other identifying marks?

建议英文：In the double-blind approach described in ICH E9, why are treatment packs labelled only with the subject number and treatment period, rather than revealing treatment identity even as a code letter?

引用：`/sources_staging/0c0ddc93cb427a70265dbcb0e7c25bfc9a3f7b52e178212b3630ea2408ad9c7e.pdf`，物理第12页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0457 ← ms-0456 — PENDING_PARENT

语言建议：`REVISE_QUERY`。补全截断问句，仍问排除偏倚评估，不替原文批准这些排除本身。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在使用全分析集(full analysis set)进行分析时，若因方案违背而排除了某些已随机受试者，是否可以不评估这些排除对结果可能造成的偏倚？

原英文：When performing an analysis based on the full analysis set, if certain randomised subjects are excluded due to protocol violations, is it acceptable to omit assessment of the potential bias arising fr…

建议英文：When using the full analysis set, if some randomised participants have been excluded because of protocol violations, is it acceptable not to assess the potential bias caused by those exclusions?

引用：`/sources_staging/0c0ddc93cb427a70265dbcb0e7c25bfc9a3f7b52e178212b3630ea2408ad9c7e.pdf`，物理第27页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0459 ← ms-0458 — PENDING_PARENT

语言建议：`KEEP_QUERY`。问multicentre centre定义的ICH参考，未混同研究中心实地检查要求。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：根据ICH E9，若对多中心临床试验中'中心'(centre)一词的定义存有疑问，可参考哪份ICH指南以获得相关指导？

保留英文：According to ICH E9, if there is doubt about the definition of 'centre' in a multicentre clinical trial, which ICH guideline can be consulted for relevant guidance?

引用：`/sources_staging/0c0ddc93cb427a70265dbcb0e7c25bfc9a3f7b52e178212b3630ea2408ad9c7e.pdf`，物理第17页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

### ms-0461 ← ms-0460 — PENDING_PARENT

语言建议：`KEEP_QUERY`。open-label治疗分配身份对谁已知的提问准确，没有误作参与者个人身份公开。

父版本状态：CO修订附件未重新取得；已完成语言建议及原PDF来源定位，但不能核实与上轮最终父query/gold/slices完全一致。

比较基准中文：在开放标签(open-label)试验中，治疗分配的身份对哪些人是已知的？

保留英文：In an open-label trial, who knows the identity of the treatment assignment?

引用：`/sources_staging/0c0ddc93cb427a70265dbcb0e7c25bfc9a3f7b52e178212b3630ea2408ad9c7e.pdf`，物理第12页。

来源检查范围：`draft_preview_prefix_not_gold`；本地锚点次数=1。仅预览前缀；完整最新父gold未验证。

正式norm-v1偏移、数据库状态及人工签署：未执行／未确认。

## 9. 尚待输入及执行

解除76条父版本阻断需要CO的实际修订表或审校JSON，而不是再提供原PDF。取得后应先核对父中文、删除/迁移状态，再同步完整gold、切片、部门和EN问句，并重算规范偏移。

整体冻结还需正式SPEC、完整候选JSON及规范页文本/应用结果；所有修改须经过用户确认，第二人工复核仍未完成。不能据本EN子表宣布main-v1配额或规范机械检查通过。

## 10. 完整限制清单

1. CO的上轮修订表/审校JSON未能在运行环境或Files检索中重新取得；不能凭上轮摘要重建出被称为原始修订快照的文件。80个CO来源孪生均未验证最新完整父gold/slices，其中4条延续可复核的排除建议，其余76条暂缓（含1条部门迁移）。

2. 93个OK仅指AI审校后英文与实际PV修订快照一致；并非annotator-01人工签名、独立复核或主数据集冻结。

3. PENDING_PARENT是本审校包新增的阻断状态，不是项目既有apply_sheet_edits.py已确认支持的语法；不得将它当OK、DROP或no_answer。

4. 仅有Markdown展示表，没有完整EN candidate JSON。26个截断英文以完整建议问句替换，不能声称恢复了未提供的原始尾部或认定原JSON错误。

5. 未取得正式SPEC.md、norm-v1页文本、完整候选JSON和apply_sheet_edits.py；未运行规范偏移重算、版本状态过滤、数据库写回、孪生正式联动或全体配额检查。

6. 本轮不独立修改孪生gold或slices。PV展示字段来自父修订快照；CO仍展示原始继承字段并明确待确认。新拟的30个中文父问题是配对建议，不声称是上轮CO修订原文。

7. 本地定位归一化使用NFKC、删除软连字符U+00AD及U+FFFE、折叠空白；本地唯一性不等于项目norm-v1逐字唯一性或语料级唯一可回答性。

8. 81条只验证可见预览前缀，不验证完整gold，其中80条来自CO，1条来自已DROP的PV。没有把短锚点命中当作完整条款通过。

9. version_conflict沿用用户声明的同PDF合成fixture。没有验证数据库document_key、归档状态、effective_date/as_of或真实内容版本差异。

10. 只审校用户已提供快照，未用网站其他版本替换PDF；FDA地方实施版与ICH原版、原指南与附录保持区分。结论不是现行法律或临床建议。

11. 源目录是用户声明路径，不代表访问用户电脑。原PDF、PV/CO原文件均保持不变。自审是同一AI第二次检查，不是第二位人工或独立模型复核。

