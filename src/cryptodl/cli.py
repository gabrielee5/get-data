"""Thin Typer CLI over cryptodl's core modules (discovery, fetch, writers).

Fully non-interactive. Every command supports --json for machine-readable output;
without it, progress and logs still go to stderr so stdout stays parseable either way.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from cryptodl import discovery, fetch, writers
from cryptodl.errors import CryptoDLError

app = typer.Typer(
    name="cryptodl",
    help=(
        "Download historical crypto OHLCV (candle) data from public exchange "
        "endpoints. No API keys required.\n\n"
        "Typical workflow: list-exchanges -> list-symbols -> list-timeframes -> download."
    ),
    no_args_is_help=True,
    add_completion=False,
)


def _print_json(obj) -> None:
    typer.echo(json.dumps(obj, indent=2))


def _fail(exc: CryptoDLError, as_json: bool) -> None:
    if as_json:
        _print_json(exc.to_dict())
    else:
        typer.echo(f"Error: {exc.message}", err=True)
        if exc.suggestions:
            typer.echo(f"Suggestions: {', '.join(exc.suggestions)}", err=True)
    raise typer.Exit(code=1)


def _as_error(exc: Exception) -> CryptoDLError:
    return exc if isinstance(exc, CryptoDLError) else CryptoDLError(str(exc))


@app.command("list-exchanges")
def list_exchanges_cmd(
    json_output: bool = typer.Option(
        False, "--json", help="Print a single JSON object to stdout instead of a table."
    ),
) -> None:
    """List every exchange that supports public OHLCV downloads.

    Examples:

        cryptodl list-exchanges

        cryptodl list-exchanges --json
    """
    try:
        exchanges = discovery.list_exchanges()
    except Exception as exc:
        _fail(_as_error(exc), json_output)
        return

    if json_output:
        _print_json({"exchanges": exchanges, "count": len(exchanges)})
    else:
        for ex in exchanges:
            typer.echo(f"{ex['id']:<20} {ex['name']}")


@app.command("list-symbols")
def list_symbols_cmd(
    exchange: str = typer.Option(..., "--exchange", help="Exchange id, e.g. binance."),
    quote: Optional[str] = typer.Option(
        None, "--quote", help="Filter to markets quoted in this asset, e.g. USDT."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print a single JSON object to stdout instead of a table."
    ),
) -> None:
    """List markets (symbols) available on an exchange, in BASE/QUOTE form.

    Examples:

        cryptodl list-symbols --exchange binance

        cryptodl list-symbols --exchange binance --quote USDT --json
    """
    try:
        symbols = discovery.list_symbols(exchange, quote=quote)
    except Exception as exc:
        _fail(_as_error(exc), json_output)
        return

    if json_output:
        _print_json({"exchange": exchange, "symbols": symbols, "count": len(symbols)})
    else:
        for s in symbols:
            typer.echo(s["symbol"])


@app.command("list-timeframes")
def list_timeframes_cmd(
    exchange: str = typer.Option(..., "--exchange", help="Exchange id, e.g. binance."),
    json_output: bool = typer.Option(
        False, "--json", help="Print a single JSON object to stdout instead of a table."
    ),
) -> None:
    """List timeframes (candle intervals) supported by an exchange, e.g. 1m, 1h, 1d.

    Examples:

        cryptodl list-timeframes --exchange binance

        cryptodl list-timeframes --exchange binance --json
    """
    try:
        timeframes = discovery.list_timeframes(exchange)
    except Exception as exc:
        _fail(_as_error(exc), json_output)
        return

    if json_output:
        _print_json({"exchange": exchange, "timeframes": timeframes})
    else:
        for tf in timeframes:
            typer.echo(tf)


@app.command("download")
def download_cmd(
    exchange: str = typer.Option(..., "--exchange", help="Exchange id, e.g. binance."),
    symbol: str = typer.Option(
        ..., "--symbol", help="Market symbol in BASE/QUOTE form, e.g. BTC/USDT."
    ),
    timeframe: str = typer.Option(..., "--timeframe", help="Candle interval, e.g. 1h."),
    start: str = typer.Option(
        ..., "--start", help="Start of range, ISO date or datetime, interpreted as UTC."
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        help="End of range, ISO date or datetime, interpreted as UTC. Defaults to now.",
    ),
    fmt: str = typer.Option("csv", "--format", help="Output format: csv or parquet."),
    output: Path = typer.Option(Path("./data"), "--output", help="Output directory."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print a single JSON summary object to stdout instead of human-readable text.",
    ),
) -> None:
    """Download OHLCV candles for a symbol and time range, and write CSV or Parquet.

    Output columns: timestamp (ISO 8601 UTC), open, high, low, close, volume.
    Rows are sorted, deduplicated, and trimmed exactly to the requested start/end range.

    Examples:

        cryptodl download --exchange binance --symbol BTC/USDT --timeframe 1h \\
            --start 2024-01-01 --end 2024-02-01

        cryptodl download --exchange binance --symbol BTC/USDT --timeframe 1h \\
            --start 2024-01-01 --format parquet --output ./data --json
    """
    if fmt not in writers.VALID_FORMATS:
        _fail(
            CryptoDLError(
                f"Unknown format '{fmt}'.", suggestions=list(writers.VALID_FORMATS)
            ),
            json_output,
        )
        return

    def on_progress(current_ts_ms: int, start_ms: int, end_ms: int, count: int) -> None:
        span = max(end_ms - start_ms, 1)
        pct = min(100, int((current_ts_ms - start_ms) / span * 100))
        current_iso = datetime.fromtimestamp(current_ts_ms / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        typer.echo(
            f"\rFetching... {pct:3d}% ({count} candles, at {current_iso})",
            err=True,
            nl=False,
        )

    try:
        df = fetch.download_ohlcv(exchange, symbol, timeframe, start, end, on_progress=on_progress)
    except Exception as exc:
        typer.echo("", err=True)
        _fail(_as_error(exc), json_output)
        return

    typer.echo("", err=True)

    start_dt = fetch.parse_datetime_utc(start, "start")
    end_dt = fetch.parse_datetime_utc(end, "end") if end is not None else datetime.now(timezone.utc)

    filename = writers.build_filename(exchange, symbol, timeframe, start_dt, end_dt, fmt)
    output_path = output / filename

    try:
        writers.write(df, output_path, fmt)
    except Exception as exc:
        _fail(_as_error(exc), json_output)
        return

    summary = {
        "file": str(output_path),
        "row_count": len(df),
        "actual_first_timestamp": df["timestamp"].iloc[0] if not df.empty else None,
        "actual_last_timestamp": df["timestamp"].iloc[-1] if not df.empty else None,
        "requested_start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "requested_end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if json_output:
        _print_json(summary)
    else:
        typer.echo(f"Wrote {summary['row_count']} rows to {summary['file']}")
        typer.echo(f"Range: {summary['actual_first_timestamp']} to {summary['actual_last_timestamp']}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
