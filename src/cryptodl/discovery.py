"""Exchange / symbol / timeframe discovery. No CLI or I/O concerns here."""

from __future__ import annotations

import difflib

import ccxt

from cryptodl.errors import CryptoDLError


def get_exchange_class(exchange_id: str):
    """Look up a ccxt exchange class by id, raising a helpful error if unknown."""
    if exchange_id not in ccxt.exchanges:
        close = difflib.get_close_matches(exchange_id, ccxt.exchanges, n=5)
        raise CryptoDLError(
            f"Exchange '{exchange_id}' not found.",
            suggestions=close,
        )
    return getattr(ccxt, exchange_id)


def get_exchange(exchange_id: str, enable_rate_limit: bool = True) -> ccxt.Exchange:
    """Instantiate a ccxt exchange, validating it exists and supports fetchOHLCV."""
    klass = get_exchange_class(exchange_id)
    exchange = klass({"enableRateLimit": enable_rate_limit})
    if not exchange.has.get("fetchOHLCV"):
        supported = list_exchanges()
        close = difflib.get_close_matches(
            exchange_id, [e["id"] for e in supported], n=5
        )
        raise CryptoDLError(
            f"Exchange '{exchange_id}' does not support fetchOHLCV.",
            suggestions=close,
        )
    return exchange


def list_exchanges() -> list[dict]:
    """List every ccxt exchange that publicly supports fetchOHLCV."""
    result = []
    for exchange_id in ccxt.exchanges:
        klass = getattr(ccxt, exchange_id)
        try:
            instance = klass()
        except Exception:
            continue
        if instance.has.get("fetchOHLCV"):
            result.append({"id": exchange_id, "name": instance.name})
    return result


def list_symbols(exchange_id: str, quote: str | None = None) -> list[dict]:
    """List markets available on an exchange, optionally filtered by quote asset."""
    exchange = get_exchange(exchange_id)
    markets = exchange.load_markets()
    result = []
    for symbol, market in markets.items():
        if not market.get("active", True):
            continue
        if quote is not None and market.get("quote", "").upper() != quote.upper():
            continue
        result.append(
            {
                "symbol": symbol,
                "base": market.get("base"),
                "quote": market.get("quote"),
            }
        )
    result.sort(key=lambda m: m["symbol"])
    return result


def list_timeframes(exchange_id: str) -> list[str]:
    """List timeframe strings (e.g. '1m', '1h', '1d') supported by an exchange."""
    exchange = get_exchange(exchange_id)
    if not exchange.timeframes:
        raise CryptoDLError(
            f"Exchange '{exchange_id}' does not expose a list of timeframes."
        )
    return list(exchange.timeframes.keys())


def validate_symbol(exchange: ccxt.Exchange, symbol: str) -> None:
    markets = exchange.load_markets()
    if symbol not in markets:
        close = difflib.get_close_matches(symbol, list(markets.keys()), n=5)
        raise CryptoDLError(
            f"Symbol '{symbol}' not found on {exchange.id}.",
            suggestions=close,
        )


def validate_timeframe(exchange: ccxt.Exchange, timeframe: str) -> None:
    if exchange.timeframes and timeframe not in exchange.timeframes:
        close = difflib.get_close_matches(timeframe, list(exchange.timeframes.keys()), n=5)
        raise CryptoDLError(
            f"Timeframe '{timeframe}' not supported on {exchange.id}.",
            suggestions=close,
        )
