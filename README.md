# MCP Proto Server

This repository contains a minimal Model Context Protocol (MCP) server implemented
with the official Python SDK (FastMCP). It exposes a few sample tools that can be
invoked over Streamable HTTP (SSE) or STDIO, making it easy to integrate with
MCP-compatible clients such as Claude Desktop or Claude Code.

## Project structure

```
.
├── Dockerfile
├── README.md
├── data
│   └── sample.csv
├── docker-compose.yml
└── server
    ├── pyproject.toml
    └── server.py
```

## Available tools

- `add(a: int, b: int)` – add two integers.
- `echo(text: str)` – echo the provided text.
- `describe_csv(path: str)` – load a CSV from `/data` and return key statistics.

## Running with Docker

Build and start the server using Docker Compose:

```bash
docker compose up --build -d
```

Mount your own CSV files by placing them in the `data/` directory before
starting the container. Once running, connect via Streamable HTTP at
`http://localhost:8080/stream`.

To stop the services, run:

```bash
docker compose down
```

## Local STDIO mode

For local experimentation without Docker, install dependencies and run the
server directly:

```bash
cd server
pip install "mcp>=1.2.0" "pandas>=2.2.0" "pyarrow>=15.0.0"
python server.py
```

Update the last line in `server.py` to `mcp.run(transport="stdio")` when using
STDIO clients.

## Testing the HTTP endpoint

After starting the Docker container, verify that the stream endpoint is
reachable:

```bash
curl -I http://localhost:8080/stream
```

A `200` or `404` response indicates that the endpoint is available for
Streamable HTTP connections.
