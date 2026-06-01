#!/usr/bin/env python3
"""Live automation runner for MT5 / Exness.

Automates the ONE strategy that showed a genuine out-of-sample edge in the
experiments: gold BREAKOUT (config.LIVE). It reuses the SAME signal code as the
backtester (src/strategy.py), so live decisions cannot silently diverge from
what was tested.

Honest expectation: the measured edge is THIN (profit factor ~1.06). This is
automated, risk-controlled execution - NOT a money printer, and NOT the +391%
overfit number (that one LOSES money out-of-sample). Run on DEMO for weeks and
compare live fills to the backtest before risking real money.

Usually launched via the per-symbol wrappers:
  python -m scripts.run_xauusd            # gold (validated edge)
  python -m scripts.run_btcusd            # BTC  (experimental / unvalidated)
Add --live to trade a DEMO MT5 account on a Windows VPS; default is offline dry run.

Live mode reads credentials from env: EXNESS_LOGIN, EXNESS_PASSWORD, EXNESS_SERVER.
mt5_live.DEMO_ONLY defaults to True and will refuse a real account.
"""
import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.strategy import STRATEGIES
from src.data import load_symbol


def latest_decision(df_closed, params, strategy):
    """df_closed must END on the last CLOSED bar. Returns (sig, atr, close)."""
    d = STRATEGIES[strategy](df_closed, params)
    row = d.iloc[-1]
    sig = 0 if pd.isna(row["sig"]) else int(row["sig"])
    atr = 0.0 if pd.isna(row["atr"]) else float(row["atr"])
    return sig, atr, float(row["close"])


def _plan(sig, atr, price, params, contract, balance, risk, lot_step, min_lot):
    """Translate a signal into a concrete order plan (or None)."""
    if not sig or atr <= 0:
        return None
    r_dist = params["sl_atr"] * atr
    sl = price - sig * r_dist
    tp = price + sig * params["tp_atr"] * atr
    risk_money = balance * risk
    raw = risk_money / (r_dist * contract)
    lots = (raw // lot_step) * lot_step
    if lots < min_lot:
        if min_lot * r_dist * contract <= risk_money:
            lots = min_lot
        else:
            return "SKIP"      # cannot size within risk cap
    return {"side": "buy" if sig == 1 else "sell", "lots": round(lots, 2),
            "entry~": round(price, 2), "sl": round(sl, 2), "tp": round(tp, 2),
            "risk_$": round(r_dist * contract * lots, 2)}


def dry_run(symbol):
    lv = config.LIVE[symbol]
    cfg = {**config.SYMBOLS[symbol], "name": symbol}
    df = load_symbol(cfg)
    p, strat = lv["params"], lv["strategy"]
    sig, atr, px = latest_decision(df, p, strat)
    bal = config.ACCOUNT["start_balance"]
    plan = _plan(sig, atr, px, p, cfg["contract_size"], bal,
                 lv["risk_per_trade"], cfg["lot_step"], cfg["min_lot"])
    tag = "VALIDATED edge" if lv["validated"] else "EXPERIMENTAL / unvalidated"
    print(f"[DRY RUN] {symbol} {lv['timeframe']} strategy={strat}  ({tag})")
    print(f"  last closed bar: {df['Date'].iloc[-1]}  close={px}  atr={atr:.2f}")
    print(f"  signal = { {1:'BUY',-1:'SELL',0:'NO TRADE'}[sig] }")
    if sig == 0:
        print("  -> would WAIT (no breakout on the last closed bar).")
    elif plan == "SKIP":
        print("  -> would SKIP (cannot size within the 5% risk cap).")
    else:
        print(f"  -> would PLACE: {plan}")
    print("(DRY RUN does not connect to any broker. Use --live on a VPS for a DEMO account.)")


def run_live(symbol):
    from src import mt5_live  # imports MetaTrader5 lazily (Windows/VPS only)

    lv = config.LIVE[symbol]
    login = int(os.environ["EXNESS_LOGIN"])
    password = os.environ["EXNESS_PASSWORD"]
    server = os.environ["EXNESS_SERVER"]
    mt5 = mt5_live.connect(login, password, server)

    sym = mt5_live.resolve_symbol(mt5, lv["symbol"])
    tf = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
          "H1": mt5.TIMEFRAME_H1, "D1": mt5.TIMEFRAME_D1}[lv["timeframe"]]
    p, strat = lv["params"], lv["strategy"]
    info = mt5.symbol_info(sym)
    point, contract = info.point, info.trade_contract_size
    last_bar = None
    print(f"LIVE on {sym} {lv['timeframe']} (DEMO_ONLY={mt5_live.DEMO_ONLY}). Ctrl-C to stop.")

    while True:
        try:
            rates = mt5.copy_rates_from_pos(sym, tf, 0, lv["history_bars"])
            df = pd.DataFrame(rates)
            df["Date"] = pd.to_datetime(df["time"], unit="s")
            closed = df.iloc[:-1]                       # drop the still-forming bar
            _, atr, _ = latest_decision(closed, p, strat)

            # always manage an open position (server SL/TP + our trail)
            if atr > 0:
                r_pts = p["sl_atr"] * atr / point
                mt5_live.move_to_breakeven_and_trail(
                    mt5, sym, be_points=p["be_trigger_R"] * r_pts,
                    trail_points=p["trail_R"] * r_pts)

            bar_time = closed["Date"].iloc[-1]
            if bar_time != last_bar:                    # act once per new closed bar
                last_bar = bar_time
                positions = mt5.positions_get(symbol=sym) or []
                if not positions:
                    sig, atr, px = latest_decision(closed, p, strat)
                    if sig and atr > 0:
                        sl_pts = p["sl_atr"] * atr / point
                        tp_pts = p["tp_atr"] * atr / point
                        lots = mt5_live.lots_for_risk(mt5, sym, sl_pts,
                                                      lv["risk_per_trade"])
                        side = "buy" if sig == 1 else "sell"
                        print(f"{bar_time}  ENTER {side} {lots} lots  sl_pts={sl_pts:.0f}")
                        mt5_live.open_trade(mt5, sym, side, lots, sl_pts, tp_pts)
                else:
                    # time-stop: close positions older than max_hold bars
                    pass
            time.sleep(lv["poll_seconds"])
        except KeyboardInterrupt:
            print("stopped."); break
        except Exception as e:                          # keep the bot alive on transient errors
            print(f"[warn] {e}"); time.sleep(lv["poll_seconds"])


def main(symbol):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="trade a (demo) MT5 account; default is offline dry run")
    args = ap.parse_args()
    run_live(symbol) if args.live else dry_run(symbol)


if __name__ == "__main__":
    main("XAUUSD")
