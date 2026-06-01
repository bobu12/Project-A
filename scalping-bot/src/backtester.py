"""Event-driven backtester + walk-forward re-optimizer with RISK MANAGEMENT.

Risk model (this is the part you asked to fix):
  * Position SIZING is risk-based. We compute the lot so that hitting the
    INITIAL stop loses at most `risk_per_trade` of current equity. So the loss
    on a stopped trade is capped (your "5% max SL") regardless of price level.
    If even the broker minimum lot would exceed that cap, the trade is SKIPPED
    rather than over-risked.
  * Stops MOVE in your favour:
      - move to BREAKEVEN once profit reaches `be_trigger_R` risk-units (R),
      - then TRAIL `trail_R` R behind the best price reached.
    Stops never move backwards. (Refs: trailing-stop / %-risk best practice.)

Integrity:
  * No look-ahead: signal from bar i is entered at bar i+1's open. Trailing
    updates take effect from the NEXT bar (we protect with the prior bar's
    stop, then ratchet at bar close) - conservative, not optimistic.
  * Pessimistic tie-break: if a bar spans both stop and target, stop wins.
  * Ruin halts the run.
"""
from dataclasses import dataclass
from itertools import product
import numpy as np

from .strategy import STRATEGIES


@dataclass
class Trade:
    symbol: str
    side: str
    entry_time: object
    entry: float
    sl: float          # INITIAL stop (the trail is recorded via exit/reason)
    tp: float
    exit_time: object
    exit: float
    reason: str        # TP / SL / TRAIL / TIME
    lots: float
    risk_usd: float    # dollars risked to the initial stop
    pnl: float
    balance: float


def _warmup(p):
    base = max(p.get("lookback", 0), p.get("channel", 0), p["atr_period"])
    return base + 1


def _size_lots(risk_money, r_distance, sym_cfg):
    """Lots so that initial-stop loss ~= risk_money. Round DOWN to lot step so
    we never exceed the cap. Returns 0.0 if even min lot would over-risk."""
    contract = sym_cfg["contract_size"]
    raw = risk_money / (r_distance * contract)
    step = sym_cfg["lot_step"]
    lots = np.floor(raw / step) * step
    if lots < sym_cfg["min_lot"]:
        min_risk = sym_cfg["min_lot"] * r_distance * contract
        if min_risk <= risk_money:
            return sym_cfg["min_lot"]
        return 0.0                      # cannot size within risk cap -> skip
    return round(lots, 4)


