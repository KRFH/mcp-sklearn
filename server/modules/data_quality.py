"""Data quality analysis functionality."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest

from .dataclass import (
    CategoricalAnalysisOutput,
    CategoricalInfo,
    DataQualityMetrics,
    DataQualityOutput,
    OutlierDetectionOutput,
    OutlierInfo,
    ProcessedDataInfo,
    ProcessedDataOutput,
)

# Suppress sklearn warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)


class DataQualityAnalyzer:
    """データ品質分析のメインクラス"""

    def __init__(self, data_root: Path):
        self.data_root = data_root

    def _resolve_csv_path(self, path: str) -> Path:
        """CSVパスの解決（server.pyから移植）"""
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

    def detect_outliers(
        self, path: str, column: str, method: str = "iqr"
    ) -> OutlierDetectionOutput:
        """
        異常値検出を実行

        Args:
            path: CSVファイルパス
            column: 対象カラム名
            method: 検出手法 ("iqr", "zscore", "isolation_forest")
        """
        csv_path = self._resolve_csv_path(path)
        df = pd.read_csv(csv_path)

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in dataset")

        series = df[column].dropna()
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError(f"Column '{column}' is not numeric")

        outliers = []
        threshold_info = {}

        if method == "iqr":
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            threshold_info = {
                "Q1": float(Q1),
                "Q3": float(Q3),
                "IQR": float(IQR),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
            }

            outlier_mask = (series < lower_bound) | (series > upper_bound)
            outlier_indices = series[outlier_mask].index.tolist()

            for idx in outlier_indices:
                value = series.iloc[idx]
                # IQRメソッドでは距離をスコアとして使用
                score = min(abs(value - lower_bound), abs(value - upper_bound))
                outliers.append(
                    OutlierInfo(
                        index=int(idx),
                        value=float(value),
                        score=float(score),
                        method=method,
                    )
                )

        elif method == "zscore":
            z_scores = np.abs(stats.zscore(series))
            threshold = 3.0
            threshold_info = {"threshold": threshold}

            outlier_mask = z_scores > threshold
            outlier_indices = series[outlier_mask].index.tolist()

            for idx in outlier_indices:
                value = series.iloc[idx]
                score = z_scores[idx]
                outliers.append(
                    OutlierInfo(
                        index=int(idx),
                        value=float(value),
                        score=float(score),
                        method=method,
                    )
                )

        elif method == "isolation_forest":
            # Isolation Forestは2D配列が必要
            X = series.values.reshape(-1, 1)

            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            outlier_labels = iso_forest.fit_predict(X)
            outlier_scores = iso_forest.score_samples(X)

            threshold_info = {"contamination": 0.1}

            outlier_indices = series[outlier_labels == -1].index.tolist()

            for idx in outlier_indices:
                value = series.iloc[idx]
                # 異常スコア（負の値）を正の値に変換
                score = abs(outlier_scores[idx])
                outliers.append(
                    OutlierInfo(
                        index=int(idx),
                        value=float(value),
                        score=float(score),
                        method=method,
                    )
                )
        else:
            raise ValueError(f"Unsupported method: {method}")

        # スコア順でソート
        outliers.sort(key=lambda x: x.score, reverse=True)

        return OutlierDetectionOutput(
            path=str(csv_path),
            column=column,
            method=method,
            total_outliers=len(outliers),
            outlier_percentage=float(len(outliers) / len(series) * 100),
            outliers=outliers[:20],  # 上位20個まで
            threshold_info=threshold_info,
        )

    def analyze_categorical(self, path: str, column: str) -> CategoricalAnalysisOutput:
        """
        カテゴリカル変数の詳細分析

        Args:
            path: CSVファイルパス
            column: 対象カラム名
        """
        csv_path = self._resolve_csv_path(path)
        df = pd.read_csv(csv_path)

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in dataset")

        series = df[column].dropna()
        value_counts = series.value_counts()
        total_count = len(series)

        # パーセンテージ計算
        value_percentages = {
            str(k): float(v / total_count * 100) for k, v in value_counts.items()
        }

        # エントロピー計算
        probabilities = value_counts / total_count
        entropy = -np.sum(probabilities * np.log2(probabilities))

        # 推奨事項生成
        recommendations = []
        unique_count = len(value_counts)

        if unique_count > 50:
            recommendations.append(
                f"高カーディナリティ ({unique_count} unique values): カテゴリの統合を検討"
            )

        if value_counts.iloc[0] / total_count > 0.9:
            recommendations.append("支配的なカテゴリが存在: データの偏りに注意")

        if unique_count == total_count:
            recommendations.append("全て異なる値: IDカラムの可能性があります")

        categorical_info = CategoricalInfo(
            unique_count=unique_count,
            value_counts={str(k): int(v) for k, v in value_counts.items()},
            value_percentages=value_percentages,
            mode=str(value_counts.index[0]),
            mode_frequency=int(value_counts.iloc[0]),
            entropy=float(entropy),
        )

        return CategoricalAnalysisOutput(
            path=str(csv_path),
            column=column,
            info=categorical_info,
            recommendations=recommendations,
        )

    def generate_quality_report(self, path: str) -> DataQualityOutput:
        """
        包括的なデータ品質レポートを生成

        Args:
            path: CSVファイルパス
        """
        csv_path = self._resolve_csv_path(path)
        df = pd.read_csv(csv_path)

        # 基本メトリクス
        total_rows, total_columns = df.shape
        duplicate_rows = df.duplicated().sum()
        duplicate_percentage = float(duplicate_rows / total_rows * 100)

        # メモリ使用量
        memory_usage_mb = float(df.memory_usage(deep=True).sum() / 1024 / 1024)

        # 欠損データサマリー
        missing_summary = {}
        for column in df.columns:
            missing_count = df[column].isna().sum()
            missing_percentage = float(missing_count / total_rows * 100)
            missing_summary[column] = {
                "missing_count": int(missing_count),
                "missing_percentage": missing_percentage,
            }

        # データ型サマリー
        data_types_summary = {col: str(dtype) for col, dtype in df.dtypes.items()}

        # カラム別品質分析
        column_quality = {}
        for column in df.columns:
            series = df[column]
            quality_info = {
                "data_type": str(series.dtype),
                "non_null_count": int(series.notna().sum()),
                "null_count": int(series.isna().sum()),
                "unique_count": int(series.nunique()),
            }

            # 数値カラムの場合
            if pd.api.types.is_numeric_dtype(series):
                quality_info.update(
                    {
                        "mean": float(series.mean())
                        if not series.isna().all()
                        else None,
                        "std": float(series.std()) if not series.isna().all() else None,
                        "min": float(series.min()) if not series.isna().all() else None,
                        "max": float(series.max()) if not series.isna().all() else None,
                        "zero_count": int((series == 0).sum()),
                        "negative_count": int((series < 0).sum()),
                    }
                )

            # カテゴリカルカラムの場合
            elif pd.api.types.is_object_dtype(series):
                quality_info.update(
                    {
                        "most_frequent": str(series.mode().iloc[0])
                        if not series.empty
                        else None,
                        "most_frequent_count": int(series.value_counts().iloc[0])
                        if not series.empty
                        else 0,
                        "cardinality_ratio": float(series.nunique() / len(series))
                        if len(series) > 0
                        else 0.0,
                    }
                )

            column_quality[column] = quality_info

        # 推奨事項とスコア計算
        recommendations = []
        severity_score = 0.0

        # 欠損データ評価
        high_missing_cols = [
            col
            for col, info in missing_summary.items()
            if info["missing_percentage"] > 20
        ]
        if high_missing_cols:
            recommendations.append(
                f"高欠損率カラム ({len(high_missing_cols)}個): {', '.join(high_missing_cols[:3])}"
            )
            severity_score += len(high_missing_cols) * 10

        # 重複データ評価
        if duplicate_percentage > 5:
            recommendations.append(
                f"重複行が多い ({duplicate_percentage:.1f}%): データクリーニングを推奨"
            )
            severity_score += duplicate_percentage

        # 高カーディナリティ評価
        high_card_cols = [
            col
            for col, info in column_quality.items()
            if info.get("cardinality_ratio", 0) > 0.9
        ]
        if high_card_cols:
            recommendations.append(
                f"高カーディナリティカラム: {', '.join(high_card_cols[:3])}"
            )
            severity_score += len(high_card_cols) * 5

        # メモリ使用量評価
        if memory_usage_mb > 100:
            recommendations.append(
                f"大きなメモリ使用量 ({memory_usage_mb:.1f}MB): 最適化を検討"
            )
            severity_score += min(memory_usage_mb / 10, 20)

        metrics = DataQualityMetrics(
            total_rows=total_rows,
            total_columns=total_columns,
            duplicate_rows=int(duplicate_rows),
            duplicate_percentage=duplicate_percentage,
            missing_data_summary=missing_summary,
            data_types_summary=data_types_summary,
            memory_usage_mb=memory_usage_mb,
        )

        return DataQualityOutput(
            path=str(csv_path),
            metrics=metrics,
            column_quality=column_quality,
            recommendations=recommendations,
            severity_score=min(severity_score, 100.0),  # 最大100
        )

    def handle_missing_data(
        self, path: str, strategy: str = "mean", columns: Optional[List[str]] = None
    ) -> ProcessedDataOutput:
        """
        欠損値処理を実行

        Args:
            path: CSVファイルパス
            strategy: 処理戦略 ("mean", "median", "mode", "drop", "fill_zero")
            columns: 対象カラム（Noneの場合は全カラム）
        """
        csv_path = self._resolve_csv_path(path)
        df = pd.read_csv(csv_path)
        original_shape = df.shape

        changes_made = []
        affected_columns = []

        # 処理対象カラムの決定
        target_columns = columns if columns else df.columns.tolist()

        for column in target_columns:
            if column not in df.columns:
                continue

            missing_count = df[column].isna().sum()
            if missing_count == 0:
                continue

            affected_columns.append(column)

            if strategy == "drop":
                df = df.dropna(subset=[column])
                changes_made.append(f"{column}: {missing_count}行を削除")

            elif strategy == "mean" and pd.api.types.is_numeric_dtype(df[column]):
                mean_value = df[column].mean()
                df[column].fillna(mean_value, inplace=True)
                changes_made.append(f"{column}: 平均値{mean_value:.2f}で補完")

            elif strategy == "median" and pd.api.types.is_numeric_dtype(df[column]):
                median_value = df[column].median()
                df[column].fillna(median_value, inplace=True)
                changes_made.append(f"{column}: 中央値{median_value:.2f}で補完")

            elif strategy == "mode":
                if not df[column].dropna().empty:
                    mode_value = df[column].mode().iloc[0]
                    df[column].fillna(mode_value, inplace=True)
                    changes_made.append(f"{column}: 最頻値'{mode_value}'で補完")

            elif strategy == "fill_zero":
                df[column].fillna(0, inplace=True)
                changes_made.append(f"{column}: 0で補完")

        processed_shape = df.shape

        # プレビューデータの作成
        preview_df = df.head(5).where(lambda d: ~d.isna(), other=None)
        processed_data_preview = preview_df.to_dict(orient="records")

        info = ProcessedDataInfo(
            original_shape=original_shape,
            processed_shape=processed_shape,
            changes_made=changes_made,
            affected_columns=affected_columns,
        )

        return ProcessedDataOutput(
            path=str(csv_path),
            strategy=strategy,
            info=info,
            processed_data_preview=processed_data_preview,
        )
