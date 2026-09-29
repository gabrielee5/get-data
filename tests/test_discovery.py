from __future__ import annotations

import pytest

from cryptodl.discovery import (
    get_exchange_class,
    validate_symbol,
    validate_timeframe,
)
from cryptodl.errors import CryptoDLError


def test_get_exchange_class_unknown_id_suggests_close_matches():
    with pytest.raises(CryptoDLError) as excinfo:
        get_exchange_class("bnance")
    assert "bnance" in excinfo.value.message
    assert "binance" in excinfo.value.suggestions


def test_get_exchange_class_known_id_returns_class():
    klass = get_exchange_class("binance")
    assert klass.__name__.lower() == "binance"


def test_validate_symbol_unknown_suggests_close_matches(fake_exchange):
    ex = fake_exchange([])
    with pytest.raises(CryptoDLError) as excinfo:
        validate_symbol(ex, "BTC/USD")
    assert "BTC/USDT" in excinfo.value.suggestions


def test_validate_symbol_known_passes(fake_exchange):
    ex = fake_exchange([])
    validate_symbol(ex, "BTC/USDT")  # must not raise


def test_validate_timeframe_unknown_suggests_close_matches(fake_exchange):
    ex = fake_exchange([])
    with pytest.raises(CryptoDLError) as excinfo:
        validate_timeframe(ex, "1hh")
    assert "1h" in excinfo.value.suggestions


def test_validate_timeframe_known_passes(fake_exchange):
    ex = fake_exchange([])
    validate_timeframe(ex, "1h")  # must not raise
