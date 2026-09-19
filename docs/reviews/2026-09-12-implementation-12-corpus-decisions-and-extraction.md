# 实现记录 12：候选清单 v0.3、现行性核对与页文本抽取

日期：2026-09-12。范围：落实决策人对[实现记录 11](2026-09-11-implementation-11-corpus-candidates-v0.2.md) 第 4 节五项的“全部批准”，做图像层与现行性核查，登记候选清单 v0.3，把 pypdf 纳入锁文件并交付页文本抽取工具。未修改冻结基线、Schema、校验器规则；未提交 Git；第三方 PDF 未入仓库。

## 1. 决策落地

| 批复项 | 落地 |
| --- | --- |
| 1. ICH 公共许可三份 | cand-0026～0028 `reviewer_decision=eligible`，`reviewer_note` 写明使用条件；MedDRA 两份注明不覆盖术语库/SMQ 数据 |
| 2. TFDA 三份 | cand-0029～0031 `reviewer_decision=eligible`；口径记入 [ADR-0003 决策记录（2026-09-12）](../adr/ADR-0003-corpus-source-license-policy.md) |
| 3. 现行性与图像层 | 现行性以 TFDA 開放資料 export/36（全部藥品許可證資料集）同日快照为准；图像层用 macOS Quartz 渲染逐页目视，结果写入 `reviewer_note` 与 `license_evidence` |
| 4. cand-0032 / 0033 | 继续核查后保持 `needs_review`（© 标记确认；扫描件无文本层） |
| 5. 抽取库 | pypdf 6.18.1 进入 `requirements.lock`，[ADR-0005](../adr/ADR-0005-pdf-extraction-library.md) |

## 2. 重要发现：v0.2 的 TFDA 五份中四份许可证已失效

export/36 快照（2026-09-12 下载，zip sha256 `0b31742f…f100`，内层 `36_5.json` sha256 `2e00df0b…e9f8`，72,043 条）：

| 候选 | 許可證字號 | 註銷狀態 | 註銷日期 / 理由 | 有效日期 |
| --- | --- | --- | --- | --- |
| cand-0029 美洛醣 850mg | 衛部藥製字第058257號 | 现行 | — | 2029/04/21 |
| cand-0030 安通脈 | 衛部藥輸字第026582號 | 已廢止 | 2024/05/15 未依公告辦理變更 | 2025/08/05 |
| cand-0031 吉福坦 100mg | 衛部藥輸字第026322號 | 已註銷 | 2025/04/24 許可證已逾有效期 | 2024/06/09 |
| cand-0032 艾摩喜林 | 衛署藥製字第021441號 | 已註銷 | 2025/07/04 許可證已逾有效期 | 2023/05/12 |
| cand-0033 血脂安 | 衛部藥輸字第026332號 | 已註銷 | 2020/08/27 屆期未申請展延 | 2019/06/26 |

许可批准（OGDL）不因註銷失效，但 cand-0030/0031 不是现行仿單。是否允许非现行仿單进入探针集 v1（例如作为历史版本样本）是决策人在批复时不知道的新事实，本轮不替决策；作为替代，按已批准的 TFDA 路径从现行许可证中重选。

## 3. 重选：cand-0034～0038（现行许可证，全部条件通过）

筛选：export/36 `註銷狀態` 为空且 `有效日期` 晚于今日 ∧ export/39 `仿單圖檔連結` 为单一 `/insert/pdfcasefile/` 链接（6,463 条），按常见通用名挑 14 份下载。淘汰 9 份：扫描件无文本（壓可平、壓降好、施黴素、汎生安美西林、舒抑痛、樂栓通）、字体编码乱码（道樂 valsartan）、抽取重复（欣律 allopurinol）、同药同厂重复。登记 5 份：

| 候选 | 文档 | 页 / 字符 | 有效日期 | 目视 |
| --- | --- | --- | --- | --- |
| cand-0034 | 痛風停錠300毫克（allopurinol，寶齡富錦） | 10 / 12,909 | 2027/01/30 | 无版权标记 |
| cand-0035 | 穩壓膜衣錠50毫克（losartan，中國化學製藥） | 1 / 4,809 | 2031/03/30 | 无版权标记，公司標誌带 ® |
| cand-0036 | 欣服寧錠3毫克（warfarin，健喬信元） | 4 / 18,983 | 2029/07/14 | 无版权标记；字形映射缺陷（寧→⮏、字→⫿）已标注 |
| cand-0037 | 心壓暢錠100毫克（metoprolol，明德） | 2 / 2,595 | 2029/11/28 | 无版权标记 |
| cand-0038 | 胃所樂腸溶膜衣錠40毫克（esomeprazole，健喬信元） | 4 / 14,636 | 2028/10/18 | 无版权标记；粗体标题重复抽取已标注 |

