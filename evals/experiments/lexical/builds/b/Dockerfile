FROM pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b AS builder

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential autoconf automake libtool pkg-config \
       postgresql-server-dev-16="${PG_VERSION}" postgresql-16="${PG_VERSION}" postgresql-client-16="${PG_VERSION}" \
    && mkdir -p /opt/dec001-b

COPY zhparser.tar.gz scws.tar.gz /tmp/source/
RUN printf '%s\n' \
      'ae670786b1372337d0527917692e7b40910fff0e3e9a727b3cccc09b73bd5584  /tmp/source/zhparser.tar.gz' \
      'c4f83883bf453aa9829a36abea76a11d546016fe639838b72b66bfca9f7f4d0d  /tmp/source/scws.tar.gz' \
      | sha256sum --check \
    && tar -xzf /tmp/source/scws.tar.gz -C /tmp/source \
    && tar -xzf /tmp/source/zhparser.tar.gz -C /tmp/source

WORKDIR /tmp/source/scws-a04ef5e655213eb6b07fb57761d0eac72c281ad4
# Upstream's generated configure is absent from the commit archive. Run the
# documented autotools steps directly so failures are not hidden by acprep pipes.
RUN touch README \
    && aclocal && autoconf && autoheader && libtoolize && automake --add-missing \
    && ./configure --prefix=/usr/local --with-pic \
    && make -j1 && make install \
    && cp config.log /opt/dec001-b/scws-config.log \
    && cp COPYING /opt/dec001-b/SCWS-COPYING

WORKDIR /tmp/source/zhparser-dd292fd591edbcb7ebee79d3c3cdc969e9cddced
RUN make -j1 PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config SCWS_HOME=/usr/local \
    && make install PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config SCWS_HOME=/usr/local \
    && cp COPYRIGHT /opt/dec001-b/zhparser-COPYRIGHT \
    && dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > /opt/dec001-b/build-packages.tsv \
    && pg_config > /opt/dec001-b/pg-config.txt \
    && gcc --version > /opt/dec001-b/gcc-version.txt

FROM pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b
LABEL org.opencontainers.image.title="Medy DEC-001 candidate B isolated experiment" \
      medy.zhparser.commit="dd292fd591edbcb7ebee79d3c3cdc969e9cddced" \
      medy.scws.commit="a04ef5e655213eb6b07fb57761d0eac72c281ad4"
COPY --from=builder /usr/local/lib/libscws.so* /usr/local/lib/
COPY --from=builder /usr/local/bin/scws /usr/local/bin/scws
COPY --from=builder /usr/local/etc/rules* /usr/local/etc/
COPY --from=builder /usr/lib/postgresql/16/lib/zhparser.so /usr/lib/postgresql/16/lib/
COPY --from=builder /usr/share/postgresql/16/extension/zhparser* /usr/share/postgresql/16/extension/
COPY --from=builder /usr/share/postgresql/16/tsearch_data/dict.utf8.xdb /usr/share/postgresql/16/tsearch_data/
COPY --from=builder /usr/share/postgresql/16/tsearch_data/rules.utf8.ini /usr/share/postgresql/16/tsearch_data/
COPY --from=builder /opt/dec001-b /opt/dec001-b/
RUN ldconfig

