# syntax=docker/dockerfile:1

# --- Builder -----------------------------------------------------------------
# Dependencies are installed into a virtualenv here and copied into a clean
# runtime stage, so build tooling never reaches the final image.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copied before the source so a code change does not invalidate the dependency
# layer on every rebuild.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install .

COPY app ./app
RUN pip install --no-deps .

# --- Runtime -----------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Runs unprivileged: a container compromise should not imply root.
RUN groupadd --system victorious \
    && useradd --system --gid victorious --create-home victorious

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=victorious:victorious app ./app

USER victorious

EXPOSE 8000

# Uses the liveness probe deliberately — readiness depends on the database, and a
# database outage should drain traffic, not trigger a container restart loop.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
