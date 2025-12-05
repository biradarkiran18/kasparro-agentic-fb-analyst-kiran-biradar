"""
Edge case tests for data handling, missing values, and extreme scenarios.

Tests cover:
- Empty dataframes
- NaN-heavy data
- Missing required columns
- Zero divisions
- Malformed CSV files
- Extreme values (Infinity, very large numbers)
"""
import os
import tempfile

import pandas as pd
import numpy as np

from src.agents.data_agent import load_csv_safe, summarize_df
from src.agents.evaluator import validate
from src.utils.baseline import compute_global_baselines
from src.utils.schema import validate_schema


class TestEmptyDataframes:
    """Test handling of empty or nearly-empty dataframes."""

    def test_empty_dataframe(self):
        """Test that empty dataframe raises appropriate error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("date,spend,impressions,clicks,revenue\n")
            temp_path = f.name

        try:
            df = load_csv_safe(temp_path)
            assert len(df) == 0, "Should load empty dataframe without crash"

            # Summary should handle empty data gracefully
            summary = summarize_df(df)
            assert summary["global"]["total_spend"] == 0.0
            assert summary["global"]["total_impressions"] == 0
            assert len(summary["by_campaign"]) == 0
        finally:
            os.unlink(temp_path)

    def test_single_row_dataframe(self):
        """Test handling of dataframe with only one row."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("date,spend,impressions,clicks,revenue,campaign\n")
            f.write("2024-01-01,100.0,1000,10,50.0,test_campaign\n")
            temp_path = f.name

        try:
            df = load_csv_safe(temp_path)
            summary = summarize_df(df)

            assert summary["global"]["total_spend"] == 100.0
            assert len(summary["by_campaign"]) == 1

            # Baseline computation should not crash
            baseline = compute_global_baselines(df, window_days=1)
            assert baseline is not None
        finally:
            os.unlink(temp_path)


class TestNaNHandling:
    """Test handling of missing and NaN values."""

    def test_nan_heavy_data(self):
        """Test dataframe with many NaN values."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'spend': [100.0, np.nan, np.nan, 150.0, np.nan, 200.0, np.nan, np.nan, 300.0, np.nan],
            'impressions': [1000, np.nan, 2000, np.nan, 3000, np.nan, np.nan, 4000, np.nan, 5000],
            'clicks': [10, 20, np.nan, np.nan, 30, 40, np.nan, np.nan, 50, np.nan],
            'revenue': [50, np.nan, 100, np.nan, np.nan, 200, 300, np.nan, np.nan, 400],
            'campaign': ['A', 'A', 'B', 'B', 'A', 'A', 'B', 'B', 'A', 'B']
        })

        # Should not crash
        summary = summarize_df(df)

        # Check that NaN values are handled (should skip or use 0)
        assert isinstance(summary["global"]["total_spend"], (int, float))
        assert not np.isnan(summary["global"]["total_spend"])
        assert not np.isinf(summary["global"]["total_spend"])

    def test_all_nan_column(self):
        """Test dataframe where entire columns are NaN."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'spend': [np.nan] * 5,
            'impressions': [1000, 2000, 3000, 4000, 5000],
            'clicks': [np.nan] * 5,
            'revenue': [100, 200, 300, 400, 500],
            'campaign': ['A', 'A', 'B', 'B', 'A']
        })

        summary = summarize_df(df)

        # Should handle gracefully
        assert summary["global"]["total_spend"] == 0.0
        assert summary["global"]["total_impressions"] > 0

        # CTR should be 0 or handle division by zero
        for camp in summary["by_campaign"]:
            assert not np.isnan(camp.get("ctr", 0.0))
            assert not np.isinf(camp.get("ctr", 0.0))


