# Research ledger

Every trading idea we test goes here, including (especially) the ones that failed, so we never re-test a dead idea by accident.

- `hypotheses.csv`: one row per idea: what it was, where it came from, how many variations were tried, results, status, lessons.
- `runs.csv`: one row per backtest run, parsed from freqtrade output. `hypothesis` links to `hypotheses.csv`.
- `parse_backtest.py`: appends new backtest results to `runs.csv`.

Status values: `untested`, `failed`, `passed backtest only`, `paper trading`, `paused`, `retired`.

## Before testing a new idea

1. Search `hypotheses.csv` for the idea and its family. If it failed, only re-test when market conditions clearly changed, and say why in the new row.
2. Add a row with status `untested` and write the prediction first: expected profit, max drawdown, win rate, and what result counts as failure. Do not edit it after the test.
3. Test, then append the runs:

   ```bash
   .venv/bin/freqtrade backtesting ... > /tmp/run.txt
   .venv/bin/python research/parse_backtest.py --hypothesis H16 /tmp/run.txt
   ```

4. Fill in the results, `variations_tried`, status and lessons.

## Rules

- **Periods:** TRAIN = 2023-01-01 to 2025-01-01 (market up ~375%), TEST = 2025-01-01 to 2026-10-14 (market down ~45%).
- **TEST is used up.** On 2026-10-14 alone it was checked against 100+ variants, so it is no longer a sealed test. The only clean data left is forward data after 2026-10-14: paper trading (`user_data/config_dryrun.json`) or a backtest of that period once enough of it exists.
- **Count every variation.** More attempts mean a higher bar; a good result after many tries is more likely luck.
- **Cap rewrites at 3 to 5 per idea.** An idea that needs more has answered the question.
- **Stress before trusting:** 2x fees, worst periods, more pairs, and `freqtrade lookahead-analysis`.
- **Paper first.** A strategy only goes near real money after weeks of dry-run that match its backtest.

## Summary as of 2026-10-14

187 backtest runs across 11 tested ideas. Only ReinforcedAverageStrategy (4h, long-only) stayed positive out of sample, and only slightly; it is in dry-run. Every intraday long/short idea (H07-H10) lost money on both periods, mostly to fees and whipsaw. Leverage above 2x destroyed accounts (H06).
