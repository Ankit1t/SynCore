# syntax=docker/dockerfile:1
# Syncore API image. Multi-stage keeps the runtime lean.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build deps first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install ".[postgres]"

# Non-root runtime user.
RUN useradd --create-home --uid 10001 syncore
USER syncore

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live').status==200 else 1)"

CMD ["uvicorn", "syncore.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
