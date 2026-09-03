# ADR-0001：身份边界采用 OIDC 兼容 token，具体 IdP 延后选择

| 项 | 内容 |
| --- | --- |
| 状态 | 部分已决：OIDC 边界已接受；IdP 厂商选择延后至 M3 上线前 |
| 日期 | 2026-09-03 |
| 关联 | 基线 DEC-010、`INV-AUTH-01`、`INV-AUTH-04`、5.7 |
| 决策人 | Qihan Zhu |

## 背景

基线多处依赖“可信 token”，但 v0.1 没有身份提供方、token 签发和用户到部门映射的决策项。部门 ACL 在数据库层执行，因此身份解析的边界必须先固定，否则 RLS、Skill scope 校验和 MCP 鉴权都没有稳定输入。

## 决策

1. 所有业务、管理和 MCP 请求使用 OIDC 兼容的 bearer token；服务端校验 issuer、audience、expiry 和 signature。
2. token 的 `sub` 只用于识别用户；部门与 scope 由服务端目录/数据库映射得到，不从 token 直接读取。
3. 若使用 IdP group claim，必须经过服务端 allowlist 映射；任意 claim 不能直接变成数据库 scope。
4. 开发与测试环境使用独立的测试签发密钥和合成身份，不连接生产 IdP。
5. MCP 生产传输为 Streamable HTTP + bearer token；stdio 仅限本地开发和自动化测试。
6. 具体 IdP 厂商不在本 ADR 锁定；选择时点为 M3 上线前，判据见基线 DEC-010。

## 后果

- M0 的契约和鉴权依赖可以按 OIDC 标准 claim 设计，不受后续厂商选择影响。
- 需要维护服务端的用户到部门/scope 映射表及其审计。
- IdP 选定后需补充本 ADR 的后续记录，不修改本文件已决部分。
