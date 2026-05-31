"""Trading signal: z-score mean-reversion with ATR-sized stops.

This is a deliberately simple, explainable strategy (no black box). When price
is stretched far from its recent mean (high |z-score|), we fade it, with a
stop and target sized in ATR units. Parameters are tuned by the walk-forward
re-optimizer in backtester.py.

There is NO claim of edge here. Whether this makes money net of costs is
exactly what the backtest measures - and on most markets/periods, it won't.
"""
import numpy as np
import pandas as pd


def _atr(high, low, close, period):
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def add_indicators(df: pd.DataFrame, lookback: int, atr_period: int) -> pd.DataFrame:
    """Return df with z-score and ATR columns added."""
    out = df.copy()
    ma = out["close"].rolling(lookback).mean()
    sd = out["close"].rolling(lookback).std()
    out["z"] = (out["close"] - ma) / sd
    out["atr"] = _atr(out["high"], out["low"], out["close"], atr_period)
    return out


def signal(z: float, entry_z: float) -> int:
    """+1 = buy (oversold), -1 = sell (overbought), 0 = no trade."""
    if np.isnan(z):
        return 0
    if z <= -entry_z:
        return 1
    if z >= entry_z:
        return -1
    return 0
