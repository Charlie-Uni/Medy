# DEC-001 candidate C: isolated build, never use the production Compose volume.
# Build context must contain the publisher-verified asset as pg_search.deb.
FROM pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b

LABEL org.opencontainers.image.source="https://github.com/paradedb/paradedb" \
      org.opencontainers.image.revision="c727757be0aab7fbb17c6cc5f0360f22efdd3776" \
      org.opencontainers.image.version="0.25.9" \
      medy.dec001.candidate="C" \
      medy.release_status="release_blocked"

COPY pg_search.deb /tmp/pg_search.deb
RUN test "$(dpkg --print-architecture)" = arm64 \
    && echo '69ac9f7ade7ec66b3e062d823e023f28440b5c87be30d6ee85b16f51eab549a9  /tmp/pg_search.deb' | sha256sum -c - \
    && test "$(dpkg-deb -f /tmp/pg_search.deb Version)" = 0.25.9 \
    && apt-get update \
    && apt-get install -y --no-install-recommends --no-upgrade \
       libopenblas0=0.3.21+ds-4 libopenblas0-pthread=0.3.21+ds-4 \
    && dpkg -i /tmp/pg_search.deb \
    && test "$(dpkg-query -W -f='${Version}' postgresql-16)" = 16.15-1.pgdg12+2 \
    && test "$(dpkg-query -W -f='${Version}' postgresql-16-pg-search)" = 0.25.9 \
    && rm /tmp/pg_search.deb \
    && rm -rf /var/lib/apt/lists/*

# The smoke runner sets shared_preload_libraries on its ephemeral server.
