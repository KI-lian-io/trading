"""Append freqtrade backtest results to research/runs.csv.

Usage:
    .venv/bin/python research/parse_backtest.py --hypothesis H07 [--label C1] [--period test] LOG [LOG ...]

Each LOG is the text output of `freqtrade backtesting` (one strategy per file).
Label defaults to the file name, period is inferred from the backtest dates
(train = ends by 2025-01-02, test = starts 2024-12-31 or later, otherwise full).
"""

import argparse
import csv
import re
from datetime import date
from pathlib import Path

RUNS = Path(__file__).with_name("runs.csv")
FIELDS = [
    "hypothesis", "label", "period", "strategy", "mode", "start", "end",
    "trades", "trades_per_day", "profit_pct", "cagr_pct", "max_dd_pct",
    "profit_factor", "win_pct", "market_change_pct", "tested_on", "source_file",
]


def metric(text: str, name: str) -> str:
    m = re.search(r"│ " + re.escape(name) + r"\s*│\s*(.*?)\s*│", text)
    return m.group(1) if m else ""


def number(value: str) -> str:
    m = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return m.group(0) if m else ""


def infer_period(start: str, end: str) -> str:
    if not start or not end:
        return ""
    if end[:10] <= "2025-01-02":
        return "train"
    if start[:10] >= "2024-12-31":
        return "test"
    return "full"


def parse(path: Path) -> dict | None:
    text = path.read_text(errors="ignore")
    if "Total profit %" not in text:
        return None
    strategy = re.search(r"Result for strategy (\S+)", text)
    start, end = metric(text, "Backtesting from"), metric(text, "Backtesting to")
    trades = metric(text, "Total/Daily Avg Trades").split("/")
    # Win% is the last number in the strategy's row of the STRATEGY SUMMARY table
    win = ""
    summary = text.split("STRATEGY SUMMARY")[-1]
    row = re.search(r"│\s*" + re.escape(strategy.group(1)) + r"\s*│(.*)", summary) if strategy else None
    if row:
        cells = [c.strip() for c in row.group(1).split("│")]
        wdl = next((c for c in cells if re.fullmatch(r"\d+\s+\d+\s+\d+\s+[\d.]+", c)), "")
        win = wdl.split()[-1] if wdl else ""
    return {
        "strategy": strategy.group(1) if strategy else "",
        "mode": metric(text, "Trading Mode"),
        "start": start,
        "end": end,
        "trades": number(trades[0]) if trades[0] else "",
        "trades_per_day": number(trades[1]) if len(trades) > 1 else "",
        "profit_pct": number(metric(text, "Total profit %")),
        "cagr_pct": number(metric(text, "CAGR %")),
        "max_dd_pct": number(metric(text, "Max % of account underwater")),
        "profit_factor": number(metric(text, "Profit factor")),
        "win_pct": win,
        "market_change_pct": number(metric(text, "Market change")),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hypothesis", required=True)
    ap.add_argument("--label")
    ap.add_argument("--period", choices=["train", "test", "full", "forward"])
    ap.add_argument("--tested-on", default=date.today().isoformat())
    ap.add_argument("logs", nargs="+", type=Path)
    args = ap.parse_args()

    new_file = not RUNS.exists()
    with RUNS.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for log in args.logs:
            row = parse(log)
            if row is None:
                print(f"skipped (no results): {log}")
                continue
            row.update(
                hypothesis=args.hypothesis,
                label=args.label or log.stem,
                period=args.period or infer_period(row["start"], row["end"]),
                tested_on=args.tested_on,
                source_file=log.name,
            )
            writer.writerow(row)


if __name__ == "__main__":
    main()
