"""MCP server for EDA functionality."""

from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import FastMCP
from modules.dataclass import (
    ColumnInfoOutput,
    CorrelationMatrixOutput,
    DescribeCSVOutput,
    ListDatasetsOutput,
    MissingValuesOutput,
    PreviewCSVOutput,
)
from modules.eda_analyzer import EDAAnalyzer

DATA_ROOT = (Path(__file__).resolve().parents[1] / "data").resolve()

mcp = FastMCP(
    "mcp-proto",
    stateless_http=True,
    host="0.0.0.0",
    port=8080,
)

# Initialize analyzer instance
analyzer = EDAAnalyzer(DATA_ROOT)


@mcp.tool()
def list_datasets() -> ListDatasetsOutput:
    """List CSV files available under the data directory."""
    return analyzer.list_datasets()


@mcp.tool()
def preview_csv(path: str, n_rows: int = 5) -> PreviewCSVOutput:
    """Return the first ``n_rows`` rows from the CSV file."""
    return analyzer.preview_csv(path, n_rows)


@mcp.tool()
def column_info(path: str) -> ColumnInfoOutput:
    """Return dtype and basic counts for each column."""
    return analyzer.column_info(path)


@mcp.tool()
def missing_values(path: str) -> MissingValuesOutput:
    """Summarise missing value counts and ratios."""
    return analyzer.missing_values(path)


@mcp.tool()
def describe_csv(path: str) -> DescribeCSVOutput:
    """Return descriptive statistics for the CSV file."""
    return analyzer.describe_csv(path)


@mcp.tool()
def correlation_matrix(
    path: str,
    *,
    columns: Optional[List[str]] = None,
    method: str = "pearson",
) -> CorrelationMatrixOutput:
    """Compute a correlation matrix for numeric columns."""
    return analyzer.correlation_matrix(path, columns=columns, method=method)


if __name__ == "__main__":
    mcp.run(transport="stdio")
    # mcp.run(transport="streamable-http")
