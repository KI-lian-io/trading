# freqtrade-bot (Binance spot)

freqtrade 2026.9, dry-run config in `user_data/config.json`.

## Setup on your server

```bash
uv venv --python 3.12 .venv
VIRTUAL_ENV=.venv uv pip install "freqtrade==2026.9"
cp .env.example .env   # fill in key/secret; keep withdrawals OFF on the Binance key
set -a; . ./.env; set +a
```

## Order of operations

1. Download data: `.venv/bin/freqtrade download-data -c user_data/config.json --timeframes 5m 1h --timerange 20250101-`
2. Backtest: `.venv/bin/freqtrade backtesting -c user_data/config.json --strategy SampleStrategy`
3. Dry run (paper, live prices) for 2–4 weeks: `.venv/bin/freqtrade trade -c user_data/config.json --strategy SampleStrategy`
4. Live: set `"dry_run": false` only after the dry run matches the backtest. Start with a small `stake_amount`.

## Dry run: ReinforcedAverageStrategy

`user_data/config_dryrun.json` paper-trades `ReinforcedAverageStrategy` (4h) on 12 USDT pairs with a 1000 USDT paper wallet, whole wallet in use (`stake_amount: unlimited`, 3 open trades).

```bash
cp .env.example .env   # fill in the FREQTRADE__API_SERVER__* values
.venv/bin/freqtrade install-ui
set -a && . ./.env && set +a && .venv/bin/freqtrade trade -c user_data/config_dryrun.json
```

FreqUI runs at http://127.0.0.1:8080 (log in with the username/password from `.env`). Trades are stored in `user_data/tradesv3.dryrun.sqlite`.

## Config notes

- Stake currency is USDC, not USDT (EEA accounts lost USDT spot pairs under MiCA). Check which quote currency your account can trade.
- API keys are read from `FREQTRADE__EXCHANGE__KEY` / `FREQTRADE__EXCHANGE__SECRET`, not stored in the config.
- `SampleStrategy` is a template, not a proven strategy.
