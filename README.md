# cryptodl

A lean CLI for downloading historical crypto OHLCV (candle) data from public exchange
endpoints — no API keys required. Built on [ccxt](https://github.com/ccxt/ccxt)'s
unified exchange API, so it works across ~100 exchanges without any per-exchange code.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <this-repo>
cd crypto-data-dl
uv sync
```

This installs a `cryptodl` entry point inside the project's virtualenv. Run it with
`uv run cryptodl ...`, or activate the venv (`source .venv/bin/activate`) and run
`cryptodl ...` directly.

## Quick start

```bash
# 1. Find an exchange
uv run cryptodl list-exchanges

# 2. Find a symbol on that exchange
uv run cryptodl list-symbols --exchange binance --quote USDT

# 3. Find supported candle intervals
uv run cryptodl list-timeframes --exchange binance

# 4. Download
uv run cryptodl download \
  --exchange binance \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2024-01-01 \
  --end 2024-02-01 \
  --format csv \
  --output ./data
```

This writes `./data/binance_BTC-USDT_1h_20240101_20240201.csv` with columns
`timestamp,open,high,low,close,volume` — sorted, deduplicated, and trimmed exactly to
the requested range. `timestamp` is ISO 8601 UTC (e.g. `2024-01-01T00:00:00Z`).

## Commands

### `list-exchanges`

Lists every exchange that publicly supports OHLCV downloads (no API key needed).

```bash
uv run cryptodl list-exchanges
uv run cryptodl list-exchanges --json
```

### `list-symbols`

Lists markets available on an exchange, in `BASE/QUOTE` form (e.g. `BTC/USDT`).

```bash
uv run cryptodl list-symbols --exchange binance
uv run cryptodl list-symbols --exchange binance --quote USDT --json
```

### `list-timeframes`

Lists candle intervals supported by an exchange (e.g. `1m`, `1h`, `1d`).

```bash
uv run cryptodl list-timeframes --exchange binance
uv run cryptodl list-timeframes --exchange binance --json
```

### `download`

Downloads OHLCV candles for a symbol and time range.

```bash
uv run cryptodl download \
  --exchange binance \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2024-01-01 \
  --end 2024-02-01 \
  --format parquet \
  --output ./data \
  --json
```

| Flag | Required | Notes |
|---|---|---|
| `--exchange` | yes | Exchange id, e.g. `binance`. See `list-exchanges`. |
| `--symbol` | yes | `BASE/QUOTE` form, e.g. `BTC/USDT`. See `list-symbols`. |
| `--timeframe` | yes | e.g. `1h`. See `list-timeframes`. |
| `--start` | yes | ISO date or datetime, interpreted as UTC. |
| `--end` | no | ISO date or datetime, UTC. Defaults to now. |
| `--format` | no | `csv` (default) or `parquet`. |
| `--output` | no | Output directory. Defaults to `./data`. |
| `--json` | no | Print a single JSON summary to stdout instead of human-readable text. |

## Designed for both humans and LLM agents

Every command is fully non-interactive and supports `--json`, which prints exactly
one JSON object to stdout — progress and logs always go to stderr, so stdout stays
clean and parseable. Errors are actionable (e.g. "Symbol BTC/USD not found on
binance. Suggestions: BTC/USDT, BTC/USDC") and use a non-zero exit code; in `--json`
mode they're returned as a `{"error": ..., "suggestions": [...]}` object instead of a
traceback. See `CLAUDE.md` for the discovery-then-download workflow an agent should
follow.

## Development

```bash
uv sync              # install deps, including dev group
uv run pytest        # run the test suite (no network calls)
```

Core logic lives in plain functions in `src/cryptodl/{discovery,fetch,writers}.py`,
independent of the CLI — `cli.py` is a thin Typer layer over them, so other
interfaces (e.g. an MCP server) can reuse the same functions later.

## Out of scope (for now)

Caching, incremental updates, gap filling, resampling, multi-symbol batches, config
files, and trades/order book data.
