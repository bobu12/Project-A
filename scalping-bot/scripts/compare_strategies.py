#!/usr/bin/env python3
"""Head-to-head test of multiple edge hypotheses on real data.

Runs walk-forward (out-of-sample) for each strategy variant on each symbol and
reports the honest verdict: does ANY of them clear costs over a large sample?

Usage:  python -m scripts.compare_strategies
Output: reports/strategy_comparison.xlsx
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.data import load_symbol
from src.backtester import walk_forward
from src.report import metrics
from src.competition_sim import r_multiples, simulate


def main():
    start = config.ACCOUNT["start_balance"]
    risk = config.ACCOUNT["risk_per_trade"]
    rows = []

    for sym, base_cfg in config.SYMBOLS.items():
        cfg = {**base_cfg, "name": sym}
        df = load_symbol(cfg)
        period = f"{df['Date'].min():%Y-%m-%d}..{df['Date'].max():%Y-%m-%d}"
        print(f"\n##### {sym} ({cfg['timeframe']})  {period}  bars={len(df)} #####")

        for var in config.STRATEGY_VARIANTS:
            # session strategies only make sense on intraday, non-close-only data
            if var.get("session_only") and (cfg["close_only"] or cfg["timeframe"] == "D1"):
                continue
            trades, _, _ = walk_forward(
                df, cfg, var["grid"], config.WALK_FORWARD[sym], start, risk,
                strategy=var["strategy"])
            m = metrics(trades, start)
            R = r_multiples(trades)
            edge = float(R.mean()) if len(R) else 0.0
            # only ask about 18x if there's a positive edge AND a real sample
            p18 = "-"
            if edge > 0 and len(R) >= 30:
                p18 = f"{simulate(R, 0.10, 200, n_sims=5000)['P(reach 18x)_%']}%"

            row = {"symbol": sym, "variant": var["name"], "trades": m["trades"],
                   "win_%": m["win_rate_%"], "edge_R": round(edge, 3),
                   "net_$": m["net_pnl_$"], "PF": m["profit_factor"],
                   "maxDD_%": m["max_drawdown_%"], "final_$": m["final_balance_$"],
                   "P(18x)@10%": p18}
            rows.append(row)
            verdict = "POSITIVE edge" if edge > 0 else "no edge"
            print(f"  {var['name']:18s} trades={m['trades']:3d} win={m['win_rate_%']:4.1f}% "
                  f"edgeR={edge:+.3f} net=${m['net_pnl_$']:+8.2f} PF={m['profit_factor']:.2f} "
                  f"DD={m['max_drawdown_%']:.0f}%  -> {verdict}")

    table = pd.DataFrame(rows)
    out = Path(__file__).resolve().parent.parent / "reports" / "strategy_comparison.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        table.to_excel(xl, sheet_name="Comparison", index=False)
        note = pd.DataFrame([
            ("edge_R", "Mean R-multiple per trade = average profit in units of risk. THE number that matters. >0 net of costs = a real edge; <=0 = no edge, no sizing fixes it."),
            ("P(18x)@10%", "Monte-Carlo prob. of reaching 18x in 200 trades at 10% risk - shown ONLY when edge>0 and >=30 trades (else it's noise)."),
            ("Reading it", "Look for any variant with edge_R clearly >0 AND a large trade count AND positive net across the out-of-sample walk-forward. That is the only honest green light."),
            ("Caveat", "Even a positive result here must survive: more data, more instruments, and weeks of DEMO forward-testing before any real money. Past != future."),
        ], columns=["Column", "Meaning"])
        note.to_excel(xl, sheet_name="READ ME", index=False)

    # honest summary
    winners = table[(table["edge_R"] > 0) & (table["trades"] >= 30) & (table["net_$"] > 0)]
    print("\n" + "=" * 70)
    if len(winners):
        print("Variants with a positive out-of-sample edge AND a real sample:")
        print(winners.to_string(index=False))
        print("\nThese are CANDIDATES, not conclusions. Validate further before trusting them.")
    else:
        print("VERDICT: No variant shows a positive out-of-sample edge on a real")
        print("sample. That is the honest result - none of these clear costs yet.")
    print(f"\nWritten: {out}")


if __name__ == "__main__":
    main()
