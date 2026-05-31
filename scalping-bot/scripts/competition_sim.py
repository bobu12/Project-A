#!/usr/bin/env python3
"""Run the competition Monte-Carlo on the real backtested trade distribution.

Usage:  python -m scripts.competition_sim
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.data import load_symbol
from src.backtester import walk_forward
from src.competition_sim import r_multiples, sweep

N_TRADES = 200   # representative competition length; results scale with this


def main():
    start = config.ACCOUNT["start_balance"]
    risk = config.ACCOUNT["risk_per_trade"]
    all_tables = {}

    for sym, cfg in config.SYMBOLS.items():
        cfg = {**cfg, "name": sym}
        df = load_symbol(cfg)
        trades, _, _ = walk_forward(df, cfg, config.PARAM_GRID,
                                    config.WALK_FORWARD[sym], start, risk)
        R = r_multiples(trades)
        if len(R) < 10:
            print(f"\n{sym}: only {len(R)} trades, skipping."); continue

        edge = R.mean()
        print(f"\n=== {sym} ===  trades={len(R)}  "
              f"mean R (edge)={edge:+.3f}  win%={100*(R>0).mean():.1f}")
        if edge <= 0:
            print("  >> NEGATIVE edge: no risk level makes this profitable on average.")
        table = sweep(R, N_TRADES)
        df_t = pd.DataFrame(table)
        print(df_t.to_string(index=False))
        all_tables[sym] = (edge, len(R), df_t)

    # also: what EDGE would be needed to make 18x realistic at a sane risk?
    print("\n=== What edge would you need? (synthetic, fixed 2:1 R, risk=10%/trade, 200 trades) ===")
    rows = []
    for win in [0.45, 0.50, 0.55, 0.60, 0.70]:
        # 2:1 payoff: win -> +2R, loss -> -1R
        synth = np.array([2.0] * int(win * 1000) + [-1.0] * int((1 - win) * 1000))
        res = sweep(synth, N_TRADES, f_grid=[0.10])[0]
        rows.append({"win_rate_%": int(win * 100), "mean_R": round(synth.mean(), 2), **res})
    print(pd.DataFrame(rows).to_string(index=False))

    # write to the report workbook as extra sheets
    out = Path(__file__).resolve().parent.parent / "reports" / "competition_sim.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        note = pd.DataFrame([
            ("Question", "Does increasing lot size / capital achieve 18x?"),
            ("Answer", "Capital is irrelevant (all results are multiples of start). Bigger size = higher f = raises P(18x) AND P(blow up) together. If mean R <= 0, it only speeds up ruin."),
            ("n_trades per competition", N_TRADES),
            ("target", "18x starting balance, measured at peak equity"),
            ("blow up defined as", "equity <= 20% of start"),
            ("sims per risk level", 20000),
        ], columns=["Item", "Detail"])
        note.to_excel(xl, sheet_name="READ ME", index=False)
        for sym, (edge, n, df_t) in all_tables.items():
            df_t.to_excel(xl, sheet_name=f"{sym} (edge {edge:+.2f})", index=False)
        pd.DataFrame(rows).to_excel(xl, sheet_name="edge needed", index=False)
    print(f"\nWritten: {out}")


if __name__ == "__main__":
    main()
