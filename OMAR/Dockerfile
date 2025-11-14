# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY gunicorn.conf.py wsgi.py ./

RUN mkdir -p runtime/archives runtime/config

RUN useradd --create-home --shell /bin/bash omar \
    && chown -R omar:omar /app
USER omar

ENV PYTHONPATH=/app/src \
    OMAR_RUNTIME_ROOT=/app/runtime \
    OMAR_ENV_FILE=/app/runtime/config/.env \
    HOST=0.0.0.0 \
    PORT=5050 \
    USE_FAKEREDIS=0

EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD curl -fsS http://127.0.0.1:5050/healthz || exit 1

CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
