# DEC-001 candidate D (ADR-0002 revision 5): pg_textsearch BM25 on PostgreSQL 17 + pgvector. Isolated experiment
# image; never use the production Compose volume. Build context must contain the publisher asset as pg_textsearch.deb
# (pg-textsearch-v1.5.1-pg17-arm64.zip -> pg-textsearch-postgresql-17_1.5.1-1_arm64.deb).
FROM pgvector/pgvector:pg17

LABEL org.opencontainers.image.source="https://github.com/timescale/pg_textsearch" \
      org.opencontainers.image.version="1.5.1" \
      medy.dec001.candidate="D" \
      medy.licence="PostgreSQL License"

COPY pg_textsearch.deb /tmp/pg_textsearch.deb
RUN test "$(dpkg --print-architecture)" = arm64 \
    && echo '9841e00382c3a094a08ffa3c1f7e6b287838bade1184cef8f656df78ebb143ce  /tmp/pg_textsearch.deb' | sha256sum -c - \
    && test "$(dpkg-deb -f /tmp/pg_textsearch.deb Version)" = 1.5.1-1 \
    && dpkg -i /tmp/pg_textsearch.deb \
    && test -f "$(pg_config --pkglibdir)/pg_textsearch.so" \
    && test -f "$(pg_config --sharedir)/extension/pg_textsearch.control" \
    && rm /tmp/pg_textsearch.deb

# The extension must be preloaded; the experiment runner starts the server with
#   -c shared_preload_libraries=pg_textsearch
