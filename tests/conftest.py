"""Shared fixtures: a duck-typed fake exchange that mimics ccxt's public surface."""

from __future__ import annotations

import ccxt
import pytest


class FakeExchange:
    """Minimal stand-in for a ccxt exchange instance, backed by an in-memory candle list.

    `batches` lets a test script exactly what fetch_ohlcv should return on each call,
    which is how we exercise pagination edge cases (empty tail, stuck `since`, etc.)
    without ever touching the network.
    """

    id = "fake"
    name = "Fake Exchange"

    def __init__(self, candles: list[list] | None = None, timeframe: str = "1h"):
        self.has = {"fetchOHLCV": True}
        self.timeframes = {"1m": "1m", "1h": "1h", "1d": "1d"}
        self._markets = {
            "BTC/USDT": {"base": "BTC", "quote": "USDT", "active": True},
            "ETH/USDT": {"base": "ETH", "quote": "USDT", "active": True},
            "ETH/BTC": {"base": "ETH", "quote": "BTC", "active": True},
        }
        self._candles = candles or []
        self._timeframe_ms = ccxt.Exchange.parse_timeframe(timeframe) * 1000
        self.fetch_calls: list[tuple[int, int]] = []  # (since, limit)

    def load_markets(self):
        return self._markets

    def parse_timeframe(self, timeframe: str) -> int:
        return ccxt.Exchange.parse_timeframe(timeframe)

    def fetch_ohlcv(self, symbol, timeframe="1m", since=None, limit=None, params=None):
        self.fetch_calls.append((since, limit))
        batch = [c for c in self._candles if c[0] >= since]
        return batch[:limit]


@pytest.fixture
def make_candles():
    def _make(start_ms: int, count: int, step_ms: int = 3_600_000, price: float = 100.0):
        return [
            [start_ms + i * step_ms, price, price + 1, price - 1, price + 0.5, 10.0 + i]
            for i in range(count)
        ]

    return _make


@pytest.fixture
def fake_exchange():
    return FakeExchange
