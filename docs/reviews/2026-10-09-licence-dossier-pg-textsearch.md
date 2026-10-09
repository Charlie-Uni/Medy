# pg_textsearch 生产许可记录

日期：2026-10-09。对应 ADR-0002 revision 6、实现记录 162。用途：把实验阶段的“PostgreSQL License”一句话补成生产镜像的直接组件、运行依赖、来源、固定身份和分发义务记录。本记录不是外部法律意见。

## 1. 生产组件

| 组件 | 固定身份 | 来源 | 许可证 | 本项目用途 |
| --- | --- | --- | --- | --- |
| `pg_textsearch` | 1.5.1，tag `v1.5.1` | [Tiger Data 官方仓库](https://github.com/timescale/pg_textsearch/tree/v1.5.1)及官方 GitHub Release | [PostgreSQL License](https://github.com/timescale/pg_textsearch/blob/v1.5.1/LICENSE) | BM25 index access method、查询与 WAL/后台状态 |
| PostgreSQL | 17.11 | PGDG / `pgvector/pgvector:pg17` 基础镜像 | [PostgreSQL License](https://www.postgresql.org/about/licence/) | 事实平面、RLS、事务、扩展宿主 |
| pgvector | 镜像内 extension 0.8.7 | [pgvector 官方镜像/仓库](https://github.com/pgvector/pgvector) | PostgreSQL License | 既有向量索引；不是 BM25 新依赖，但与生产数据库同镜像分发 |
| Debian | bookworm 运行层 | 上述基础镜像 | 各 Debian 包自身许可证 | libc、shell、证书和 PostgreSQL 运行环境 |

`pg_textsearch` 的 Debian 包声明唯一包依赖为 `timescaledb-2-postgresql-17 | postgresql-17`；本镜像满足后一支，没有安装 TimescaleDB。对 `pg_textsearch.so` 运行 `ldd` 只列出 glibc `libc.so.6` 与动态加载器；没有额外私有共享库。glibc 及基础镜像的系统包继续适用 Debian 镜像内 `/usr/share/doc/<package>/copyright` 的相应条款。

## 2. 发布资产与可复现身份

| 平台 | 官方 zip SHA-256 | 解包 deb SHA-256 |
| --- | --- | --- |
| PostgreSQL 17 / amd64 | `ed4410e8b6879a8971cd87fd03853f182e47b85b199c9bfcd9b34f159caba9fb` | `357d27e5a1a8b6131f89851daf7ec47c2a6419a7f0f5bcfa08860b31334e804d` |
| PostgreSQL 17 / arm64 | `e65f953e99f47c05dde88a031884cf36ea269bcb62377f554b76ddb4d13fdc3e` | `9841e00382c3a094a08ffa3c1f7e6b287838bade1184cef8f656df78ebb143ce` |

基础镜像固定为 `pgvector/pgvector:pg17@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d`。构建脚本先核验 zip，再核验 deb，并核对 Debian package version `1.5.1-1`。本机 arm64 最终镜像 digest 为 `sha256:dc45fe08db3a71f544a20ae8115eb957aa6955a27a05d479beb437e2b9646239`；不同平台的最终 manifest digest可以不同，发布资产和基础 manifest identity 不变。

## 3. 义务与结论

PostgreSQL License 是宽松许可证：允许使用、复制、修改与分发，不要求公开本项目源码，也没有网络服务条款。分发软件或镜像副本时必须保留对应版权声明、许可段落和免责条款。pgvector 与 PostgreSQL 适用同类义务。

Debian 基础镜像包含多种许可证的系统包。当前镜像只在本机和 CI 临时 runner 使用，没有推送到公共或客户 registry。若以后分发镜像，发布流程必须同时输出该镜像的软件物料清单，携带 `/usr/share/doc/*/copyright` 与本记录，并按其中的 LGPL/GPL 等条款提供所需通知或可获得的对应源码；不能只附 `pg_textsearch` 的许可证后宣称整个镜像都是 PostgreSQL License。

结论：`pg_textsearch` 1.5.1、PostgreSQL 17 和 pgvector 本身没有 AGPL 或其他网络 copyleft 阻塞，满足当前项目的生产采用许可门禁。未来变更扩展版本、基础镜像 digest、安装 TimescaleDB 或向外分发镜像时必须重新生成依赖/SBOM并复核，本记录不能自动沿用。
