"""MCP server for data quality analysis functionality."""

# Import core functionality from src
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from modules import (
    CategoricalAnalysisOutput,
    DataQualityAnalyzer,
    DataQualityOutput,
    OutlierDetectionOutput,
    ProcessedDataOutput,
)

# Initialize data root and MCP server
DATA_ROOT = (Path(__file__).resolve().parents[1] / "data").resolve()

# Initialize MCP server
mcp = FastMCP(
    "mcp-data-quality",
    stateless_http=True,
    host="0.0.0.0",
    port=8081,  # Different port from main server
)

# Initialize analyzer instance
analyzer = DataQualityAnalyzer(DATA_ROOT)


# MCP Tool Wrappers


@mcp.tool()
def detect_outliers(
    path: str, column: str, method: str = "iqr"
) -> OutlierDetectionOutput:
    """
    Detect outliers in a numeric column using specified method.

    Args:
        path: Path to CSV file
        column: Column name to analyze
        method: Detection method ("iqr", "zscore", "isolation_forest")

    Returns:
        OutlierDetectionOutput with detected outliers and statistics

    Example:
        >>> detect_outliers("sample.csv", "age", "iqr")
    """
    return analyzer.detect_outliers(path, column, method)


@mcp.tool()
def analyze_categorical(path: str, column: str) -> CategoricalAnalysisOutput:
    """
    Perform detailed analysis of a categorical variable.

    Args:
        path: Path to CSV file
        column: Column name to analyze

    Returns:
        CategoricalAnalysisOutput with detailed categorical statistics

    Example:
        >>> analyze_categorical("sample.csv", "category")
    """
    return analyzer.analyze_categorical(path, column)


@mcp.tool()
def data_quality_report(path: str) -> DataQualityOutput:
    """
    Generate comprehensive data quality report for the entire dataset.

    Args:
        path: Path to CSV file

    Returns:
        DataQualityOutput with comprehensive quality metrics and recommendations

    Example:
        >>> data_quality_report("sample.csv")
    """
    return analyzer.generate_quality_report(path)


@mcp.tool()
def handle_missing_data(
    path: str, strategy: str = "mean", columns: Optional[List[str]] = None
) -> ProcessedDataOutput:
    """
    Handle missing values in the dataset using specified strategy.

    Args:
        path: Path to CSV file
        strategy: Handling strategy ("mean", "median", "mode", "drop", "fill_zero")
        columns: Specific columns to process (None for all columns)

    Returns:
        ProcessedDataOutput with information about changes made

    Example:
        >>> handle_missing_data("sample.csv", "mean", ["age", "income"])
    """
    return analyzer.handle_missing_data(path, strategy, columns)


@mcp.tool()
def list_data_quality_datasets() -> Dict[str, Any]:
    """List CSV files available for data quality analysis."""

    datasets: List[str] = []
    if DATA_ROOT.exists():
        for csv_file in sorted(DATA_ROOT.rglob("*.csv")):
            try:
                datasets.append(str(csv_file.relative_to(DATA_ROOT)))
            except ValueError:
                datasets.append(str(csv_file))

    return {
        "data_root": str(DATA_ROOT),
        "datasets": datasets,
        "server_info": "Data Quality Analysis Server",
        "available_methods": {
            "outlier_detection": ["iqr", "zscore", "isolation_forest"],
            "missing_data_strategies": ["mean", "median", "mode", "drop", "fill_zero"],
        },
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
    # Alternative: mcp.run(transport="streamable-http")
