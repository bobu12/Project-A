#!/usr/bin/env python3
"""Deliver an 80%+ win rate - and show what it actually costs.

You can manufacture almost any win rate by changing ONE thing: the ratio of
take-profit to stop-loss. Tiny TP + wide SL => most trades hit the small TP =>
huge win rate. But the occasional big loss eats all the small wins.

This script sweeps that ratio and prints win% NEXT TO net profit and profit
factor, so the trade-off is impossible to miss.

Research backing (win rate is the wrong target; profit factor is what matters):
  tradezella.com/blog/win-rate, tradeciety.com win-rate myth,
  backtestbase.com win-rate-vs-profit-factor.

Usage:  python -m scripts.win_rate_demo
Output: reports/win_rate_demo.xlsx
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.data import load_symbol
from src.backtester import run_backtest
from src.report import metrics

START = config.ACCOUNT["start_balance"]
RISK = config.ACCOUNT["risk_per_trade"]

# Walk TP from tiny -> large while keeping a WIDE stop. Disable breakeven/trail
# (be_trigger high, trail high) so the structure stays "small win vs big loss".
TP_SL_CASES = [
    # label,           tp_atr, sl_atr
    ("tiny TP / wide SL", 0.25, 4.0),
    ("small TP",          0.5,  4.0),
    ("0.75 TP",           0.75, 3.0),
    ("1:1-ish",           1.5,  1.5),
    ("let winners run",   4.0,  1.0),
]


def main():
    rows = []
    for sym, base in config.SYMBOLS.items():
        cfg = {**base, "name": sym}
        df = load_symbol(cfg)
        print(f"\n##### {sym} ({cfg['timeframe']}) #####")
        for label, tp, sl in TP_SL_CASES:
            params = {"channel": 20, "atr_period": 14, "session": None,
                      "sl_atr": sl, "tp_atr": tp, "be_trigger_R": 99.0,
                      "trail_R": 99.0, "max_hold": 48}
            trades, _ = run_backtest(df, params, cfg, START, RISK, "breakout")
            m = metrics(trades, START)
            rows.append({"symbol": sym, "setup": label, "TP/SL": f"{tp}/{sl}",
                         "win_%": m["win_rate_%"], "trades": m["trades"],
                         "profit_factor": m["profit_factor"],
                         "net_$": m["net_pnl_$"], "final_$": m["final_balance_$"],
                         "ruined": m["ruined"]})
            print(f"  {label:18s} TP/SL={tp}/{sl}  WIN={m['win_rate_%']:5.1f}%  "
                  f"PF={m['profit_factor']:.2f}  net=${m['net_pnl_$']:+8.2f}  "
                  f"{'RUINED' if m['ruined'] else ''}")

    table = pd.DataFrame(rows)
    print("\n" + "=" * 72)
    print("Notice: the HIGHEST win% rows are NOT the most profitable rows.")
    hi = table.loc[table["win_%"].idxmax()]
    print(f"Highest win rate: {hi['win_%']}% on {hi['symbol']} "
          f"-> net ${hi['net_$']} (PF {hi['profit_factor']})")

    outp = Path(__file__).resolve().parent.parent / "reports" / "win_rate_demo.xlsx"
    with pd.ExcelWriter(outp, engine="openpyxl") as xl:
        table.to_excel(xl, sheet_name="Win% vs Profit", index=False)
        pd.DataFrame([
            ("The trick", "Tiny take-profit + wide stop = most trades are small wins = high win %."),
            ("The cost", "The rare loss is huge relative to the wins, so net profit and profit factor FALL as win% rises."),
            ("What matters", "Profit Factor (>1 = makes money) and Net P/L. Win rate alone is meaningless."),
            ("Pro reality", "Many professionals win ~40-50% of trades and are highly profitable because winners > losers (research: tradezella, tradeciety, backtestbase)."),
        ], columns=["Point", "Detail"]).to_excel(xl, sheet_name="READ ME", index=False)
    print(f"\nWritten: {outp}")


if __name__ == "__main__":
    main()
