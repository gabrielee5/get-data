"""Core OHLCV download logic: pagination, retries, dedup, range trimming.

Plain functions only — no CLI or printing here, so other interfaces (e.g. an MCP
server) can reuse this module directly.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone

import ccxt
import pandas as pd

from cryptodl.discovery import get_exchange, validate_symbol, validate_timeframe
from cryptodl.errors import CryptoDLError

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# (last_candle_ts_ms, start_ms, end_ms, candles_fetched_so_far)
ProgressCallback = Callable[[int, int, int, int], None]


def parse_datetime_utc(value: str | datetime, field: str = "date") -> datetime:
    """Parse an ISO date ("2024-01-01") or datetime string as UTC.

    Naive datetimes (no timezone) are assumed to already be UTC, per the CLI contract.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        text = value.strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CryptoDLError(
                f"Could not parse {field} '{value}'. Use an ISO date (2024-01-01) "
                "or datetime (2024-01-01T00:00:00)."
            ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _fetch_with_retries(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    since: int,
    limit: int,
    max_retries: int,
) -> list[list]:
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        except ccxt.NetworkError as exc:
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
        except ccxt.ExchangeError as exc:
            raise CryptoDLError(f"Exchange error while fetching OHLCV: {exc}") from exc
    raise CryptoDLError(
        f"Network error while fetching OHLCV after {max_retries} attempts: {last_error}"
    )


def fetch_ohlcv_paginated(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
    limit: int = 1000,
    max_retries: int = 5,
    on_progress: ProgressCallback | None = None,
) -> list[list]:
    """Page forward through fetchOHLCV from start_ms until end_ms or data runs out.

    Stops when: a request returns no candles, `end_ms` has been passed, or the next
    `since` fails to advance past the current one (guards against an exchange
    returning the same batch again, which would otherwise loop forever).
    """
    timeframe_ms = exchange.parse_timeframe(timeframe) * 1000
    since = start_ms
    candles: list[list] = []

    while since <= end_ms:
        batch = _fetch_with_retries(exchange, symbol, timeframe, since, limit, max_retries)
        if not batch:
            break

        candles.extend(batch)
        next_since = batch[-1][0] + timeframe_ms

        if on_progress is not None:
            on_progress(batch[-1][0], start_ms, end_ms, len(candles))

        if next_since <= since:
            break
        since = next_since

    return candles


def to_dataframe(candles: list[list], start_ms: int, end_ms: int) -> pd.DataFrame:
    """Turn raw ccxt candles into a sorted, deduped, range-trimmed DataFrame."""
    df = pd.DataFrame(candles, columns=OHLCV_COLUMNS)
    if df.empty:
        return df

    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df = df[(df["timestamp"] >= start_ms) & (df["timestamp"] <= end_ms)]
    df = df.reset_index(drop=True)

    numeric_cols = ["open", "high", "low", "close", "volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return df


def download_ohlcv_with_exchange(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    start: str | datetime,
    end: str | datetime | None = None,
    limit: int = 1000,
    on_progress: ProgressCallback | None = None,
) -> pd.DataFrame:
    """Validate inputs against an already-constructed exchange and download OHLCV.

    Kept separate from `download_ohlcv` so tests can pass a duck-typed fake exchange
    without touching real ccxt exchange construction.
    """
    if not exchange.has.get("fetchOHLCV"):
        raise CryptoDLError(f"Exchange '{exchange.id}' does not support fetchOHLCV.")

    validate_symbol(exchange, symbol)
    validate_timeframe(exchange, timeframe)

    start_dt = parse_datetime_utc(start, "start")
    end_dt = parse_datetime_utc(end, "end") if end is not None else datetime.now(timezone.utc)

    if start_dt >= end_dt:
        raise CryptoDLError(
            f"start ({start_dt.isoformat()}) must be before end ({end_dt.isoformat()})."
        )

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    # Cap the per-request page size to roughly what the requested range needs, so a
    # short range (e.g. one day of 1h candles) doesn't pull a full 1000-candle page
    # (weeks of extra data) only to trim it back down afterwards.
    timeframe_ms = exchange.parse_timeframe(timeframe) * 1000
    span_candles = int((end_ms - start_ms) // timeframe_ms) + 2
    effective_limit = max(1, min(limit, span_candles))

    candles = fetch_ohlcv_paginated(
        exchange,
        symbol,
        timeframe,
        start_ms,
        end_ms,
        limit=effective_limit,
        on_progress=on_progress,
    )
    return to_dataframe(candles, start_ms, end_ms)


def download_ohlcv(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: str | datetime,
    end: str | datetime | None = None,
    limit: int = 1000,
    on_progress: ProgressCallback | None = None,
) -> pd.DataFrame:
    """Validate inputs and download OHLCV candles for [start, end] as a DataFrame."""
    exchange = get_exchange(exchange_id)
    return download_ohlcv_with_exchange(
        exchange, symbol, timeframe, start, end, limit=limit, on_progress=on_progress
    )
