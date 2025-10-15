"""Data models for preprocessing functionality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Union


@dataclass
class OutlierInfo:
    """単一の異常値に関する情報"""

    index: int
    value: Union[float, int]
    score: float
    method: str


@dataclass
class OutlierDetectionOutput:
    """異常値検出結果"""

    path: str
    column: str
    method: str
    total_outliers: int
    outlier_percentage: float
    outliers: List[OutlierInfo]
    threshold_info: Dict[str, float]


@dataclass
class CategoricalInfo:
    """カテゴリカル変数の詳細情報"""

    unique_count: int
    value_counts: Dict[str, int]
    value_percentages: Dict[str, float]
    mode: str
    mode_frequency: int
    entropy: float


@dataclass
class CategoricalAnalysisOutput:
    """カテゴリカル変数分析結果"""

    path: str
    column: str
    info: CategoricalInfo
    recommendations: List[str]


@dataclass
class DataQualityMetrics:
    """データ品質メトリクス"""

    total_rows: int
    total_columns: int
    duplicate_rows: int
    duplicate_percentage: float
    missing_data_summary: Dict[str, Dict[str, Union[int, float]]]
    data_types_summary: Dict[str, str]
    memory_usage_mb: float


@dataclass
class DataQualityOutput:
    """包括的なデータ品質レポート"""

    path: str
    metrics: DataQualityMetrics
    column_quality: Dict[str, Dict[str, Any]]
    recommendations: List[str]
    severity_score: float  # 0-100, higher is worse


@dataclass
class ProcessedDataInfo:
    """処理されたデータの情報"""

    original_shape: Tuple[int, int]
    processed_shape: Tuple[int, int]
    changes_made: List[str]
    affected_columns: List[str]


@dataclass
class ProcessedDataOutput:
    """データ処理結果"""

    path: str
    strategy: str
    info: ProcessedDataInfo
    processed_data_preview: List[Dict[str, Any]]  # First 5 rows
