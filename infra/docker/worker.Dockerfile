FROM ghcr.io/astral-sh/uv:0.11.12@sha256:3a59a3cdd5f7c217faa36e32dbc7fddbb0412889c2a0a5229f6d790e5a019dd7 AS uv

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS build
ARG TARGETARCH
RUN test "$TARGETARCH" = arm64 && test "$(dpkg --print-architecture)" = arm64
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api apps/api
COPY packages/contracts packages/contracts
COPY packages/simulation-worker packages/simulation-worker
RUN uv sync --locked --no-dev --no-editable --package earthmind-worker

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS runtime
ARG TARGETARCH
ARG SUMO_PACKAGE_VERSION=1.15.0+dfsg-1+deb12u1
RUN test "$TARGETARCH" = arm64 \
    && test "$(dpkg --print-architecture)" = arm64 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        "sumo=$SUMO_PACKAGE_VERSION" "sumo-tools=$SUMO_PACKAGE_VERSION" \
    && sumo --version \
    && netconvert --version \
    && test -r /usr/share/sumo/data/typemap/osmNetconvert.typ.xml \
    && test -r /usr/share/sumo/data/xsd/net_file.xsd \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 earthmind \
    && useradd --uid 10001 --gid 10001 --create-home earthmind
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH=/app/.venv/bin:$PATH SUMO_HOME=/usr/share/sumo
WORKDIR /app
COPY --from=build --chown=10001:10001 /app /app
USER 10001:10001
CMD ["python", "-m", "earthmind_worker"]
