from __future__ import annotations

import pytest

from cryptodl.errors import CryptoDLError
from cryptodl.fetch import (
    download_ohlcv_with_exchange,
    fetch_ohlcv_paginated,
    parse_datetime_utc,
    to_dataframe,
)

HOUR_MS = 3_600_000


def test_pagination_walks_forward_across_pages(fake_exchange, make_candles):
    candles = make_candles(start_ms=0, count=25, step_ms=HOUR_MS)
    ex = fake_exchange(candles)

    result = fetch_ohlcv_paginated(
        ex, "BTC/USDT", "1h", start_ms=0, end_ms=candles[-1][0], limit=10
    )

    assert [c[0] for c in result] == [c[0] for c in candles]
    # 25 candles at page size 10 -> 3 requests (10, 10, 5)
    assert len(ex.fetch_calls) == 3


def test_pagination_stops_when_batch_is_empty(fake_exchange, make_candles):
    candles = make_candles(start_ms=0, count=5, step_ms=HOUR_MS)
    ex = fake_exchange(candles)

    # end_ms far beyond available data; pagination must stop once fetch_ohlcv
    # returns an empty batch rather than looping until end_ms.
    result = fetch_ohlcv_paginated(
        ex, "BTC/USDT", "1h", start_ms=0, end_ms=1_000 * HOUR_MS, limit=10
    )

    assert len(result) == 5
    assert len(ex.fetch_calls) == 2  # one batch of 5, one empty batch, then stop


def test_pagination_guards_against_stuck_since(fake_exchange):
    class StuckExchange(fake_exchange):
        def fetch_ohlcv(self, symbol, timeframe="1m", since=None, limit=None, params=None):
            self.fetch_calls.append((since, limit))
            # Always returns the same batch regardless of `since` -- simulates a
            # buggy/misbehaving exchange that would otherwise loop forever.
            return [[0, 1, 2, 0.5, 1.5, 10], [HOUR_MS, 1, 2, 0.5, 1.5, 10]]

    ex = StuckExchange()

    result = fetch_ohlcv_paginated(ex, "BTC/USDT", "1h", start_ms=0, end_ms=100 * HOUR_MS, limit=10)

    # `since` advances once (0 -> 2h) on the strength of the batch's last candle,
    # but the next batch is identical and would produce the same next `since` again
    # -- the guard must catch that repeat and stop instead of looping forever.
    assert len(ex.fetch_calls) == 2
    assert len(result) == 4


def test_to_dataframe_dedupes_sorts_and_trims_range():
    candles = [
        [3 * HOUR_MS, 1, 2, 0.5, 1.5, 10],
        [1 * HOUR_MS, 1, 2, 0.5, 1.5, 10],
        [1 * HOUR_MS, 1, 2, 0.5, 1.5, 10],  # duplicate
        [5 * HOUR_MS, 1, 2, 0.5, 1.5, 10],  # outside range, trimmed
        [2 * HOUR_MS, 1, 2, 0.5, 1.5, 10],
    ]

    df = to_dataframe(candles, start_ms=1 * HOUR_MS, end_ms=3 * HOUR_MS)

    assert list(df["timestamp"]) == [
        "1970-01-01T01:00:00Z",
        "1970-01-01T02:00:00Z",
        "1970-01-01T03:00:00Z",
    ]
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df["open"].dtype.kind == "f"


def test_to_dataframe_empty_input_has_correct_columns():
    df = to_dataframe([], start_ms=0, end_ms=HOUR_MS)
    assert df.empty
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


def test_download_happy_path(fake_exchange, make_candles):
    candles = make_candles(start_ms=0, count=24, step_ms=HOUR_MS)
    ex = fake_exchange(candles)

    df = download_ohlcv_with_exchange(
        ex, "BTC/USDT", "1h", start="1970-01-01T00:00:00Z", end="1970-01-01T23:00:00Z"
    )

    assert len(df) == 24
    assert df["timestamp"].iloc[0] == "1970-01-01T00:00:00Z"
    assert df["timestamp"].iloc[-1] == "1970-01-01T23:00:00Z"


def test_unknown_symbol_raises_with_suggestions(fake_exchange):
    ex = fake_exchange([])
    with pytest.raises(CryptoDLError) as excinfo:
        download_ohlcv_with_exchange(ex, "BTC/USD", "1h", start="2024-01-01")
    assert "BTC/USD" in excinfo.value.message
    assert "BTC/USDT" in excinfo.value.suggestions


def test_unknown_timeframe_raises_with_suggestions(fake_exchange):
    ex = fake_exchange([])
    with pytest.raises(CryptoDLError) as excinfo:
        download_ohlcv_with_exchange(ex, "BTC/USDT", "1hh", start="2024-01-01")
    assert "1hh" in excinfo.value.message
    assert "1h" in excinfo.value.suggestions


def test_start_after_end_raises(fake_exchange):
    ex = fake_exchange([])
    with pytest.raises(CryptoDLError, match="must be before"):
        download_ohlcv_with_exchange(
            ex, "BTC/USDT", "1h", start="2024-02-01", end="2024-01-01"
        )


def test_download_caps_page_size_to_requested_range(fake_exchange, make_candles):
    # 24 hourly candles requested, but the exchange's default page limit is 1000 --
    # the effective per-request limit should be capped near what's actually needed.
    candles = make_candles(start_ms=0, count=1000, step_ms=HOUR_MS)
    ex = fake_exchange(candles)

    download_ohlcv_with_exchange(
        ex, "BTC/USDT", "1h", start="1970-01-01T00:00:00Z", end="1970-01-01T23:00:00Z", limit=1000
    )

    assert len(ex.fetch_calls) == 1
    requested_limit = ex.fetch_calls[0][1]
    assert requested_limit <= 30  # well under the 1000 default, close to the 24 needed


def test_exchange_without_ohlcv_support_raises(fake_exchange):
    ex = fake_exchange([])
    ex.has = {"fetchOHLCV": False}
    with pytest.raises(CryptoDLError, match="does not support fetchOHLCV"):
        download_ohlcv_with_exchange(ex, "BTC/USDT", "1h", start="2024-01-01")


def test_parse_datetime_utc_accepts_bare_date_and_z_suffix():
    d1 = parse_datetime_utc("2024-01-01")
    d2 = parse_datetime_utc("2024-01-01T12:00:00Z")
    assert d1.tzinfo is not None
    assert d2.hour == 12


def test_parse_datetime_utc_rejects_garbage():
    with pytest.raises(CryptoDLError, match="Could not parse"):
        parse_datetime_utc("not-a-date")
