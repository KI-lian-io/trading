"""H14: delta-neutral funding-rate carry backtest (spot long + USDT-M perp short).

Rules are fixed in research/predictions/H14.md; do not tune them here.

Usage:
    .venv/bin/python research/strategies/h14_funding_carry.py [--fee-mult 2] [--version A|B]
"""

import argparse
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "user_data" / "data" / "binance"
PAIRS = "BTC ETH SOL XRP ADA DOGE LINK AVAX LTC DOT TRX ATOM".split()
START, END = pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2026-10-14 18:00", tz="UTC")
CAPITAL = 1000.0
LEVERAGE = 2.0
CAPITAL_PER_NOTIONAL = 1 + 1 / LEVERAGE  # spot leg + short margin
REBALANCE_UP = 0.40
ENTER_ABOVE, EXIT_BELOW, LOOKBACK = 0.0001, 0.0, 9
SPOT_FEE, PERP_FEE = 0.001, 0.0005  # Binance base taker, per side


def load(coin: str) -> tuple[pd.DataFrame, pd.Series]:
    spot = pd.read_feather(DATA / f"{coin}_USDT-1h.feather").set_index("date")
    perp = pd.read_feather(DATA / "futures" / f"{coin}_USDT_USDT-1h-futures.feather").set_index("date")
    mark = pd.read_feather(DATA / "futures" / f"{coin}_USDT_USDT-1h-mark.feather").set_index("date")
    fund = pd.read_feather(DATA / "futures" / f"{coin}_USDT_USDT-1h-funding_rate.feather").set_index("date")
    idx = pd.date_range(START, END, freq="1h")
    px = pd.DataFrame({
        "s_open": spot["open"], "s_close": spot["close"],
        "f_open": perp["open"], "f_close": perp["close"],
        "m_open": mark["open"],
    }).reindex(idx).ffill()
    rates = fund["funding_rate"]
    rates = rates[(rates.index >= START) & (rates.index <= END)]
    return px, rates


def run_sleeve(px: pd.DataFrame, rates: pd.Series, capital: float, version: str, fee_mult: float) -> dict:
    fs, ff = SPOT_FEE * fee_mult, PERP_FEE * fee_mult
    cash, q, f_entry = capital, 0.0, 0.0
    fees = funding = 0.0
    rebalances = trades = hours_in = 0
    equity = []
    rate_at = rates.to_dict()
    history: list[float] = []

    def value(s, f):
        return cash + q * s + q * (f_entry - f)

    def enter(s, f):
        nonlocal cash, q, f_entry, fees, trades
        notional = value(s, f) / CAPITAL_PER_NOTIONAL
        q = notional / s
        cost = q * s * fs + q * f * ff
        cash -= q * s + cost
        f_entry, fees, trades = f, fees + cost, trades + 1

    def leave(s, f):
        nonlocal cash, q, fees
        cost = q * s * fs + q * f * ff
        cash += q * s + q * (f_entry - f) - cost
        fees, q = fees + cost, 0.0

    for i, (ts, row) in enumerate(px.iterrows()):
        if ts in rate_at:
            rate = rate_at[ts]
            if q:
                pay = q * row.m_open * rate
                cash, funding = cash + pay, funding + pay
            history.append(rate)
            mean = sum(history[-LOOKBACK:]) / min(len(history), LOOKBACK)
            if version == "B":
                if not q and len(history) >= LOOKBACK and mean > ENTER_ABOVE:
                    enter(row.s_open, row.f_open)
                elif q and mean < EXIT_BELOW:
                    leave(row.s_open, row.f_open)
        if version == "A" and i == 0:
            enter(row.s_open, row.f_open)
        if q and row.f_close >= f_entry * (1 + REBALANCE_UP):
            leave(row.s_close, row.f_close)
            enter(row.s_close, row.f_close)
            rebalances += 1
        hours_in += bool(q)
        equity.append(value(row.s_close, row.f_close))
    if q:
        last = px.iloc[-1]
        leave(last.s_close, last.f_close)
        equity[-1] = cash
    return {
        "equity": pd.Series(equity, index=px.index),
        "fees": fees, "funding": funding, "rebalances": rebalances,
        "entries": trades, "time_in_market": hours_in / len(px),
    }


def annualized(eq: pd.Series, start: str, end: str | None = None) -> float:
    part = eq[start:end] if end else eq[start:]
    years = (part.index[-1] - part.index[0]).total_seconds() / (365.25 * 86400)
    return (part.iloc[-1] / part.iloc[0]) ** (1 / years) - 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fee-mult", type=float, default=2.0)
    ap.add_argument("--version", choices=["A", "B"], default="A")
    args = ap.parse_args()

    sleeves, rows = [], []
    for coin in PAIRS:
        px, rates = load(coin)
        r = run_sleeve(px, rates, CAPITAL / len(PAIRS), args.version, args.fee_mult)
        sleeves.append(r["equity"])
        rows.append({
            "pair": coin,
            "return_pct": 100 * (r["equity"].iloc[-1] / r["equity"].iloc[0] - 1),
            "funding": r["funding"], "fees": r["fees"],
            "rebalances": r["rebalances"], "entries": r["entries"],
            "in_market_pct": 100 * r["time_in_market"],
        })
    eq = pd.concat(sleeves, axis=1).sum(axis=1)
    dd = (eq / eq.cummax() - 1).min()
    table = pd.DataFrame(rows).set_index("pair")
    print(table.round(2).to_string())
    print()
    print(f"version {args.version}, fee x{args.fee_mult:g}")
    print(f"final equity      {eq.iloc[-1]:.2f} USDT from {CAPITAL:.0f}")
    print(f"total return      {100 * (eq.iloc[-1] / CAPITAL - 1):.2f}%")
    print(f"annual 2023-26    {100 * annualized(eq, '2023-01-01'):.2f}%")
    print(f"annual 2023-24    {100 * annualized(eq, '2023-01-01', '2024-12-31'):.2f}%")
    print(f"annual 2025-26    {100 * annualized(eq, '2025-01-01'):.2f}%")
    print(f"max drawdown      {100 * -dd:.2f}%")
    print(f"funding received  {table.funding.sum():.2f} USDT")
    print(f"fees paid         {table.fees.sum():.2f} USDT")
    print(f"rebalances        {int(table.rebalances.sum())}")
    print(f"avg time in mkt   {table.in_market_pct.mean():.1f}%")
    by_year = eq.resample("YE").last()
    by_year = pd.concat([pd.Series([CAPITAL], index=[eq.index[0]]), by_year])
    print("year returns      " + ", ".join(
        f"{d.year}: {100 * (v / p - 1):.2f}%" for d, p, v in zip(by_year.index[1:], by_year.values[:-1], by_year.values[1:])
    ))


if __name__ == "__main__":
    main()
