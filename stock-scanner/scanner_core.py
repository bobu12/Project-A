"""
Core scanning engine: EMA-confluence + breakout detection for stocks/ETFs.

Strategy (daily timeframe):
  * Price is NEAR or UNDER the 200 EMA.
  * The 20, 50, 100 EMAs are all clustered within +/- CONFLUENCE_PCT of price
    (a compressed base).
  * BREAKOUT trigger: latest close breaks above the prior N-day high on
    above-average volume.

The data-fetch layer uses yfinance; the analysis layer is pure pandas so it can
be unit-tested offline without network access.
"""

from dataclasses import dataclass, asdict

import pandas as pd
import yfinance as yf


@dataclass
class ScanConfig:
    confluence_pct: float = 6.0      # +/- band for 20/50/100 EMA vs price
    near200_pct: float = 6.0         # how far ABOVE 200 EMA still counts as "near"
    breakout_lookback: int = 20      # bars to define the resistance being broken
    vol_mult: float = 1.5            # today's volume must exceed this x avg volume
    require_breakout: bool = True    # False = confluence-only (no trigger)


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def analyse(df: pd.DataFrame, cfg: ScanConfig = ScanConfig()):
    """Return a metrics dict for one instrument, or None if not enough data."""
    close = df["Close"].dropna()
    if len(close) < 200:  # need 200 bars for a meaningful 200 EMA
        return None
    high = df["High"].reindex(close.index)
    volume = df["Volume"].reindex(close.index)

    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    pct_change = (price - prev) / prev * 100 if prev else 0.0

    e20 = float(ema(close, 20).iloc[-1])
    e50 = float(ema(close, 50).iloc[-1])
    e100 = float(ema(close, 100).iloc[-1])
    e200 = float(ema(close, 200).iloc[-1])

    # Deviation of each fast EMA from current price, in %.
    dev = {
        20: (e20 - price) / price * 100,
        50: (e50 - price) / price * 100,
        100: (e100 - price) / price * 100,
    }
    max_dev = max(abs(v) for v in dev.values())          # tightness of the cluster
    confluence = max_dev <= cfg.confluence_pct

    # Price near or under the 200 EMA (under it, or up to near200_pct above it).
    dist_200 = (price - e200) / e200 * 100
    near_under_200 = price <= e200 * (1 + cfg.near200_pct / 100)

    # Breakout: latest close clears the highest high of the prior lookback bars.
    if len(high) > cfg.breakout_lookback:
        prior_high = float(high.iloc[-(cfg.breakout_lookback + 1):-1].max())
    else:
        prior_high = float(high.iloc[:-1].max()) if len(high) > 1 else price
    broke_high = price > prior_high

    vol_today = float(volume.iloc[-1])
    vol_avg = float(volume.iloc[-(cfg.breakout_lookback + 1):-1].mean())
    vol_ratio = vol_today / vol_avg if vol_avg else 0.0
    vol_ok = vol_ratio >= cfg.vol_mult

    breakout = broke_high and vol_ok

    matched = confluence and near_under_200 and (breakout or not cfg.require_breakout)

    return {
        "price": round(price, 2),
        "pctChange": round(pct_change, 2),
        "ema20": round(e20, 2),
        "ema50": round(e50, 2),
        "ema100": round(e100, 2),
        "ema200": round(e200, 2),
        "distTo200Pct": round(dist_200, 2),
        "maxDevPct": round(max_dev, 2),
        "priorHigh": round(prior_high, 2),
        "volRatio": round(vol_ratio, 2),
        "confluence": confluence,
        "nearUnder200": near_under_200,
        "breakout": breakout,
        "matched": matched,
    }


def fetch_prices(tickers, period="2y"):
    """Bulk daily OHLCV download (2y gives a stable 200 EMA)."""
    return yf.download(
        tickers,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )


def ticker_frame(data, ticker):
    try:
        if isinstance(data.columns, pd.MultiIndex):
            df = data[ticker].dropna(how="all")
        else:
            df = data.dropna(how="all")
    except (KeyError, TypeError):
        return None
    return df if df is not None and not df.empty else None


def scan(tickers, cfg: ScanConfig = ScanConfig(), fetch_frames=None, period="2y"):
    """Scan a list of tickers; return (matches, stats).

    fetch_frames: optional callable(tickers) -> {ticker: OHLCV DataFrame}. When
    omitted, falls back to a yfinance bulk download. Use providers.get_fetcher()
    to obtain a Groww or yfinance fetcher.
    """
    if fetch_frames is None:
        data = fetch_prices(tickers, period=period)
        frames = {t: ticker_frame(data, t) for t in tickers}
    else:
        frames = fetch_frames(tickers)

    matches, errors = [], 0
    for t in tickers:
        df = frames.get(t)
        if df is None:
            errors += 1
            continue
        m = analyse(df, cfg)
        if m is None:
            continue
        if m["matched"]:
            m["ticker"] = t
            m["symbol"] = t.replace(".NS", "").replace(".BO", "")
            matches.append(m)
    matches.sort(key=lambda m: m["maxDevPct"])  # tightest confluence first
    return matches, {"scanned": len(tickers), "errors": errors, "matched": len(matches)}
