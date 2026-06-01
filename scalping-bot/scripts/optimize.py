#!/usr/bin/env python3
"""Run MANY test cases, find the 'best profit' config, then expose the catch.

This deliberately does two things:
  1. IN-SAMPLE optimization: sweep a big grid over the WHOLE dataset and pick the
     highest-profit parameters. These numbers look great. They are also a LIE -
     the strategy was tuned to this exact history (curve-fitting / overfitting).
  2. HONEST check: optimize on the first 70% of history, then trade the unseen
     last 30% with those locked parameters. This is what live trading really is.

The point: the prettiest backtest number is the most overfit one. Compare the
two columns and you can see the profit evaporate out-of-sample.

Usage:  python -m scripts.optimize
Output: reports/optimization_reality.xlsx
"""
import sys
from pathlib import Path
from itertools import product
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.data import load_symbol
from src.backtester import run_backtest
from src.report import metrics

START = config.ACCOUNT["start_balance"]
RISK = config.ACCOUNT["risk_per_trade"]

# Big-ish grids to give the optimizer lots of chances to "find profit".
GRIDS = {
    "breakout": {"channel": [10, 15, 20, 30, 40, 55], "atr_period": [14],
                 "session": [None], "sl_atr": [0.8, 1.0, 1.5, 2.0],
                 "tp_atr": [2.0, 3.0, 4.0, 6.0], "be_trigger_R": [1.0],
                 "trail_R": [0.8, 1.0, 1.5], "max_hold": [48]},
    "meanrev": {"lookback": [10, 20, 40, 60], "atr_period": [14],
                "entry_z": [1.0, 1.5, 2.0, 2.5, 3.0], "session": [None],
                "sl_atr": [0.8, 1.0, 1.5, 2.0], "tp_atr": [2.0, 3.0, 4.0],
                "be_trigger_R": [1.0], "trail_R": [1.0, 1.5], "max_hold": [48]},
}


def grid(g):
    keys = list(g)
    for combo in product(*(g[k] for k in keys)):
        yield dict(zip(keys, combo))


def evaluate(df, params, strat, start, active_after=None):
    trades, _ = run_backtest(df, params, _CFG, start, RISK, strat, active_after)
    return trades, metrics(trades, start)


def main():
    out_rows = []          # in-sample vs out-of-sample headline per symbol/strategy
    leaderboards = {}

    global _CFG
    for sym, base in config.SYMBOLS.items():
        _CFG = {**base, "name": sym}
        df = load_symbol(_CFG)
        split = int(len(df) * 0.70)
        in_df = df.iloc[:split]
        # out-of-sample frame keeps a warmup prefix; entries only after split date
        oos_start = df.iloc[split]["Date"]

        for strat, g in GRIDS.items():
            combos = list(grid(g))
            print(f"\n##### {sym} / {strat}: testing {len(combos)} cases #####")

            # 1) IN-SAMPLE optimize on FULL data (the 'best profit' the user wants)
            scored = []
            for p in combos:
                _, m = evaluate(df, p, strat, START)
                scored.append((m["final_balance_$"], m, p))
            scored.sort(key=lambda x: x[0], reverse=True)
            best_full = scored[0]
            leaderboards[f"{sym}_{strat}"] = scored[:10]
            print(f"  BEST in-sample (overfit): final=${best_full[0]:.2f} "
                  f"net=${best_full[1]['net_pnl_$']:+.2f} win={best_full[1]['win_rate_%']}% "
                  f"trades={best_full[1]['trades']}  params={best_full[2]}")

            # 2) HONEST: optimize on first 70%, trade the unseen last 30%
            scored_is = []
            for p in combos:
                _, m = evaluate(in_df, p, strat, START)
                scored_is.append((m["final_balance_$"], p))
            scored_is.sort(key=lambda x: x[0], reverse=True)
            best_is_params = scored_is[0][1]
            _, m_is = evaluate(in_df, best_is_params, strat, START)
            _, m_oos = evaluate(df, best_is_params, strat, START, active_after=oos_start)
            print(f"  HONEST  in-sample 70%: net=${m_is['net_pnl_$']:+.2f}  ->  "
                  f"unseen 30%: net=${m_oos['net_pnl_$']:+.2f} "
                  f"(win {m_oos['win_rate_%']}%, {m_oos['trades']} trades, "
                  f"{'RUINED' if m_oos['ruined'] else 'survived'})")

            out_rows.append({
                "symbol": sym, "strategy": strat,
                "overfit_full_net_$": best_full[1]["net_pnl_$"],
                "overfit_full_win_%": best_full[1]["win_rate_%"],
                "honest_in_sample_net_$": m_is["net_pnl_$"],
                "honest_unseen_net_$": m_oos["net_pnl_$"],
                "honest_unseen_win_%": m_oos["win_rate_%"],
                "honest_unseen_trades": m_oos["trades"],
            })

    table = pd.DataFrame(out_rows)
    print("\n" + "=" * 78)
    print("THE REALITY (net $ on a $500 account):")
    print(table.to_string(index=False))

    outp = Path(__file__).resolve().parent.parent / "reports" / "optimization_reality.xlsx"
    with pd.ExcelWriter(outp, engine="openpyxl") as xl:
        table.to_excel(xl, sheet_name="Overfit vs Honest", index=False)
        pd.DataFrame([
            ("overfit_full_net_$", "Best profit found by tuning on ALL the data. Looks great. NOT achievable live - it's curve-fit to the past."),
            ("honest_in_sample_net_$", "Profit on the 70% the optimizer was allowed to see."),
            ("honest_unseen_net_$", "Same params on the 30% it had NEVER seen. THIS is the realistic estimate of live performance."),
            ("The lesson", "The prettiest number (overfit) and the honest number (unseen) are very different. Anyone selling you the first one is selling a fantasy."),
        ], columns=["Column", "Meaning"]).to_excel(xl, sheet_name="READ ME", index=False)
        for key, lb in leaderboards.items():
            rows = [{**p, "final_$": round(fb, 2), "net_$": m["net_pnl_$"],
                     "win_%": m["win_rate_%"], "trades": m["trades"]} for fb, m, p in lb]
            pd.DataFrame(rows).to_excel(xl, sheet_name=f"{key[:25]} top10", index=False)
    print(f"\nWritten: {outp}")


if __name__ == "__main__":
    main()