五份的 pdf_url 均在 2026-09-12 下载的 export/39 快照中逐字出现（该快照与 2026-09-11 下载逐字节相同，zip sha256 `2b6ae0be…ee36`）；文本层标记词扫描命中均为临床文本；预判 `eligible`，`reviewer_decision` 为空待签字。

## 4. 交付与实测

| 项 | 内容 |
| --- | --- |
| [DEC-011-candidates-v0.3.json](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.3.json) / [.md](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.3.md) | 38 条：前 25 条与 v0.2 逐字相同（程序比对）；cand-0026～0033 只改 `reviewer_decision`/`reviewer_note`，TFDA 五条追加现行性证据；新增 5 条 |
| [extract.py](../../src/medops/evals/probe/extract.py) + [test_extract.py](../../tests/unit/evals/test_extract.py) | `python -m medops.evals.probe.extract <pdf>... --pages DIR`：输出 `<pages>/<source_hash>/<page>.txt` 与 `extraction.json`（extractor/version/params/params_hash），目录按 source_hash 不可变；4 个测试（页序与 PageTextProvider 对接、幂等与冲突拒绝、空页上报、CLI 失败退出码） |
| pyproject / requirements.lock | 新增 `pypdf>=6.0,<7`，锁定 6.18.1（带哈希）；其余 25 个包版本不变；`make install` 后 `pip check` 无冲突 |
| [ADR-0003](../adr/ADR-0003-corpus-source-license-policy.md) 决策记录 2026-09-12、[ADR-0005](../adr/ADR-0005-pdf-extraction-library.md) | 决策与选型记录 |
| 六份已批准 PDF 的页文本 | 已用新工具从临时目录抽取到会话 scratchpad（6 个 source_hash 目录：61/49/29/2/13/2 页 + extraction.json），用于验证工具；见第 6 节的存储阻塞 |

`make check`：仓库外导入通过，ruff 通过，mypy 36 个源文件通过，pytest **218 passed**（新增 5），Schema 导出无漂移；`git diff --check` 通过。

预判/决策汇总（v0.3）：license_status eligible 19（MA 8、PV 8、CO 3；en 8、zh-Hans 2、zh-Hant 9）、needs_review 15、research_only 1、rejected 3；reviewer_decision eligible 6、needs_review 10、rejected 1、待定 21。

## 5. 需要决策人决定

1. **非现行仿單能否进入探针集 v1**：cand-0030、0031 许可已批准但许可证已廢止/註銷。建议：不进入 v1 主体，MA 以现行的 cand-0029 与新增 cand-0034～0038 为主；若要保留“历史版本”样本，另作决定。
2. **cand-0034～0038 签字**：条件与 cand-0029 相同（OGDL；条件 (1)(2)(3) 通过；许可证现行）。（第二版修正：许可证现行不等于该 PDF 修订版现行；cand-0036 因抽取乱码本轮排除，签字对象为其余四份，签字后 MA 有 5 份许可证现行且抽取合格的文档，见第 9 节。）
3. **`verified_by` surrogate id**：corpus.json 的 `license_or_terms.verified_by` 记录签字者 surrogate id，请指定（例如 `reviewer-01`），我不代填。
4. **cand-0036 字形缺陷**：是否接受该文档（标注时避开缺陷字形）或放弃。

## 6. 阻塞与边界

- **原件本地存储被权限策略拦截**：三次尝试把六份已批准 PDF 复制到仓库内 gitignored 的 `evals/probe/precise_clause/v1/sources/`（SPEC §2 指定的本地原件目录）均被自动权限分类器拒绝，未绕过。原件仍在 `/tmp/medy-corpus-research.ji2oNC/`（三份指南 + 六份 TFDA）与会话 scratchpad `tfda_new/`（新增五份）；请手动复制或放开该目录的写权限后我再执行抽取到仓库内目录。
- 图像层目视只判断版权/保密标记，不替代法律意见；扫描件未 OCR。
- 页文本抽取只验证了工具与产物结构，未做 gold 标注、frozen 校验或检索实验。
- pypdf 在部分 TFDA 仿單上有字形映射缺陷（cand-0036）与粗体重复（cand-0038、cand-0030），按 SPEC §4 由标注阶段逐页判定，不改抽取参数掩盖。

## 7. Codex 审核焦点

- v0.3 对 cand-0001～0025 是否逐字承接；cand-0026～0033 是否只改了决策字段与追加证据；新增 5 条证据是否一一对应。
- 现行性证据（export/36）是否足以支撑 `version_label`/生效时间字段；非现行仿單的处理建议是否合理。
- `extract.py` 的不可变目录语义（内容不同或多余文件即报错）与 `PageTextProvider` 的读取约定是否一致；`params_hash` 是否按基线 3.2 canonical JSON 计算。
- 锁文件只新增 pypdf 一行、构建锁未变。

