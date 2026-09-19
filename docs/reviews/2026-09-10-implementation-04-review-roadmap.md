# 实现复核 04：校验器加固与全量任务路线

日期：2026-09-10。范围：复核实现记录 03 的六类修复与运行门禁，按用户要求盘点全部任务、已完成工作和学习路线。未实现领域模型、未修改冻结基线、未提交 Git。

## 1. 结论与实测

六类修复均有实现与回归覆盖：文档索引/引用版本、SHA256SUMS 严格解析、映射抽取版本、缺页时仍执行独立检查、全集 query/key 比较、严格输入与 Finding。原先这六类问题可以收敛，不要求继续扩写校验器架构。

| 检查 | 本轮结果 |
| --- | --- |
| `env -u PYTHONPATH make check` | 退出 0；仓库外 import 通过；ruff 通过；mypy 15 源文件通过；pytest 61 passed（1.81s） |
| 四个示例复制为标准文件名，在仓库根目录调用 CLI、不设 PYTHONPATH | PASS (draft)，errors=0、warnings=17 |
| 六个 JSON Schema 的 Draft202012Validator 元校验 | 6/6 通过 |
| DEC-011 候选 JSON 的 Schema 校验 | 无错误，25 条 |
| `docs/source/` 下 `shasum -a 256 -c SHA256SUMS` | PDF 与项目描述两份均 OK |

回归文件有 14 个反向测试函数与 1 个正向控制函数；部分函数同时覆盖同一规则的两个字段或输入变体。因此“每条只隔离一个规则”不能理解为每次变异绝不会触发其他规则；关键是测试显式断言目标规则的 Finding，而不是只断言整体失败。

本轮没有运行远端 GitHub CI、真实冻结语料校验、数据库/模型/服务端到端评测，也没有重新复现 iCloud 标志自动恢复的时序。当前 venv 导入有效已验证，不将本机历史排障结论扩写成通用平台结论。

## 2. 新确认问题：分词器全局词典污染

位置：[tokenizer.py](../../src/medops/retrieval/lexical/tokenizer.py) 中 `JiebaTokenizerV1.__init__` 和 `tokenize`。

实例保存的是同一个 `jieba` 模块，调用模块级 `load_userdict`、`cut`。其他实例加载词典会改变已存在实例的分词结果，而该实例的 `dictionary_version` 不变；违反基线 3.6/3.7 与 ADR-0002 的同版本可复现约定。

独立 Python 进程内复现（仅内存中加载合成词条，没有修改用户词典或项目文件）：

```python
from io import StringIO
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1

first = JiebaTokenizerV1()
phrase = "药物警戒专用合成术语"
before = first.tokenize(phrase)
version = first.dictionary_version
second = JiebaTokenizerV1()
second._jieba.load_userdict(StringIO(phrase + " 100000000 nz\n"))
after = first.tokenize(phrase)
assert before != after
assert version == first.dictionary_version
```

实测：`before=['药物', '警戒', '专用', '合成', '术语']`，`after=['药物警戒专用合成术语']`；版本始终为 `jieba-0.42.1+default`。这里直接调用实例所保存模块的加载方法，用于隔离演示构造器加载词典时的相同全局副作用，不是新增生产入口。

处置：在正式词法实验前改用每实例独立 `jieba.Tokenizer`，增加两个不同词典及默认实例互不污染的回归；不改 norm-v1、不引入额外服务。本轮仅审核与列任务，未实施修复。问题不阻塞先做纯领域契约与 AgentState。

## 3. 进度盘点边界

- 当前 HEAD `aa5e503` 是基线 v0.5；工作区有未提交的 v0.6 和代码。没有提交或暂存任何用户已有改动。
- 99 个基线复选项 = M0–M5 的 79 项 + 11 项选做 + 9 项汇总验收，全部未勾选。已写代码不自动等于整项验收完成。
- 候选预判：eligible 8（PV 6、CO 2、MA 0）、needs_review 13、research_only 1、rejected 3。`reviewer_decision=eligible` 为 0；不能说已有 8 份最终批准语料。
- 合成 fixture、示意 draft 与离线 BM25 不作为真实语料、冻结集和生产检索的完成证据。
- 基线 §1.3 多模态 P1 与 §7.2/checklist P2 有文字不一致；路线采用详细条款的 P2，并记录待同步，没有直接修改冻结契约。

## 4. 本轮交付

- 新增[开发任务、当前进度与学习路线](../DEVELOPMENT_ROADMAP.md)：逐项映射 99 个基线复选项；补列正文的横向实现要求及两组未单独成 checklist 行的选做方向；列出 11 项 DEC；给出代码入口、知识点和按轮自检方法。
- README 增加路线入口。
- 不新增 P0 需求，不改原有源码、测试、Schema 或验收数值；下一轮建议领域契约与 AgentState，小步实施。

交付前复检实测：路线逐项编号唯一且顺序/数量与基线一致（79 + 11 + 9）；30 个不变量、99 个未勾选项、11 个 DEC；检查 21 份 Markdown，本地文件链接缺失 0、代码围栏配对；新增文档 UTF-8/LF 与空白检查、`git diff --check` 均通过。再次运行 `make check` 全部通过，pytest 61 passed（1.72s）。这些是本地交付检查，不替代尚未运行的正式服务验收。
