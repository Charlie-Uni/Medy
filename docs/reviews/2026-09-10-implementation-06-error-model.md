# 实现记录 06：统一错误模型、trace_id 传播与结构化脱敏日志（M0-05）（2026-09-10）

按基线第 9 节交付格式。本轮只做 M0-05，不接 FastAPI，不接观测后端，不改领域契约。**状态：待 Codex 审核。**

## 完成

| 文件 | 内容 | 对应条款 |
| --- | --- | --- |
| `src/medops/core/errors.py` | `ErrorCode` 13 个稳定错误码，分 client / identity / domain / infrastructure 四类；`HTTP_STATUS` 映射表（供 API 层使用，现在不接路由）；`MedOpsError` 基类不可直接抛出；`BusinessError` 对外原样返回 message、不可重试；`InfrastructureError` 对外只给通用文案，`detail` 只进日志，除 internal_error 外默认可重试；`public()` 生成 `ErrorResponse`，结构上不含 detail | M0-05；基线 5.10“审计失败不得无审计作答”对应 `audit_unavailable`；拒答/升级不是错误，仍用 `domain.ReasonCode` |
| `src/medops/core/tracing.py` | `new_trace_id()` 32 位小写十六进制；`bind_trace_id()` 用 contextvars 作用域绑定并在退出时恢复；`require_trace_id()` 未绑定时抛 `InfrastructureError(internal_error)`；asyncio 子任务继承 | INV-OBS-01 |
| `src/medops/core/logging.py` | 每行一个 JSON：ts（UTC）、level、logger、event、trace_id、可选 fields 与 exception；`redact()` 递归屏蔽敏感键（authorization、token、password、api_key 等）并替换 bearer、sk- 密钥、JWT、邮箱等子串；`configure_logging()` 幂等、压低 uvicorn/httpx 噪音 | INV-OBS-02/03；4.3 密钥不进日志 |
| `tests/unit/core/test_errors.py`、`test_tracing.py`、`test_logging.py` | 18 个测试：码表完整与唯一；基类不可实例化；业务与基础设施错误分类互斥；detail 不出现在 `str()` 与公开响应；trace_id 绑定/恢复/嵌套/任务继承/格式；JSON 行字段、脱敏、异常序列化、幂等配置、级别 | |

## 约束

- `detail` 是内部字段，`ErrorResponse` 用 `extra="forbid"` 且没有该字段，处理器无法误传。
- 错误码与 `ReasonCode` 是两套枚举：错误码表示请求失败，reason code 表示拒答或升级的业务结果；唯一桥接是基础设施故障导致运行升级时使用 `ReasonCode.system_failure`（尚未实现调用点）。
- 日志脱敏是兜底，不是替代：身份字段必须在调用点就是 surrogate id。

## 验证

```text
env -u PYTHONPATH make check
  install-check           -> medops importable outside the repo
  ruff check src tests    -> All checks passed!
  mypy                    -> Success: no issues found in 28 source files
  pytest -q               -> 105 passed in 2.89s
```

## 未完成

- 未接入 FastAPI 异常处理器与 OpenAPI 错误响应（M0-08、M3-01）。
- 未接入 OTel/Langfuse，trace_id 只在进程内传播（M3-09）。
- 不勾选 M0-05：还缺与 API、worker 的接线证据。

## 待 Codex 审核的重点

1. 错误码集合是否够用且不过度：是否有应当合并或缺失的码；`evidence_integrity_failed` 映射 500 是否合理，或应作为升级结果而非错误。
2. `InfrastructureError` 默认可重试（除 internal_error）是否会让调用方对 `audit_unavailable` 盲目重试；是否需要按码单独定义重试策略。
3. 脱敏正则的误杀与漏杀：邮箱模式会误伤形如 `a@b.cd` 的正常文本；JWT 与 bearer 模式是否足够；是否应把 `medops.evals.probe.pii` 的模式复用到日志。
4. contextvars 在线程池（`run_in_executor`）中的传播需要显式 `contextvars.copy_context()`，当前未提供辅助函数，是否应现在补。
5. `configure_logging()` 直接替换 root handlers，是否会与 pytest 的 caplog 或 uvicorn 的日志配置冲突。
6. 反向测试是否遗漏：例如 `redact()` 对非常深或循环引用的结构、超长字符串的性能。

## 第二版：按 Codex 审核修订（2026-09-10）

Codex 结论为“需修改，暂不通过”。三项必修全部修复，六个审核点按建议处理。**状态：待 Codex 复核。**

