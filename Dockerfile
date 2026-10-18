# syntax=docker/dockerfile:1
# Production image for the FastAPI service (Render, or `docker run`).
#   docker build -t fraud-api .
#   docker run -p 8000:8000 --env-file .env fraud-api

# --- build: install dependencies into a virtualenv -----------------------------
FROM python:3.13-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

# --- runtime: venv + code + model only, run as a non-root user -----------------
FROM python:3.13-slim
# libgomp: OpenMP runtime for xgboost / scikit-learn
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba \
    PORT=8000
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY api/ api/
COPY ml/*.py ml/
COPY ml/artifacts/model.joblib ml/artifacts/metadata.json ml/artifacts/score_distribution.json ml/artifacts/
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"
# Render sets PORT. One worker on purpose: /metrics and the demo-stream lock live in memory.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port \"$PORT\" --no-access-log --proxy-headers --forwarded-allow-ips '*'"]
