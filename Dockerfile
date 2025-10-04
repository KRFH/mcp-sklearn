FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app
COPY server/pyproject.toml /app/
RUN uv pip compile -q pyproject.toml > requirements.txt && \
    uv pip install --system -r requirements.txt

COPY server/server.py /app/server.py

EXPOSE 8080
CMD ["python", "-m", "mcp.server.fastmcp.run", "server", "streamable-http", "--host", "0.0.0.0", "--port", "8080", "--module", "server"]
