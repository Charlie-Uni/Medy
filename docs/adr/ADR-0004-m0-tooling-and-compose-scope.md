# ADR-0004：M0 锁编译工具与 Compose 范围

- 日期：2026-09-10
- 状态：已批准（仅下述两项）
- 决策来源：记录 08 第三版通过 Codex 复核后，项目负责人在当前对话回复“批准”。

## 决策

1. 使用 uv 编译 pip 兼容、带 SHA-256 的锁文件，使用 pip 安装；uv 不作为运行时依赖。`requirements-build.lock` 负责构建工具引导，`requirements.lock` 负责主依赖，两者的共同依赖保持一致。安装顺序和验证证据见[实现记录 08 第三版](../reviews/2026-09-10-implementation-08-m0-environment.md)。
2. 当前 M0 切片的 Compose 只包含 PostgreSQL/pgvector 与 Redis 基础设施。API、worker 随实际代码加入；对象存储等待 DEC-007，不提前创建服务空壳。

## 批准边界

- 本次批准不包含 Redis 具体版本、镜像 digest 或许可证适用性；这些仍须项目负责人明确确认，现有镜像标签不因本次批准而改变。
- PostgreSQL 16 仍是当前开发候选，不据此冻结后续 DEC-001/002 的扩展或模型选型。
- Compose 的阶段范围不替代工程基线 M0-11 的完整验收要求；远端 CI、容器启动与运行验证仍待完成，不勾选基线 checklist。
- 不包含 Git 提交、推送或部署授权，也不代表后续实现轮次已审核。

## 后续决定（2026-09-17）

- Redis：项目负责人确认改用 7.2 系列（BSD-3-Clause），Compose 镜像固定为 `redis:7.2-alpine@sha256:ccd6aa8d45ff3f033d6fa15b8cc1a50579f65c89f38cf9bb607a954c4f2128ed`（当日对应 7.2.16-alpine）；标签与 digest 必须一起升级。7.4 及以后（RSALv2/SSPLv1）不采用。见[实现记录 15](../reviews/2026-09-17-implementation-15-approved-follow-ups.md) 轮 D。
- 本机容器运行时：确认采用 Docker Desktop，沿用本 ADR 的 Compose 范围；安装为负责人本机操作，启动验证归 M0-11。
