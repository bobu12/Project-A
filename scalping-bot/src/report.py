"""Performance metrics + Excel report writer.

The Trades sheet has exactly the columns requested (Time, Buy/Sell, Entry, SL,
Exit) plus the fields you need to make sense of them (exit reason, P/L, running
balance). A Summary sheet and a README/Disclaimer sheet are included so the
numbers can never be mistaken for a promise.
"""
from dataclasses import asdict
import pandas as pd


def metrics(trades, start_balance):
    if not trades:
        return {"trades": 0, "win_rate_%": 0, "net_pnl_$": 0,
                "final_balance_$": start_balance, "max_drawdown_%": 0,
                "profit_factor": 0, "expectancy_$": 0, "ruined": False}

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    bals = [start_balance] + [t.balance for t in trades]

    peak = bals[0]
    max_dd = 0.0
    for b in bals:
        peak = max(peak, b)
        if peak > 0:
            max_dd = max(max_dd, (peak - b) / peak)

    gross_win = sum(wins)
    gross_loss = -sum(losses)
    final = bals[-1]
    return {
        "trades": len(trades),
        "win_rate_%": round(100 * len(wins) / len(trades), 1),
        "net_pnl_$": round(final - start_balance, 2),
        "final_balance_$": round(final, 2),
        "max_drawdown_%": round(100 * max_dd, 1),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
        "expectancy_$": round(sum(pnls) / len(pnls), 2),
        "ruined": final <= 0,
    }


_TRADE_COLS = {
    "entry_time": "Time",
    "side": "Buy/Sell",
    "entry": "Entry",
    "sl": "SL",
    "exit": "Exit",
    "exit_time": "Exit Time",
    "reason": "Exit Reason",
    "lots": "Lots",
    "pnl": "P/L $",
    "balance": "Balance $",
}


def trades_frame(trades):
    if not trades:
        return pd.DataFrame(columns=list(_TRADE_COLS.values()))
    df = pd.DataFrame(asdict(t) for t in trades)
    df = df[list(_TRADE_COLS)]                       # order: requested cols first
    return df.rename(columns=_TRADE_COLS)


DISCLAIMER = [
    ("WHAT THIS IS", "A walk-forward backtest of a z-score mean-reversion strategy on REAL historical data."),
    ("WHAT THIS IS NOT", "A prediction, a guarantee, or evidence the strategy will make money live. It is not advice."),
    ("", ""),
    ("XAUUSD data", "Real M15 OHLC from ejtraderLabs/historical-data (GitHub). Coverage ends 2022-03. 'Last year' = most recent real year available in-sandbox."),
    ("BTCUSD data", "Real DAILY CLOSE only from CoinMetrics. No intraday highs/lows => SL/TP can only trigger on a daily close crossing the level. LOW fidelity; treat as illustrative."),
    ("Costs modeled", "Spread + slippage + commission are ESTIMATES of Exness-style costs, not a live feed. Real fills, slippage and swaps will differ and are usually worse."),
    ("Leverage note", "1:2000 leverage does not reduce risk - it enables ruin. The requested fixed lots (0.10 XAU / 0.06 BTC) on $500 are very large relative to capital; see Max Drawdown and the 'ruined' flag."),
    ("Win rate trap", "A high win rate does NOT mean profitable. Read Net P/L, Profit Factor and Max Drawdown together, never win rate alone."),
    ("Before any real money", "Re-run on YOUR broker's data, then forward-test on a DEMO account for weeks. If demo != backtest, the cost model is wrong."),
]


def write_excel(path, results):
    """results: dict[symbol] -> {trades, metrics, params, period, timeframe}."""
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        # Summary first
        summ = []
        for sym, r in results.items():
            row = {"Symbol": sym, "Timeframe": r["timeframe"], "Period": r["period"]}
            row.update(r["metrics"])
            summ.append(row)
        pd.DataFrame(summ).to_excel(xl, sheet_name="Summary", index=False)

        # Disclaimer
        pd.DataFrame(DISCLAIMER, columns=["Item", "Detail"]).to_excel(
            xl, sheet_name="READ ME - Disclaimer", index=False)

        # Per-symbol trades + the param schedule the re-optimizer chose
        for sym, r in results.items():
            trades_frame(r["trades"]).to_excel(xl, sheet_name=f"{sym} Trades", index=False)
            if r.get("params"):
                pd.DataFrame(r["params"]).to_excel(
                    xl, sheet_name=f"{sym} Params", index=False)
    return path