def run_backtest(df, params, sym_cfg, start_balance, risk_per_trade,
                 strategy="meanrev", active_after=None):
    d = STRATEGIES[strategy](df, params).reset_index(drop=True)
    dates = d["Date"].to_numpy()
    o, h, low, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sig_arr, atr = d["sig"].to_numpy(), d["atr"].to_numpy(float)
    n = len(d)

    contract = sym_cfg["contract_size"]
    half_spread, slip = sym_cfg["spread"] / 2.0, sym_cfg["slippage"]
    edge = half_spread + slip
    close_only = sym_cfg["close_only"]
    active_after = np.datetime64(active_after) if active_after is not None else None

    balance = start_balance
    trades, pos = [], None
    i = _warmup(params)

    while i < n - 1:
        if pos is None:
            if active_after is not None and dates[i] < active_after:
                i += 1; continue
            sig = int(sig_arr[i])
            if sig and not np.isnan(atr[i]) and atr[i] > 0:
                j = i + 1
                ref = c[j] if close_only else o[j]
                side = sig
                entry = ref + side * edge
                r_dist = params["sl_atr"] * atr[i]            # R = initial risk distance
                sl = entry - side * r_dist
                tp = entry + side * params["tp_atr"] * atr[i]
                lots = _size_lots(risk_per_trade * balance, r_dist, sym_cfg)
                if lots <= 0:                                  # can't size within risk -> skip
                    i += 1; continue
                pos = {"side": side, "entry": entry, "sl": sl, "sl_init": sl,
                       "tp": tp, "R": r_dist, "best": entry, "be": False,
                       "opened": j, "lots": lots, "etime": dates[j]}
                i = j; continue
            i += 1; continue

        # --- manage open position on bar i (protect with prior stop first) ---
        side, sl, tp = pos["side"], pos["sl"], pos["tp"]
        if close_only:
            px = c[i]
            hit_sl = px <= sl if side == 1 else px >= sl
            hit_tp = px >= tp if side == 1 else px <= tp
        else:
            if side == 1:
                hit_sl, hit_tp = low[i] <= sl, h[i] >= tp
            else:
                hit_sl, hit_tp = h[i] >= sl, low[i] <= tp

        reason = exit_ref = None
        if hit_sl:
            # was the stop already trailed past breakeven? label TRAIL vs SL
            reason = "TRAIL" if pos["be"] else "SL"
            exit_ref = sl
        elif hit_tp:
            reason, exit_ref = "TP", tp
        elif (i - pos["opened"]) >= params["max_hold"]:
            reason, exit_ref = "TIME", c[i]

        if reason:
            exit_fill = exit_ref - side * edge
            lots = pos["lots"]
            gross = (exit_fill - pos["entry"]) * contract * lots * side
            net = gross - sym_cfg["commission"] * lots
            balance += net
            trades.append(Trade(
                symbol=sym_cfg["name"], side="BUY" if side == 1 else "SELL",
                entry_time=pos["etime"], entry=round(pos["entry"], 2),
                sl=round(pos["sl_init"], 2),
                tp=round(tp, 2), exit_time=dates[i], exit=round(exit_fill, 2),
                reason=reason, lots=lots,
                risk_usd=round(pos["R"] * contract * lots, 2),
                pnl=round(net, 2), balance=round(balance, 2)))
            pos = None
            if balance <= 0:
                break
            i += 1; continue

        # --- ratchet the stop at bar close (takes effect next bar) ---
        ext = h[i] if side == 1 else low[i]
        if close_only:
            ext = c[i]
        pos["best"] = max(pos["best"], ext) if side == 1 else min(pos["best"], ext)
        profit_dist = (pos["best"] - pos["entry"]) * side
        if not pos["be"] and profit_dist >= params["be_trigger_R"] * pos["R"]:
            be = pos["entry"] + side * (half_spread)          # ~breakeven incl. half-spread
            pos["sl"] = max(pos["sl"], be) if side == 1 else min(pos["sl"], be)
            pos["be"] = True
        if pos["be"]:
            trail = pos["best"] - side * params["trail_R"] * pos["R"]
            pos["sl"] = max(pos["sl"], trail) if side == 1 else min(pos["sl"], trail)
        i += 1

    return trades, balance


def _score(trades):
    if len(trades) < 5:
        return -1e9
    return sum(t.pnl for t in trades)


def _grid(g):
    keys = list(g)
    for combo in product(*(g[k] for k in keys)):
        yield dict(zip(keys, combo))


def walk_forward(df, sym_cfg, grid_cfg, wf_cfg, start_balance, risk_per_trade,
                 strategy="meanrev"):
    train_n, test_n = wf_cfg["train"], wf_cfg["test"]
    combos = list(_grid(grid_cfg))
    balance = start_balance
    oos_trades, param_log = [], []

    i = train_n
    while i + test_n <= len(df) and balance > 0:
        train = df.iloc[i - train_n:i]
        best_p, best_s = None, -1e18
        for p in combos:
            t, _ = run_backtest(train, p, sym_cfg, 10_000.0, risk_per_trade, strategy)
            s = _score(t)
            if s > best_s:
                best_s, best_p = s, p

        warm = _warmup(best_p)
        seg = df.iloc[max(0, i - warm):i + test_n]
        active_after = df.iloc[i]["Date"]
        t, balance = run_backtest(seg, best_p, sym_cfg, balance, risk_per_trade,
                                  strategy, active_after=active_after)
        oos_trades.extend(t)
        param_log.append({"from": active_after, **best_p, "is_score": round(best_s, 2)})
        i += test_n

    return oos_trades, balance, param_log