class TestMissingColumns:
    """Test handling of missing required columns."""

    def test_missing_required_column(self):
        """Test when required columns are missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            # Missing 'clicks' column
            f.write("date,spend,impressions,revenue\n")
            f.write("2024-01-01,100.0,1000,50.0\n")
            temp_path = f.name

        try:
            df = load_csv_safe(temp_path)
            is_valid, errors = validate_schema(df, strict=False)

            # Should detect missing column but not crash
            assert not is_valid
            assert any('clicks' in str(err).lower() for err in errors)

            # Summary should still work with fallback
            summary = summarize_df(df)
            assert "global" in summary
        finally:
            os.unlink(temp_path)

    def test_optional_campaign_column_missing(self):
        """Test when optional 'campaign' column is missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("date,spend,impressions,clicks,revenue\n")
            f.write("2024-01-01,100.0,1000,10,50.0\n")
            f.write("2024-01-02,150.0,1500,15,75.0\n")
            temp_path = f.name

        try:
            df = load_csv_safe(temp_path)
            summary = summarize_df(df)

            # Should work without campaign breakdown
            assert "global" in summary
            assert summary["global"]["total_spend"] == 250.0
            # by_campaign should be empty or have single 'unknown' entry
            assert len(summary["by_campaign"]) <= 1
        finally:
            os.unlink(temp_path)


class TestZeroDivision:
    """Test handling of zero division scenarios."""

    def test_zero_impressions(self):
        """Test CTR calculation with zero impressions."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=3),
            'spend': [100.0, 150.0, 200.0],
            'impressions': [0, 0, 0],
            'clicks': [10, 20, 30],
            'revenue': [50, 75, 100],
            'campaign': ['A', 'A', 'B']
        })

        summary = summarize_df(df)

        # Should not crash, CTR should be 0 or handled safely
        for camp in summary["by_campaign"]:
            ctr = camp.get("ctr", 0.0)
            assert not np.isnan(ctr)
            assert not np.isinf(ctr)
            assert ctr == 0.0  # With zero impressions, CTR should be 0

    def test_zero_spend(self):
        """Test ROAS calculation with zero spend."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=3),
            'spend': [0.0, 0.0, 0.0],
            'impressions': [1000, 2000, 3000],
            'clicks': [10, 20, 30],
            'revenue': [50, 75, 100],
            'campaign': ['A', 'A', 'B']
        })

        summary = summarize_df(df)  # noqa: F841
        baseline = compute_global_baselines(df, window_days=1)

        # ROAS should be 0 or handled safely (not infinity)
        assert baseline is not None
        roas = baseline.get("global_roas", 0.0)
        # With zero spend, ROAS could be infinity - should be handled
        assert not np.isnan(roas)


class TestMalformedCSV:
    """Test handling of malformed CSV files."""

    def test_inconsistent_columns(self):
        """Test CSV with inconsistent column counts."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("date,spend,impressions,clicks,revenue\n")
            f.write("2024-01-01,100.0,1000,10,50.0\n")
            f.write("2024-01-02,150.0,1500\n")  # Missing columns
            f.write("2024-01-03,200.0,2000,20,100.0,extra\n")  # Extra column
            temp_path = f.name

        try:
            # Should handle with on_bad_lines='skip' or error logging
            df = load_csv_safe(temp_path)
            assert len(df) >= 1  # At least one valid row should load
        finally:
            os.unlink(temp_path)

    def test_non_numeric_values(self):
        """Test CSV with non-numeric values in numeric columns."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("date,spend,impressions,clicks,revenue,campaign\n")
            f.write("2024-01-01,100.0,1000,10,50.0,A\n")
            f.write("2024-01-02,invalid,1500,15,75.0,B\n")
            f.write("2024-01-03,200.0,not_a_number,20,100.0,A\n")
            temp_path = f.name

        try:
            df = load_csv_safe(temp_path)

            # Pandas will convert to NaN, our code should handle it
            summary = summarize_df(df)
            total_spend = summary["global"].get("total_spend", 0.0)
            assert isinstance(total_spend, (int, float))
            assert not np.isnan(total_spend)
            assert not np.isinf(total_spend)
        finally:
            os.unlink(temp_path)


