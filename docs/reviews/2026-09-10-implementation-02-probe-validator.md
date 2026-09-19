# 实现记录 02：探针集校验器与 M0 工程门禁（2026-09-10）

按基线第 9 节交付格式。

## 完成

- `src/medops/evals/probe/validator.py`：实现 SPEC 第 10 节 PR-01 到 PR-14。`draft` 模式把数量不足与页文本缺失记为警告，`frozen` 模式全部为错误并执行 PR-10（SHA256SUMS、manifest.files、dataset_hash、无 example 文件）与 PR-12（映射文件）检查。页文本按 `<pages_dir>/<source_hash>/<page>.txt` 读取并施加 norm-v1（已写入 SPEC 4 节）。
- `src/medops/evals/probe/pii.py`：`pii-rules-v1`（身份证、手机号、邮箱、患者标识字段）；manifest 声明的规则集版本必须与校验器一致。
- `src/medops/evals/probe/__main__.py`：CLI，失败返回非零退出码。
- `tests/unit/evals/fixture_builder.py`：程序化生成 12 份虚构文档、72 条样本、两页合成页文本的完整冻结数据集，页文本故意含抽取伪空白与全角标点以证明校验器先做 norm-v1。
- `tests/unit/evals/test_probe_validator.py`：合成冻结集通过全部规则；示例目录以 draft 通过且只有警告；draft 数据按 frozen 校验失败；页内重复 key_text、篡改 SHA256SUMS、部门不一致、query 等于 key_text、PII、映射缺项、prompt 哈希过期、CLI 退出码各有测试。
- M0 工程门禁：`pyproject.toml` 增加 ruff 与 mypy 配置；`Makefile` 提供 install、lint、format、typecheck、test、check、validate-probe；`.github/workflows/ci.yml` 在 Python 3.11 上跑 ruff、mypy、pytest 与示例 draft 校验。
- 示例 manifest 与 corpus 的 PII 规则集版本升为 `pii-rules-v1`，文件哈希同步。

## 约束

- 校验器不放行任何冻结前置：无页文本时 frozen 模式直接失败；数量门禁含 zh-Hans 不少于 8。
- 校验器只依赖仓库内 Schema 与 norm-v1 实现；jsonschema 由 dev 依赖改为运行时依赖。
- 未触碰生产检索或 Harness；未引入旧项目代码。

## 验证

```text
make check
  ruff check src tests      -> All checks passed!
  mypy                      -> Success: no issues found in 15 source files
  pytest -q                 -> 46 passed in 0.79s
python -m medops.evals.probe /tmp/probe-draft --mode draft
  -> PASS (draft); errors=0 warnings=17（数量不足、缺页文本、PV 文档不足，均为预期警告）
```

## 未完成

- M0“配置 lint、format、type check、unit test 和 migration check”：migration check 无迁移可查，保持 `[ ]`。
- M0“建立 CI”：工作流文件已创建、未提交，尚未在 GitHub 上运行，保持 `[ ]`。
- 校验器尚未对真实数据集运行；探针集 v1 仍受第七轮记录的三项语料门禁阻塞。
- mypy 当前以 `check_untyped_defs` 运行，未开 `disallow_untyped_defs`；随 M0 契约落地再收紧。

## 风险

- `pii-rules-v1` 只覆盖显式模式，不能替代人工 PII 复核；PR-07 的定位是拦截明显泄漏。
- fixture 的页文本是合成的，PR-05 对真实抽取器输出的鲁棒性要在语料到位后验证。
- 无新增已知安全风险。
