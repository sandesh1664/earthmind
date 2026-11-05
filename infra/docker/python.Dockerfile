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
COPY packages/simulation-worker/pyproject.toml packages/simulation-worker/pyproject.toml
RUN uv sync --locked --no-dev --no-editable --package earthmind-api

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH=/app/.venv/bin:$PATH
RUN groupadd --gid 10001 earthmind && useradd --uid 10001 --gid 10001 --create-home earthmind
WORKDIR /app
COPY --from=build --chown=10001:10001 /app /app
RUN install -d -o 10001 -g 10001 -m 0750 /simulation-artifacts
USER 10001:10001
CMD ["uvicorn", "earthmind_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
