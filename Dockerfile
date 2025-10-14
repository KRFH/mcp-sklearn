# ./Dockerfile
FROM python:3.12-slim

# ベースツール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

# Poetry
ENV POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

# 依存定義をルートで扱う（Poetryが相対パスを見失わないように）
COPY server/pyproject.toml ./pyproject.toml
COPY server/poetry.lock* ./poetry.lock
RUN poetry install --only main --no-root

# アプリ本体
COPY server ./server
RUN mkdir -p /app/data

ENV TRANSPORT=stdio
CMD ["/bin/bash", "-lc", "cd /app && poetry run python server/server.py --transport stdio"]
