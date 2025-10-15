"""EDA analysis functionality."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from .dataclass import (
    ColumnInfoOutput,
    ColumnSummary,
    CorrelationMatrixOutput,
    DescribeCSVOutput,
    ListDatasetsOutput,
    MissingValuesOutput,
    MissingValueSummary,
    PreviewCSVOutput,
)


def _ensure_serializable(values: Iterable) -> List[Optional[object]]:
    """Convert values to JSON-serializable format."""
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


class EDAAnalyzer:
    """探索的データ分析のメインクラス"""

    def __init__(self, data_root: Path):
        self.data_root = data_root

    def _resolve_csv_path(self, path: str) -> Path:
        """CSVパスの解決"""
        csv_path = Path(path)
        if not csv_path.is_absolute():
            csv_path = self.data_root / csv_path

        try:
            csv_path = csv_path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"CSV file not found: {path}") from exc

        if self.data_root not in csv_path.parents and csv_path != self.data_root:
            raise ValueError("CSV path must be located within the data directory")

        return csv_path

    def list_datasets(self) -> ListDatasetsOutput:
        """データディレクトリ下の利用可能なCSVファイルをリスト"""
        datasets: List[str] = []
        if self.data_root.exists():
            for csv_file in sorted(self.data_root.rglob("*.csv")):
                try:
                    datasets.append(str(csv_file.relative_to(self.data_root)))
                except ValueError:
                    datasets.append(str(csv_file))
        return ListDatasetsOutput(data_root=str(self.data_root), datasets=datasets)

    def preview_csv(self, path: str, n_rows: int = 5) -> PreviewCSVOutput:
        """CSVファイルの最初のn行を返す"""
        csv_path = self._resolve_csv_path(path)
        df = pd.read_csv(csv_path)
        preview_df = df.head(n_rows).where(lambda d: ~d.isna(), other=None)
        rows: List[Dict[str, Optional[Any]]] = preview_df.to_dict(orient="records")
        return PreviewCSVOutput(
            path=str(csv_path),
            n_rows=len(preview_df),
            columns=preview_df.columns.tolist(),
            rows=rows,
        )

    def column_info(self, path: str) -> ColumnInfoOutput:
        """各カラムのdtypeと基本統計を返す"""
        csv_path = self._resolve_csv_path(path)
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

    def missing_values(self, path: str) -> MissingValuesOutput:
        """欠損値の数と比率をサマリー"""
        csv_path = self._resolve_csv_path(path)
        df = pd.read_csv(csv_path)

        total_rows = len(df)
        summary: Dict[str, MissingValueSummary] = {}
        for column, count in df.isna().sum().items():
            summary[column] = MissingValueSummary(
                missing=int(count),
                ratio=float(count / total_rows) if total_rows else 0.0,
            )
        return MissingValuesOutput(
            path=str(csv_path), summary=summary, n_rows=total_rows
        )

    def describe_csv(self, path: str) -> DescribeCSVOutput:
        """CSVファイルの記述統計を返す"""
        csv_path = self._resolve_csv_path(path)
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

    def correlation_matrix(
        self,
        path: str,
        *,
        columns: Optional[List[str]] = None,
        method: str = "pearson",
    ) -> CorrelationMatrixOutput:
        """数値カラムの相関行列を計算"""
        csv_path = self._resolve_csv_path(path)
        df = pd.read_csv(csv_path)

        numeric_df = df.select_dtypes(include="number")
        if columns:
            missing_cols = [col for col in columns if col not in numeric_df.columns]
            if missing_cols:
                raise ValueError(
                    f"Non-numeric or missing columns requested: {missing_cols}"
                )
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
