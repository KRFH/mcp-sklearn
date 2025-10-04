FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app
COPY server/pyproject.toml /app/
RUN /root/.cargo/bin/uv pip install --system -r <(/root/.cargo/bin/uv pip compile -q pyproject.toml)

COPY server/server.py /app/server.py

EXPOSE 8080
CMD ["python", "-m", "mcp.server.fastmcp.run", "server", "streamable-http", "--host", "0.0.0.0", "--port", "8080", "--module", "server"]
