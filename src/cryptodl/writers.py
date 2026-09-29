"""CSV / Parquet output helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

VALID_FORMATS = ("csv", "parquet")


def build_filename(
    exchange_id: str, symbol: str, timeframe: str, start: datetime, end: datetime, fmt: str
) -> str:
    """e.g. binance_BTC-USDT_1h_20240101_20240201.csv"""
    safe_symbol = symbol.replace("/", "-")
    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")
    return f"{exchange_id}_{safe_symbol}_{timeframe}_{start_str}_{end_str}.{fmt}"


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")


def write(df: pd.DataFrame, path: Path, fmt: str) -> None:
    if fmt == "csv":
        write_csv(df, path)
    elif fmt == "parquet":
        write_parquet(df, path)
    else:
        raise ValueError(f"Unknown format '{fmt}'. Must be one of {VALID_FORMATS}.")
