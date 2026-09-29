from __future__ import annotations

import json

from typer.testing import CliRunner

from cryptodl.cli import app

runner = CliRunner()


def test_download_unknown_exchange_json_error_exit_code():
    result = runner.invoke(
        app,
        [
            "download",
            "--exchange",
            "not-a-real-exchange",
            "--symbol",
            "BTC/USDT",
            "--timeframe",
            "1h",
            "--start",
            "2024-01-01",
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert "error" in payload
    assert "not-a-real-exchange" in payload["error"]


def test_download_unknown_exchange_human_error_goes_to_stderr():
    result = runner.invoke(
        app,
        [
            "download",
            "--exchange",
            "not-a-real-exchange",
            "--symbol",
            "BTC/USDT",
            "--timeframe",
            "1h",
            "--start",
            "2024-01-01",
        ],
    )

    assert result.exit_code == 1
    assert "Error:" in result.stdout or "Error:" in (result.stderr or "")


def test_download_bad_format_rejected_before_network():
    result = runner.invoke(
        app,
        [
            "download",
            "--exchange",
            "binance",
            "--symbol",
            "BTC/USDT",
            "--timeframe",
            "1h",
            "--start",
            "2024-01-01",
            "--format",
            "xlsx",
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert "xlsx" in payload["error"] or "Unknown format" in payload["error"]


def test_list_exchanges_json_is_single_object():
    result = runner.invoke(app, ["list-exchanges", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "exchanges" in payload
    assert "count" in payload
    assert payload["count"] == len(payload["exchanges"])
