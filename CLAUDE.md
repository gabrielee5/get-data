# cryptodl — agent usage guide

CLI for downloading historical crypto OHLCV (candle) data from public exchange
endpoints. No API keys, fully non-interactive, safe to call in a loop.

Run it as `uv run cryptodl <command> ...` from this directory (or `cryptodl ...` if
the venv is active).

## Workflow: discover, then download

Don't guess exchange ids, symbols, or timeframes — they vary per exchange and a
guess will fail. Always discover first:

```bash
uv run cryptodl list-exchanges --json          # find an exchange id
uv run cryptodl list-symbols --exchange binance --quote USDT --json   # find a symbol
uv run cryptodl list-timeframes --exchange binance --json             # find a timeframe
uv run cryptodl download --exchange binance --symbol BTC/USDT --timeframe 1h \
  --start 2024-01-01 --end 2024-02-01 --format csv --output ./data --json
```

If a `download` call fails because the symbol/timeframe/exchange was wrong, the JSON
error includes `suggestions` — retry with one of those rather than re-listing
everything.

## Always pass `--json`

Every command supports `--json`. With it, **stdout contains exactly one JSON object**
and nothing else — parse it directly, don't scrape human-readable text. Progress bars
and log lines always go to stderr, in both modes, so stdout is safe to pipe into
`jq` or a JSON parser even without `--json` filtering noise (though `--json` is still
the reliable contract for machine parsing).

On success, `download --json` prints:

```json
{
  "file": "data/binance_BTC-USDT_1h_20240101_20240201.csv",
  "row_count": 744,
  "actual_first_timestamp": "2024-01-01T00:00:00Z",
  "actual_last_timestamp": "2024-01-31T23:00:00Z",
  "requested_start": "2024-01-01T00:00:00Z",
  "requested_end": "2024-02-01T00:00:00Z"
}
```

- `file` — path to the written CSV/Parquet file.
- `row_count` — number of candles actually written.
- `actual_first_timestamp` / `actual_last_timestamp` — the real range of data
  returned by the exchange, which may be narrower than requested (e.g. if the
  market didn't exist yet at `requested_start`, or `requested_end` is in the future).
- `requested_start` / `requested_end` — normalized (UTC, ISO 8601) echo of what
  you asked for, so you can diff it against the actual range.

On failure, exit code is non-zero and stdout is a single JSON error object instead:

```json
{"error": "Symbol 'BTC/USD' not found on binance.", "suggestions": ["BTC/USDT", "BTC/USDC"]}
```

Check the exit code (or the presence of an `"error"` key) before assuming success.

## Symbol format

Always `BASE/QUOTE`, e.g. `BTC/USDT`, `ETH/BTC` — matching ccxt's unified market
symbols exactly as returned by `list-symbols`. Not `BTCUSDT`, not `BTC-USDT`.

## Date format

`--start` and `--end` accept an ISO date (`2024-01-01`) or datetime
(`2024-01-01T12:00:00`), always interpreted as UTC regardless of local timezone.
`--end` defaults to now (UTC) if omitted.

## Output

CSV or Parquet (`--format`), written to `--output` (default `./data`) with an
auto-generated filename: `<exchange>_<BASE-QUOTE>_<timeframe>_<start>_<end>.<ext>`,
e.g. `binance_BTC-USDT_1h_20240101_20240201.csv`. Columns are always
`timestamp,open,high,low,close,volume`, sorted ascending, deduplicated, and trimmed
exactly to `[start, end]`. `timestamp` is ISO 8601 UTC (`2024-01-01T00:00:00Z`).

## Things to know

- A market can exist under a symbol you don't expect (e.g. `BTC/USD` may be a
  futures/delivery contract distinct from `BTC/USDT`) — if a symbol resolves but the
  returned data looks odd (very short actual range, unexpected prices), double check
  it's the spot market you meant via `list-symbols`.
- Large ranges paginate automatically and show progress on stderr; this can take a
  while for long ranges on fine-grained timeframes (e.g. years of `1m` data) — don't
  assume a hang, let it run.
- Nothing here caches results — repeated identical calls re-download from the
  exchange.
