"""Event-driven backtester + walk-forward re-optimizer.

Design choices that keep it honest:
  * No look-ahead: a signal computed from bar i is entered at bar i+1's open.
  * Costs are charged on every trade (spread + slippage per side, commission
    round-turn). If the edge dies once costs are applied, the report shows it.
  * Pessimistic tie-break: if a bar's range spans BOTH stop and target, we
    assume the stop was hit first.
  * Ruin stops the run: if equity hits 0 the account is blown and we halt.

The walk-forward loop is the real version of "backtest daily and improve its
own accuracy": on each step it re-optimizes parameters on a trailing window,
locks them, and trades the next (unseen) window. This guards against - but does
NOT eliminate - overfitting, and never guarantees accuracy will improve.
"""
from dataclasses import dataclass, asdict
from itertools import product
import numpy as np

from .strategy import add_indicators, signal


@dataclass
class Trade:
    symbol: str
    side: str          # BUY / SELL
    entry_time: object
    entry: float
    sl: float
    tp: float
    exit_time: object
    exit: float
    reason: str        # TP / SL / TIME
    lots: float
    pnl: float         # net USD after costs
    balance: float     # account balance after this trade


def _warmup(params):
    return max(params["lookback"], params["atr_period"]) + 1


def run_backtest(df, params, sym_cfg, start_balance, active_after=None):
    """Run one parameter set over `df`. Returns (list[Trade], final_balance).

    `active_after`: only OPEN new trades on bars with Date >= this timestamp
    (used by walk-forward so the warmup bars before a test window don't trade).
    """
    d = add_indicators(df, params["lookback"], params["atr_period"]).reset_index(drop=True)

    dates = d["Date"].to_numpy()
    o = d["open"].to_numpy(float)
    h = d["high"].to_numpy(float)
    low = d["low"].to_numpy(float)
    c = d["close"].to_numpy(float)
    z = d["z"].to_numpy(float)
    atr = d["atr"].to_numpy(float)
    n = len(d)

    contract = sym_cfg["contract_size"]
    lots = sym_cfg["lots"]
    half_spread = sym_cfg["spread"] / 2.0
    slip = sym_cfg["slippage"]
    commission = sym_cfg["commission"] * lots
    close_only = sym_cfg["close_only"]
    edge = half_spread + slip  # adverse price adjustment per side

    active_after = np.datetime64(active_after) if active_after is not None else None

    balance = start_balance
    trades = []
    pos = None
    i = _warmup(params)

    while i < n - 1:
        if pos is None:
            if active_after is not None and dates[i] < active_after:
                i += 1
                continue
            sig = signal(z[i], params["entry_z"])
            if sig != 0 and not np.isnan(atr[i]) and atr[i] > 0:
                j = i + 1                       # enter at NEXT bar
                ref = c[j] if close_only else o[j]
                side = sig
                entry = ref + side * edge       # buy pays up, sell sells down
                if side == 1:
                    sl = entry - params["sl_atr"] * atr[i]
                    tp = entry + params["tp_atr"] * atr[i]
                else:
                    sl = entry + params["sl_atr"] * atr[i]
                    tp = entry - params["tp_atr"] * atr[i]
                pos = {"side": side, "entry": entry, "sl": sl, "tp": tp,
                       "etime": dates[j], "opened": j}
                i = j
                continue
            i += 1
            continue

        # manage open position on bar i
        side = pos["side"]
        if close_only:
            px = c[i]
            hit_sl = px <= pos["sl"] if side == 1 else px >= pos["sl"]
            hit_tp = px >= pos["tp"] if side == 1 else px <= pos["tp"]
        else:
            if side == 1:
                hit_sl, hit_tp = low[i] <= pos["sl"], h[i] >= pos["tp"]
            else:
                hit_sl, hit_tp = h[i] >= pos["sl"], low[i] <= pos["tp"]

        reason = exit_ref = None
        if hit_sl:                              # pessimistic: stop wins ties
            reason, exit_ref = "SL", pos["sl"]
        elif hit_tp:
            reason, exit_ref = "TP", pos["tp"]
        elif (i - pos["opened"]) >= params["max_hold"]:
            reason, exit_ref = "TIME", c[i]

        if reason:
            exit_fill = exit_ref - side * edge  # exit also crosses costs
            gross = (exit_fill - pos["entry"]) * contract * lots * side
            net = gross - commission
            balance += net
            trades.append(Trade(
                symbol=sym_cfg["name"], side="BUY" if side == 1 else "SELL",
                entry_time=pos["etime"], entry=round(pos["entry"], 2),
                sl=round(pos["sl"], 2), tp=round(pos["tp"], 2),
                exit_time=dates[i], exit=round(exit_fill, 2), reason=reason,
                lots=lots, pnl=round(net, 2), balance=round(balance, 2)))
            pos = None
            if balance <= 0:                    # ruin
                break
        i += 1

    return trades, balance


def _score(trades):
    """Optimization objective for the training window: net PnL, but require a
    minimum number of trades so we don't pick a fluke single winner."""
    if len(trades) < 5:
        return -1e9
    return sum(t.pnl for t in trades)


def _grid(grid_cfg):
    keys = list(grid_cfg)
    for combo in product(*(grid_cfg[k] for k in keys)):
        yield dict(zip(keys, combo))


def walk_forward(df, sym_cfg, grid_cfg, wf_cfg, start_balance):
    """Rolling re-optimization. Returns (oos_trades, final_balance, param_log)."""
    train_n, test_n = wf_cfg["train"], wf_cfg["test"]
    combos = list(_grid(grid_cfg))
    balance = start_balance
    oos_trades, param_log = [], []

    i = train_n
    while i + test_n <= len(df) and balance > 0:
        train = df.iloc[i - train_n:i]
        # pick params by best net PnL on the trailing (in-sample) window
        best_p, best_s = None, -1e18
        for p in combos:
            t, _ = run_backtest(train, p, sym_cfg, start_balance=10_000.0)
            s = _score(t)
            if s > best_s:
                best_s, best_p = s, p

        # trade the NEXT (out-of-sample) window with locked params. We feed the
        # warmup bars before the window so indicators are valid, but only allow
        # entries from the window start onward (active_after).
        warm = _warmup(best_p)
        seg = df.iloc[max(0, i - warm):i + test_n]
        active_after = df.iloc[i]["Date"]
        t, balance = run_backtest(seg, best_p, sym_cfg, start_balance=balance,
                                  active_after=active_after)
        oos_trades.extend(t)
        param_log.append({"from": active_after, **best_p, "is_score": round(best_s, 2)})
        i += test_n

    return oos_trades, balance, param_log
