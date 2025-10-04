from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
from mcp.server.fastmcp import FastMCP

DATA_ROOT = (Path(__file__).resolve().parents[1] / "data").resolve()


mcp = FastMCP(
    "mcp-proto",
    stateless_http=True,
    host="0.0.0.0",
    port=8080,
)


def _resolve_csv_path(path: str) -> Path:
    csv_path = Path(path)
    if not csv_path.is_absolute():
        csv_path = DATA_ROOT / csv_path

    try:
        csv_path = csv_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"CSV file not found: {path}") from exc

    if DATA_ROOT not in csv_path.parents and csv_path != DATA_ROOT:
        raise ValueError("CSV path must be located within the data directory")

    return csv_path


def _ensure_serializable(values: Iterable) -> List[Optional[object]]:
    import numpy as np
    
    serializable: List[Optional[object]] = []
    for value in values:
        if pd.isna(value):
            serializable.append(None)
        elif isinstance(value, (np.integer, np.floating)):
            # Convert numpy numeric types to Python types
            serializable.append(value.item())
        elif isinstance(value, np.ndarray):
            # Convert numpy arrays to lists
            serializable.append(value.tolist())
        else:
            serializable.append(value)
    return serializable


@dataclass
class ListDatasetsOutput:
    data_root: str
    datasets: List[str]


@dataclass
class PreviewCSVOutput:
    path: str
    n_rows: int
    columns: List[str]
    rows: List[Dict[str, Optional[Any]]]


@dataclass
class ColumnSummary:
    dtype: str
    non_null: int
    null: int
    unique: int


@dataclass
class ColumnInfoOutput:
    path: str
    columns: Dict[str, ColumnSummary]


@dataclass
class MissingValueSummary:
    missing: int
    ratio: float


@dataclass
class MissingValuesOutput:
    path: str
    summary: Dict[str, MissingValueSummary]
    n_rows: int


@dataclass
class DescribeCSVOutput:
    path: str
    shape: List[int]
    describe: Dict[str, Dict[str, Optional[Any]]]


@dataclass
class CorrelationMatrixOutput:
    path: str
    columns: List[str]
    method: str
    matrix: Dict[str, Dict[str, Optional[float]]]


@mcp.tool()
def list_datasets() -> ListDatasetsOutput:
    """List CSV files available under the data directory."""

    datasets: List[str] = []
    if DATA_ROOT.exists():
        for csv_file in sorted(DATA_ROOT.rglob("*.csv")):
            try:
                datasets.append(str(csv_file.relative_to(DATA_ROOT)))
            except ValueError:
                datasets.append(str(csv_file))
    return ListDatasetsOutput(data_root=str(DATA_ROOT), datasets=datasets)


@mcp.tool()
def preview_csv(path: str, n_rows: int = 5) -> PreviewCSVOutput:
    """Return the first ``n_rows`` rows from the CSV file."""

    csv_path = _resolve_csv_path(path)
    df = pd.read_csv(csv_path)
    preview_df = df.head(n_rows).where(lambda d: ~d.isna(), other=None)
    rows: List[Dict[str, Optional[Any]]] = preview_df.to_dict(orient="records")
    return PreviewCSVOutput(
        path=str(csv_path),
        n_rows=len(preview_df),
        columns=preview_df.columns.tolist(),
        rows=rows,
    )


@mcp.tool()
def column_info(path: str) -> ColumnInfoOutput:
    """Return dtype and basic counts for each column."""

    csv_path = _resolve_csv_path(path)
    df = pd.read_csv(csv_path)

    info: Dict[str, ColumnSummary] = {}
    for column in df.columns:
        series = df[column]
        info[column] = ColumnSummary(
            dtype=str(series.dtype),
            non_null=int(series.notna().sum()),
            null=int(series.isna().sum()),
            unique=int(series.nunique(dropna=True)),
        )
    return ColumnInfoOutput(path=str(csv_path), columns=info)


@mcp.tool()
def missing_values(path: str) -> MissingValuesOutput:
    """Summarise missing value counts and ratios."""

    csv_path = _resolve_csv_path(path)
    df = pd.read_csv(csv_path)

    total_rows = len(df)
    summary: Dict[str, MissingValueSummary] = {}
    for column, count in df.isna().sum().items():
        summary[column] = MissingValueSummary(
            missing=int(count),
            ratio=float(count / total_rows) if total_rows else 0.0,
        )
    return MissingValuesOutput(path=str(csv_path), summary=summary, n_rows=total_rows)


@mcp.tool()
def describe_csv(path: str) -> DescribeCSVOutput:
    """Return descriptive statistics for the CSV file."""

    csv_path = _resolve_csv_path(path)
    df = pd.read_csv(csv_path)
    describe_df = df.describe(include="all").transpose()
    describe: Dict[str, Dict[str, Optional[Any]]] = {}
    for column, stats in describe_df.iterrows():
        describe[column] = {
            key: (None if pd.isna(value) else _ensure_serializable([value])[0]) 
            for key, value in stats.items()
        }

    return DescribeCSVOutput(
        path=str(csv_path),
        shape=list(df.shape),
        describe=describe,
    )


@mcp.tool()
def correlation_matrix(
    path: str,
    *,
    columns: Optional[List[str]] = None,
    method: str = "pearson",
) -> CorrelationMatrixOutput:
    """Compute a correlation matrix for numeric columns."""

    csv_path = _resolve_csv_path(path)
    df = pd.read_csv(csv_path)

    numeric_df = df.select_dtypes(include="number")
    if columns:
        missing_cols = [col for col in columns if col not in numeric_df.columns]
        if missing_cols:
            raise ValueError(f"Non-numeric or missing columns requested: {missing_cols}")
        numeric_df = numeric_df[columns]

    if numeric_df.empty:
        raise ValueError("No numeric columns available for correlation computation")

    corr = numeric_df.corr(method=method)
    matrix = {
        column: dict(zip(corr.index, _ensure_serializable(corr[column].tolist())))
        for column in corr.columns
    }

    return CorrelationMatrixOutput(
        path=str(csv_path),
        columns=corr.columns.tolist(),
        method=method,
        matrix=matrix,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
