# Build context: thư mục server/ (xem docker-compose.yml ở gốc repo)
# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH \
    PYTHONPATH=/app/src

# Security: run as non-root user
RUN useradd -m appuser

COPY src/ ./src/
COPY prompts/ ./prompts/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Cùng image cho api / worker / agent-worker, khác lệnh khởi động (ADR-0004)
CMD ["uvicorn", "app.main_api:app", "--host", "0.0.0.0", "--port", "8000"]
