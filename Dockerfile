# MedOps Copilot runtime image (M3-12): multi-stage, hash-pinned dependencies, non-root, no secrets.
# Base image digest resolved 2026-09-24 for python:3.11-slim (multi-arch index); bump tag and digest together.
ARG PYTHON_IMAGE=python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9

# ---- builder: the same order as `make install` / `make install-embed`, every wheel hash-checked -------------
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /build
ARG TARGETARCH
# The embed stack (PyTorch CPU wheels from download.pytorch.org/whl/cpu + sentence-transformers) is locked per
# Linux architecture (`make lock`), because the macOS lock omits Linux-only dependencies such as cuda-toolkit.
COPY requirements-build.lock requirements.lock requirements-embed-linux-aarch64.lock requirements-embed-linux-x86_64.lock pyproject.toml ./
RUN case "${TARGETARCH}" in arm64) ARCH=aarch64 ;; amd64) ARCH=x86_64 ;; *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; esac \
 && pip install --require-hashes -r requirements-build.lock \
 && pip install --no-build-isolation --require-hashes -r requirements.lock \
 && pip install --no-build-isolation --require-hashes --extra-index-url https://download.pytorch.org/whl/cpu -r "requirements-embed-linux-${ARCH}.lock"
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN pip install --no-build-isolation --no-deps . && pip check

# ---- runtime: virtualenv + migrations only; runs as an unprivileged user ------------------------------------
FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:${PATH}" \
    MODEL_CACHE_DIR=/models HF_HOME=/models/hf
RUN groupadd --gid 10001 medops && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin medops \
 && mkdir -p /models /app && chown -R medops:medops /models /app
COPY --from=builder --chown=medops:medops /opt/venv /opt/venv
COPY --from=builder --chown=medops:medops /build/migrations /app/migrations
COPY --from=builder --chown=medops:medops /build/alembic.ini /app/alembic.ini
WORKDIR /app
USER medops
VOLUME ["/models"]
EXPOSE 8000 8001
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=6 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"
CMD ["python", "-m", "medops.api.serve", "--host", "0.0.0.0", "--port", "8000", "--device", "cpu"]
