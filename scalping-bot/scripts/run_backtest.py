#!/usr/bin/env python3
"""Run the walk-forward backtest on both symbols and write the Excel report.

Usage:  python -m scripts.run_backtest
Output: reports/backtest_report.xlsx
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.data import load_symbol
from src.backtester import walk_forward
from src.report import metrics, write_excel


def main():
    start = config.ACCOUNT["start_balance"]
    results = {}

    for sym, cfg in config.SYMBOLS.items():
        cfg = {**cfg, "name": sym}
        print(f"\n=== {sym} ({cfg['timeframe']}) ===")
        df = load_symbol(cfg)
        period = f"{df['Date'].min():%Y-%m-%d} -> {df['Date'].max():%Y-%m-%d}"
        print(f"  bars: {len(df)}  period: {period}")

        trades, final_bal, params = walk_forward(
            df, cfg, config.PARAM_GRID, config.WALK_FORWARD[sym], start)

        m = metrics(trades, start)
        print(f"  trades={m['trades']}  win%={m['win_rate_%']}  "
              f"net=${m['net_pnl_$']}  final=${m['final_balance_$']}  "
              f"maxDD={m['max_drawdown_%']}%  ruined={m['ruined']}")

        results[sym] = {"trades": trades, "metrics": m, "params": params,
                        "period": period, "timeframe": cfg["timeframe"]}

    out = Path(__file__).resolve().parent.parent / "reports" / "backtest_report.xlsx"
    write_excel(out, results)
    print(f"\nReport written: {out}")


if __name__ == "__main__":
    main()