class TestExtremeValues:
    """Test handling of extreme numeric values."""

    def test_infinity_values(self):
        """Test handling of infinity values in data."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=3),
            'spend': [100.0, np.inf, 200.0],
            'impressions': [1000, 2000, np.inf],
            'clicks': [10, 20, 30],
            'revenue': [50, np.inf, 100],
            'campaign': ['A', 'B', 'A']
        })

        summary = summarize_df(df)

        # Should filter out infinity values
        total_spend = summary["global"].get("total_spend", 0.0)
        total_impressions = summary["global"].get("total_impressions", 0)
        assert isinstance(total_spend, (int, float))
        assert isinstance(total_impressions, (int, float))
        assert not np.isinf(total_spend)
        assert not np.isinf(total_impressions)

    def test_very_large_numbers(self):
        """Test handling of very large numbers."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=3),
            'spend': [1e15, 1e15, 1e15],
            'impressions': [1e15, 1e15, 1e15],
            'clicks': [1e10, 1e10, 1e10],
            'revenue': [1e15, 1e15, 1e15],
            'campaign': ['A', 'A', 'B']
        })

        summary = summarize_df(df)

        # Should handle large numbers without overflow
        assert isinstance(summary["global"]["total_spend"], (int, float))
        assert summary["global"]["total_spend"] > 0

    def test_negative_values(self):
        """Test handling of negative values (e.g., refunds)."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=3),
            'spend': [100.0, -50.0, 200.0],  # Negative spend (refund?)
            'impressions': [1000, 2000, 3000],
            'clicks': [10, 20, 30],
            'revenue': [50, -25, 100],  # Negative revenue (refund)
            'campaign': ['A', 'A', 'B']
        })

        summary = summarize_df(df)

        # Should handle negative values (net calculation)
        assert isinstance(summary["global"]["total_spend"], (int, float))
        # Net spend could be positive or negative
        assert summary["global"]["total_spend"] == 250.0  # 100 - 50 + 200


class TestEvaluatorEdgeCases:
    """Test evaluator with edge case hypotheses."""

    def test_empty_hypotheses_list(self):
        """Test evaluator with empty hypotheses."""
        hypotheses = []
        summary = {
            "global": {"total_spend": 100.0, "total_revenue": 50.0}
        }
        cfg = {"confidence_min": 0.5}

        validated, metrics = validate(hypotheses, summary, cfg)

        assert validated == []
        assert metrics["num_hypotheses"] == 0
        assert metrics["validation_rate"] == 0.0

    def test_malformed_hypothesis_structure(self):
        """Test evaluator with missing required fields."""
        hypotheses = [
            {"hypothesis": "Test 1"},  # Missing initial_confidence
            {"initial_confidence": 0.8},  # Missing hypothesis
            {}  # Empty dict
        ]
        summary = {
            "global": {"total_spend": 100.0, "total_revenue": 50.0, "ctr": 0.01, "roas": 0.5}
        }
        cfg = {"confidence_min": 0.5}

        # Should handle gracefully without crashing
        validated, metrics = validate(hypotheses, summary, cfg)

        # Should return results without crashing
        assert isinstance(validated, list)
        assert isinstance(metrics, dict)

    def test_extreme_confidence_values(self):
        """Test hypotheses with out-of-range confidence values."""
        hypotheses = [
            {
                "id": "h1",
                "hypothesis": "Test extreme confidence",
                "initial_confidence": 5.0,  # > 1.0
                "metrics_used": ["ctr"]
            },
            {
                "id": "h2",
                "hypothesis": "Test negative confidence",
                "initial_confidence": -0.5,  # < 0.0
                "metrics_used": ["roas"]
            }
        ]
        summary = {
            "global": {"total_spend": 100.0, "total_revenue": 50.0, "ctr": 0.01, "roas": 0.5}
        }
        cfg = {"confidence_min": 0.5}

        validated, metrics = validate(hypotheses, summary, cfg)

        # Should normalize confidence to 0-1 range
        for v in validated:
            if "confidence" in v:
                assert 0.0 <= v["confidence"] <= 1.0


class TestBaselineEdgeCases:
    """Test baseline computation with edge cases."""

    def test_baseline_with_insufficient_data(self):
        """Test baseline when data is less than min_days."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=2),  # Only 2 days
            'spend': [100.0, 150.0],
            'impressions': [1000, 1500],
            'clicks': [10, 15],
            'revenue': [50, 75],
        })

        baseline = compute_global_baselines(df, window_days=7)

        # Should still return baseline (may use available data or defaults)
        assert baseline is not None
        assert "ctr_baseline" in baseline

    def test_baseline_with_all_zeros(self):
        """Test baseline when all metrics are zero."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'spend': [0.0] * 5,
            'impressions': [0] * 5,
            'clicks': [0] * 5,
            'revenue': [0.0] * 5,
        })

        baseline = compute_global_baselines(df, window_days=1)

        # Should handle zeros gracefully
        assert baseline is not None
        assert baseline["ctr_baseline"] == 0.0
        # ROAS could be 0 or NaN with zero spend
        roas = baseline.get("roas_baseline", 0.0)
        assert roas == 0.0 or np.isnan(roas)