## 8. 自审（基线 §9）

- 未越权：五份新候选与 `verified_by` 未代签；非现行仿單是否入集未替决策。
- 未改冻结契约：Schema、SPEC、校验器规则不变；候选清单按版本追加。
- 边界如实：目视 ≠ 法律意见；文本可抽取 ≠ 抽取质量合格；许可批准 ≠ 文档现行。
- 最小实现：抽取工具一个模块一个 CLI，不做 OCR、版面分析或缓存层。
- 权限拦截如实记录，未尝试绕过。

## 9. 第二版修正（2026-09-13，按审核意见）

审核结论：本轮暂不能关闭；四项必须修正与两处记录订正如下，全部已落地。

| # | 审核意见 | 修正 | 证据 |
| --- | --- | --- | --- |
| 1 | 欣服寧（cand-0036）不是只有两个字形错误，四页均有乱码 | 以锁定版 pypdf 6.18.1 逐页复测：p1 297、p2 300、p3 254、p4 33 个可疑字符（含「減Ͽ」「個㚰」「72军96」）；按 SPEC §4 本轮排除，不做 OCR、不建替换表；许可预判不变 | [候选 v0.4](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.4.md) cand-0036 |
| 2 | “逐字节不可变”未成立（`read_text` 归一化换行） | 改为 `read_bytes` 逐字节比较、以字节写入；回归：把 extraction.json 的 LF 改为 CRLF 后重跑必须报错 | [extract.py](../../src/medops/evals/probe/extract.py)、`test_immutability_compares_raw_bytes_not_normalized_text` |
| 3 | 写入失败留下无法重试的半成品 | 改为在 `pages_dir` 下的临时目录完整写入后一次 rename 发布，失败即清理；回归：模拟第 2 页写入失败后最终目录与临时目录都不存在，重试成功 | `test_failed_write_leaves_no_partial_directory_and_retry_succeeds` |
| 4 | 不能屏蔽字体解析告警 | 删除日志屏蔽；告警保留在 pypdf logger 上，同时按次计数并在 CLI 每文件输出 `extractor_warnings`，>0 即要求页级质量复核；回归：告警被计数且仍可见，处理器用后移除 | `test_pypdf_warnings_are_counted_and_still_logged` |
| 订正 a | 新增 5 条扫描证据沿用了模板日期与版本 | v0.4 改为实际执行信息：2026-09-12 以 pypdf 6.15.0（会话临时环境）初筛，2026-09-13 以锁定版 6.18.1 复测，记录页数、字符数、告警数 | v0.4 cand-0034～0038 `license_evidence[7]` |
| 订正 b | TFDA 十份合计 48 页，不是 46 页 | v0.2 五份 27 页 + v0.3 五份 21 页 = 48 页 | 本节 |

锁定版复测的告警分布：cand-0038 胃所樂 8 条、cand-0030 安通脈 33 条（均为 fontTools 缺失导致 CFF Type1 字体编码未完整解析），其余（含三份指南、美洛醣、吉福坦、痛風停、穩壓、心壓暢、欣服寧）0 条；欣服寧的乱码没有触发任何告警，说明告警数不能替代逐页质量复核。字符数按 6.18.1 重新记录（与 6.15.0 相差 1～55 字符）。

边界收紧：许可证现行（export/36 的註銷狀態与有效日期）不等于该 PDF 修订版现行；发证日期、到期日、PDF 创建日期都不是说明书生效日期。候选清单 v0.4、路线图已按此措辞。原件复制继续暂停：目标目录 `evals/probe/precise_clause/v1/sources/` 目前不存在，拦截原因未定；待收口后提供源路径、目标路径与预期哈希，由决策人授权或手动复制，不修改仓库权限绕过。

复测后的四项决定仍由决策人作出：(1) cand-0030、0031 不进入 v1 主体，保留许可批准与註銷事实；(2) cand-0034、0035、0037、0038 继续核验版本与页文本后由决策人终审，0036 本轮排除；(3) `verified_by` 建议 `reviewer-01` 对应实际人工决策人，待确认；(4) 欣服寧抽取页不作 gold，不放宽 SPEC。

本版实测：`make check` 全绿，pytest **222 passed**（抽取工具 7 个测试，候选清单校验覆盖 v0.1～v0.4）；v0.4 对 cand-0001～0033 与 v0.3 逐字相同，仅 cand-0034～0038 的 `license_evidence`、`reasoning`、`notes` 变化。
