# Build context: thư mục server/ (xem docker-compose.yml ở gốc repo)
# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

# Install deps into a venv: /root/.local (pip --user) is unreadable by the non-root runtime user.
ENV VIRTUAL_ENV=/opt/venv \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:$PATH

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Security: run as non-root user
RUN useradd --create-home appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# app.platform.prompts.loader resolves prompts at /app/prompts
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser prompts/ ./prompts/
# Alembic config + revisions: the `migrate` compose service runs `alembic upgrade head` from this image
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser migrations/ ./migrations/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Cùng image cho api / worker / agent-worker, khác lệnh khởi động (ADR-0004)
CMD ["uvicorn", "app.main_api:app", "--host", "0.0.0.0", "--port", "8000"]
