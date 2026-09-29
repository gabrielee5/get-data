from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from cryptodl.writers import build_filename, write, write_csv, write_parquet


def test_build_filename_replaces_slash_and_formats_dates():
    name = build_filename(
        "binance",
        "BTC/USDT",
        "1h",
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 2, 1, tzinfo=timezone.utc),
        "csv",
    )
    assert name == "binance_BTC-USDT_1h_20240101_20240201.csv"


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "timestamp": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [10.5, 11.5],
        }
    )


def test_write_csv_round_trip(tmp_path: Path, sample_df):
    path = tmp_path / "out.csv"
    write_csv(sample_df, path)
    result = pd.read_csv(path)
    assert list(result.columns) == list(sample_df.columns)
    assert len(result) == 2
    assert result["timestamp"].iloc[0] == "2024-01-01T00:00:00Z"


def test_write_parquet_round_trip(tmp_path: Path, sample_df):
    path = tmp_path / "out.parquet"
    write_parquet(sample_df, path)
    result = pd.read_parquet(path)
    assert list(result.columns) == list(sample_df.columns)
    assert len(result) == 2


def test_write_dispatches_on_format(tmp_path: Path, sample_df):
    write(sample_df, tmp_path / "a.csv", "csv")
    write(sample_df, tmp_path / "b.parquet", "parquet")
    assert (tmp_path / "a.csv").exists()
    assert (tmp_path / "b.parquet").exists()

    with pytest.raises(ValueError, match="Unknown format"):
        write(sample_df, tmp_path / "c.bad", "bad")


def test_write_creates_missing_output_dir(tmp_path: Path, sample_df):
    path = tmp_path / "nested" / "dir" / "out.csv"
    write_csv(sample_df, path)
    assert path.exists()
