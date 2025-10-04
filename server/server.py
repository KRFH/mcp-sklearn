from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union

import pandas as pd
from mcp.server.fastmcp import FastMCP


DATA_ROOT = Path("/data")

mcp = FastMCP(
    "mcp-proto",
    stateless_http=True,
    host="0.0.0.0",
    port=8080,
)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers and return the result."""
    return a + b


@mcp.tool()
def echo(text: str) -> str:
    """Echo back the provided text."""
    return text


@mcp.tool()
def describe_csv(path: str) -> Dict[str, Union[List[int], List[str], Dict[str, Dict[str, Union[float, str]]]]]:
    """Return basic statistics for a CSV file located under /data.

    Parameters
    ----------
    path:
        Absolute path to the CSV file or a path relative to /data.
    """

    csv_path = Path(path)
    if not csv_path.is_absolute():
        csv_path = DATA_ROOT / csv_path

    try:
        csv_path = csv_path.resolve(strict=True)
    except FileNotFoundError as exc:  # pragma: no cover - FastMCP handles errors
        raise FileNotFoundError(f"CSV file not found: {path}") from exc

    if DATA_ROOT not in csv_path.parents and csv_path != DATA_ROOT:
        raise ValueError("CSV path must be located within /data")

    df = pd.read_csv(csv_path)
    describe_df = df.describe(include="all").fillna("")
    return {
        "path": str(csv_path),
        "shape": list(df.shape),
        "columns": df.columns.tolist(),
        "describe": {col: stats.to_dict() for col, stats in describe_df.items()},
    }


if __name__ == "__main__":
    # HTTP(Streamable) transport is convenient for Docker deployments.
    # For local STDIO usage, call mcp.run(transport="stdio").
    mcp.run(transport="streamable-http")
