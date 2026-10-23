"""H16: Kronos-small 24h forecast as a daily long/flat signal for BTC and ETH.

Rules are fixed in research/predictions/H16.md; do not tune them here.
Needs the Kronos repo and its own venv (torch):

    ~/Claude/Kronos/.venv/bin/python research/strategies/h16_kronos_signal.py forecast
    ~/Claude/Kronos/.venv/bin/python research/strategies/h16_kronos_signal.py evaluate [--fee 0.002]

`forecast` writes research/strategies/h16_forecasts.csv (one row per pair and day);
`evaluate` turns that file into the backtest, so fees can be varied without re-running the model.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
KRONOS = Path.home() / "Claude" / "Kronos"
DATA = ROOT / "user_data" / "data" / "binance"
OUT = Path(__file__).with_name("h16_forecasts.csv")
PAIRS = ["BTC", "ETH"]
START, END = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-10-22", tz="UTC")
LOOKBACK, PRED_LEN = 400, 6
THRESHOLD = 0.01
SEED = 42


def load(coin: str) -> pd.DataFrame:
    df = pd.read_feather(DATA / f"{coin}_USDT-4h.feather")
    df["amount"] = df["volume"] * df["close"]  # quote volume approximation
    return df.set_index("date")


def forecast() -> None:
    import torch

    sys.path.insert(0, str(KRONOS))
    from model import Kronos, KronosPredictor, KronosTokenizer

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    # from_pretrained leaves the modules in training mode, which turns attention dropout on
    tokenizer.eval()
    model.eval()
    predictor = KronosPredictor(model, tokenizer, device=device, max_context=512)

    data = {c: load(c) for c in PAIRS}
    rows = []
    for day in pd.date_range(START, END, freq="1D"):
        xs, xts, yts, meta = [], [], [], []
        for coin, df in data.items():
            # candles are indexed by open time; the last closed candle before `day` opened at day - 4h
            hist = df[df.index <= day - pd.Timedelta(hours=4)].tail(LOOKBACK)
            future = df[(df.index >= day) & (df.index < day + pd.Timedelta(hours=4 * PRED_LEN))]
            if len(hist) < LOOKBACK or len(future) < PRED_LEN:
                continue
            xs.append(hist[["open", "high", "low", "close", "volume", "amount"]].reset_index(drop=True))
            xts.append(pd.Series(hist.index.tz_localize(None)))
            yts.append(pd.Series(future.index.tz_localize(None)))
            meta.append((coin, hist["close"].iloc[-1], future["close"].iloc[-1]))
        if not xs:
            continue
        preds = predictor.predict_batch(
            df_list=xs, x_timestamp_list=xts, y_timestamp_list=yts,
            pred_len=PRED_LEN, T=1.0, top_p=0.9, sample_count=5, verbose=False,
        )
        for (coin, last_close, actual_close), pred in zip(meta, preds):
            rows.append({
                "date": day, "pair": coin, "last_close": last_close,
                "pred_close": float(pred["close"].iloc[-1]), "actual_close": actual_close,
            })
        print(day.date(), " ".join(f"{r['pair']} {r['pred_close'] / r['last_close'] - 1:+.3%}" for r in rows[-len(meta):]), flush=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"wrote {len(rows)} forecasts to {OUT}")


def run_pair(g: pd.DataFrame, long: np.ndarray, fee: float) -> float:
    equity, pos = 1.0, 0
    for want, ret in zip(long, g["actual_ret"].to_numpy()):
        if want != pos:
            equity *= 1 - fee
            pos = want
        if pos:
            equity *= 1 + ret
    if pos:
        equity *= 1 - fee
    return equity


def evaluate(fee: float) -> None:
    df = pd.read_csv(OUT, parse_dates=["date"])
    df["pred_ret"] = df["pred_close"] / df["last_close"] - 1
    df["actual_ret"] = df["actual_close"] / df["last_close"] - 1
    rng = np.random.default_rng(SEED)
    strat, hold, random_runs = 0.0, 0.0, np.zeros(1000)
    for coin, g in df.groupby("pair"):
        g = g.sort_values("date")
        long = (g["pred_ret"] > THRESHOLD).astype(int).to_numpy()
        hit = (np.sign(g["pred_ret"]) == np.sign(g["actual_ret"])).mean()
        corr = g["pred_ret"].corr(g["actual_ret"])
        eq = run_pair(g, long, fee)
        bh = (g["actual_close"].iloc[-1] / g["last_close"].iloc[0]) * (1 - fee) ** 2
        rand = np.array([run_pair(g, rng.permutation(long), fee) for _ in range(1000)])
        long_days = g["actual_ret"][long == 1]
        print(f"{coin}: days {len(g)}, long {long.sum()} ({long.mean():.0%}), hit rate {hit:.1%}, "
              f"corr {corr:+.3f}, avg next-24h return when long {long_days.mean():+.3%} vs all days {g['actual_ret'].mean():+.3%}")
        print(f"      strategy {eq - 1:+.2%}, buy-and-hold {bh - 1:+.2%}, random median {np.median(rand) - 1:+.2%}, "
              f"random 95th pct {np.percentile(rand, 95) - 1:+.2%}")
        strat += 500 * eq
        hold += 500 * bh
        random_runs += 500 * rand
    pct = (random_runs < strat).mean()
    print(f"\ncombined (1000 USDT, fee {fee:.2%} per side): strategy {strat:.1f} ({strat / 1000 - 1:+.2%}), "
          f"buy-and-hold {hold:.1f} ({hold / 1000 - 1:+.2%}), random median {np.median(random_runs):.1f}, "
          f"random 95th pct {np.percentile(random_runs, 95):.1f}; strategy beats {pct:.0%} of random runs")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["forecast", "evaluate"])
    ap.add_argument("--fee", type=float, default=0.002)
    args = ap.parse_args()
    forecast() if args.step == "forecast" else evaluate(args.fee)