| Codex 发现 | 修复 | 回归测试 |
| --- | --- | --- |
| 脱敏旁路：bytes/未知对象绕过 `redact()` 后被 `default=str` 输出 | `redact()` 只接受 JSON 原生类型；bytes/bytearray/memoryview 变为 `<bytes len=N>`，未知对象变为 `<类型名>`；`json.dumps` 的 `default` 改为占位函数，不再字符串化 | `test_bytes_and_unknown_objects_never_reach_str_serialization` |
| 循环结构触发 `RecursionError`，无深度/长度/大小边界 | 深度上限 8、容器上限 200 项、字符串上限 2000 字符并标注截断；循环以 `<cycle>` 切断；格式化失败时输出不含原始内容的最小安全记录 | `test_cycles_depth_size_and_length_are_bounded`、`test_format_failure_emits_safe_record_without_raw_content` |
| trace_id 校验不严格：末尾换行的 33 字符通过、空串被静默替换 | `re.fullmatch`；只有 `None` 自动生成，其余非法值抛 `ValueError` | 参数化 6 个非法值 + `test_only_none_generates_a_fresh_id` |

审核点处理：

1. 错误码保持 13 个不扩充；`evidence_integrity_failed` 维持 500，公开文案固定为安全文本。
2. 新增显式 `RETRYABLE_CODES`（dependency_timeout、dependency_unavailable、audit_unavailable），`retryable` 明确为提示，执行仍受次数、预算与幂等约束；审计不可用期间不得作答已写入注释。不新增重试框架。
3. 不让 `core` 反向依赖 `evals`；日志默认不接收完整 query 与证据正文，已写入模块文档。
4. 线程池传播暂不补辅助函数，引入 `run_in_executor` 时再显式复制上下文并测试。
5. `configure_logging()` 文档明确只供应用入口调用；`tests/unit/core/conftest.py` 自动保存并恢复 root handlers 与级别。
6. 深度、循环、长度已随第 2 项一并处理。

记录更正：三个新增 core 测试文件为 17 项，总增量 18 项含 1 项文档一致性测试。

同轮关闭的既有问题：`UserContext.acl_scopes` 集合序列化顺序随进程哈希种子变化，导致 dump 与哈希跨进程不一致。修复为 `field_serializer` 按字典序输出该字段，不换算法、不全局重排数组；`VersionSet.skill_version_set` 按契约是集合，改为校验时排序去重（如 Codex 认为不应改，可回退为原样保留）。回归：`test_scope_set_serializes_in_stable_order_for_hashing`、`test_skill_version_set_is_order_independent`。

仍未关闭：Codex 提到的“上一轮六项领域契约问题”，具体清单尚未转达，待收到后单独一轮处理。

验证：`env -u PYTHONPATH make check` 通过；ruff 通过；mypy 28 个源文件通过；pytest 118 passed（本轮新增 13 项）。

## 第三版：按 Codex 复核关闭 M0-05 剩余三处（2026-09-10）

| Codex 发现 | 修复 | 回归测试 |
| --- | --- | --- |
| `evidence_integrity_failed` 公开文案未固定，传入的内部细节原样返回 | 新增 `FIXED_PUBLIC_MESSAGES`；`BusinessError` 对该码固定安全文案，传入文本转入 `detail` | `test_evidence_integrity_failure_has_fixed_public_text_and_keeps_input_as_detail` |
| 先截断再脱敏会留下密钥片段 | `_redact_str` 改为先脱敏后截断；超过 20,000 字符的字符串不扫描，整段占位；`sk-` 模式去掉词边界，粘连文本也脱敏（过度脱敏是安全方向） | `test_secret_crossing_the_truncation_boundary_leaves_no_fragment` |
| 容器上限只限输出不限处理：未知键 `str()`、集合成员 `repr()`、`list(value)` 全量复制 | Mapping 与序列都用 `islice(MAX_ITEMS + 1)` 按上限读取；键只接受 str/int/float/bool，其余为 `<key:类型>` 占位；集合不再按 repr 排序，成员作为值处理；不支持任意对象 | `test_container_processing_is_bounded_and_keys_are_never_stringified_beyond_limit`（懒 Mapping 计数读取次数 ≤ 201，越界键与集合成员的 `__str__/__repr__` 被调用即失败） |

`skill_version_set` 排序去重按 Codex 意见保留：它是版本集合而非执行顺序，`a@1` 与 `a@2` 仍为不同条目。

验证：`env -u PYTHONPATH make check` 通过；pytest 121 passed（本批新增 3 项）。**状态：待 Codex 复核。**

补充（2026-09-10）：按复核意见，`evidence_integrity_failed` 的固定公开文案改为“证据完整性校验未通过，无法提供回答，需要人工核验”，不再宣称已转人工处理，因为构造异常本身不创建升级记录。
