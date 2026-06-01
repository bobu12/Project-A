"""Strategy library: pluggable signal builders + shared indicators.

Each builder takes a price DataFrame + params and returns the frame with two
extra columns the backtester needs:
    'atr' : volatility unit for stop/target sizing
    'sig' : +1 (go long), -1 (go short), 0 (no trade) at each bar, computed
            using ONLY information available up to that bar (no look-ahead).

The backtester is strategy-agnostic: it just consumes 'sig' and 'atr' and
applies the shared risk management (risk-based size, breakeven, trailing).

These are hypotheses to TEST, not claims of edge. The comparison harness
measures whether any of them actually clears costs over a large sample.
"""
import numpy as np
import pandas as pd


def atr(df, period):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _session_mask(dates, start_h, end_h):
    """True where the bar's UTC hour is within [start_h, end_h)."""
    hours = pd.DatetimeIndex(dates).hour
    return (hours >= start_h) & (hours < end_h)


def build_meanrev(df, p):
    """Mean-reversion: fade stretched price (z-score of close vs rolling mean)."""
    d = df.copy()
    ma = d["close"].rolling(p["lookback"]).mean()
    sd = d["close"].rolling(p["lookback"]).std()
    z = (d["close"] - ma) / sd
    d["atr"] = atr(d, p["atr_period"])
    sig = np.where(z <= -p["entry_z"], 1, np.where(z >= p["entry_z"], -1, 0))
    d["sig"] = _maybe_session(d, sig, p)
    return d


def build_breakout(df, p):
    """Momentum: Donchian breakout of the prior N-bar high/low (no lookahead -
    the channel excludes the current bar via shift(1))."""
    d = df.copy()
    hi = d["high"].rolling(p["channel"]).max().shift(1)
    lo = d["low"].rolling(p["channel"]).min().shift(1)
    d["atr"] = atr(d, p["atr_period"])
    sig = np.where(d["close"] > hi, 1, np.where(d["close"] < lo, -1, 0))
    d["sig"] = _maybe_session(d, sig, p)
    return d


def _maybe_session(d, sig, p):
    """Optionally zero signals outside a liquid trading window (UTC hours)."""
    sess = p.get("session")
    if sess is None:
        return sig
    mask = _session_mask(d["Date"].to_numpy(), sess[0], sess[1])
    return np.where(mask, sig, 0)


STRATEGIES = {
    "meanrev": build_meanrev,
    "breakout": build_breakout,
}
