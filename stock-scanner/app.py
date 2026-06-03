"""
NSE/BSE Stock Scanner — mobile web app backend.

Serves a phone-friendly single page (static/index.html) and a /api/scan
endpoint that screens a universe of Indian stocks on technical, price/volume,
and fundamental criteria.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://<this-host>:5000 on your phone.
"""

import math

import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, request, send_from_directory

import providers
import scanner_core as sc
import universe as uni
from universe import UNIVERSES

app = Flask(__name__, static_folder="static")

# Cache of (period) -> bulk price DataFrame, refreshed per process run.
_price_cache = {}


# --------------------------------------------------------------------------- #
# Indicator helpers
# --------------------------------------------------------------------------- #
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _clean(value):
    """Make a value JSON-safe (no NaN/inf)."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _round(value, ndigits=2):
    value = _clean(value)
    return round(value, ndigits) if value is not None else None


# --------------------------------------------------------------------------- #
# Data fetching
# --------------------------------------------------------------------------- #
def fetch_prices(tickers, period="1y"):
    """Bulk-download daily OHLCV for all tickers at once (fast)."""
    key = (period, tuple(tickers))
    if key in _price_cache:
        return _price_cache[key]
    data = yf.download(
        tickers,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )
    _price_cache[key] = data
    return data


def ticker_frame(data, ticker):
    """Pull a single ticker's OHLCV frame out of a bulk yfinance download."""
    try:
        if isinstance(data.columns, pd.MultiIndex):
            df = data[ticker].dropna(how="all")
        else:  # single-ticker download
            df = data.dropna(how="all")
    except (KeyError, TypeError):
        return None
    return df if df is not None and not df.empty else None


def fundamentals(ticker):
    """Per-ticker fundamentals. Slow, so only called for matched stocks."""
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return {}
    return {
        "name": info.get("shortName") or info.get("longName"),
        "sector": info.get("sector"),
        "pe": _round(info.get("trailingPE")),
        "marketCap": info.get("marketCap"),
        "dividendYield": _round(
            (info.get("dividendYield") or 0) * 100 if info.get("dividendYield") and info.get("dividendYield") < 1
            else info.get("dividendYield"), 2
        ),
    }


# --------------------------------------------------------------------------- #
# Scan
# --------------------------------------------------------------------------- #
def analyse(df):
    """Compute indicators for one stock from its OHLCV frame."""
    close = df["Close"].dropna()
    volume = df["Volume"].dropna()
    if len(close) < 50:
        return None

    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    pct_change = (last - prev) / prev * 100 if prev else 0.0

    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    rsi14 = float(rsi(close).iloc[-1])

    vol_today = float(volume.iloc[-1])
    vol_avg20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = vol_today / vol_avg20 if vol_avg20 else 0.0

    high_52w = float(close.max())
    low_52w = float(close.min())

    signals = []
    if rsi14 < 35:
        signals.append("Oversold")
    if rsi14 > 70:
        signals.append("Overbought")
    if sma20 > sma50 and last > sma20:
        signals.append("Bullish trend")
    if sma20 < sma50 and last < sma20:
        signals.append("Bearish trend")
    if vol_ratio >= 1.5:
        signals.append("Volume spike")
    if last >= high_52w * 0.98:
        signals.append("Near 52w high")
    if last <= low_52w * 1.02:
        signals.append("Near 52w low")

    return {
        "price": _round(last),
        "pctChange": _round(pct_change),
        "rsi": _round(rsi14),
        "sma20": _round(sma20),
        "sma50": _round(sma50),
        "volRatio": _round(vol_ratio),
        "high52w": _round(high_52w),
        "low52w": _round(low_52w),
        "signals": signals,
    }


def passes(metrics, f):
    """Apply the user's filters (all optional)."""
    p = metrics["price"]
    if f.get("minPrice") is not None and (p is None or p < f["minPrice"]):
        return False
    if f.get("maxPrice") is not None and (p is None or p > f["maxPrice"]):
        return False
    if f.get("minPct") is not None and (metrics["pctChange"] is None or metrics["pctChange"] < f["minPct"]):
        return False
    if f.get("maxPct") is not None and (metrics["pctChange"] is None or metrics["pctChange"] > f["maxPct"]):
        return False
    if f.get("rsiMin") is not None and (metrics["rsi"] is None or metrics["rsi"] < f["rsiMin"]):
        return False
    if f.get("rsiMax") is not None and (metrics["rsi"] is None or metrics["rsi"] > f["rsiMax"]):
        return False
    if f.get("volRatioMin") is not None and (metrics["volRatio"] is None or metrics["volRatio"] < f["volRatioMin"]):
        return False
    if f.get("trend") == "bullish" and "Bullish trend" not in metrics["signals"]:
        return False
    if f.get("trend") == "bearish" and "Bearish trend" not in metrics["signals"]:
        return False
    return True


@app.route("/api/scan", methods=["POST"])
def scan():
    body = request.get_json(force=True, silent=True) or {}
    universe = body.get("universe", "nifty50")
    tickers = UNIVERSES.get(universe, UNIVERSES["nifty50"])
    filters = body.get("filters", {})
    want_fundamentals = body.get("fundamentals", True)
    max_pe = filters.get("maxPe")

    data = fetch_prices(tickers)

    matches = []
    errors = 0
    for ticker in tickers:
        df = ticker_frame(data, ticker)
        if df is None:
            errors += 1
            continue
        metrics = analyse(df)
        if metrics is None:
            continue
        if not passes(metrics, filters):
            continue
        metrics["ticker"] = ticker
        metrics["symbol"] = ticker.replace(".NS", "").replace(".BO", "")
        matches.append(metrics)

    # Sort by absolute % move (most active first) and cap fundamentals lookups.
    matches.sort(key=lambda m: abs(m["pctChange"] or 0), reverse=True)

    if want_fundamentals:
        for m in matches[:25]:  # fundamentals are slow; only enrich the top hits
            m.update(fundamentals(m["ticker"]))
        if max_pe is not None:
            matches = [
                m for m in matches
                if m.get("pe") is None or m["pe"] <= max_pe
            ]

    return jsonify({
        "count": len(matches),
        "scanned": len(tickers),
        "errors": errors,
        "results": matches,
    })


@app.route("/api/scan-ema", methods=["POST"])
def scan_ema():
    """EMA-confluence breakout scan (price near/under 200 EMA, 20/50/100 EMAs
    within +/- pct, optional breakout trigger), using the configured data
    provider (Groww if creds present, else yfinance)."""
    body = request.get_json(force=True, silent=True) or {}
    uni_name = body.get("universe", "nifty50")
    pct = float(body.get("confluencePct", 6.0))
    require_breakout = bool(body.get("requireBreakout", True))

    if uni_name in ("nifty50", "nifty100"):
        tickers = uni.stock_and_etf_universe(uni_name)
    else:
        tickers = uni.equity_universe(uni_name) + uni.etf_universe()

    cfg = sc.ScanConfig(
        confluence_pct=pct, near200_pct=pct, require_breakout=require_breakout
    )
    try:
        fetch, provider_name = providers.get_fetcher(body.get("provider"))
        matches, stats = sc.scan(tickers, cfg, fetch_frames=fetch)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"provider": provider_name, "results": matches, **stats})


@app.route("/api/universes")
def universes():
    return jsonify({k: len(v) for k, v in UNIVERSES.items()})


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    import os
    # host=0.0.0.0 so a phone on the same network can reach it.
    # PORT is configurable: macOS uses port 5000 for AirPlay Receiver, so set
    # PORT=8000 (or disable AirPlay Receiver in System Settings > General > AirDrop & Handoff).
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f" * Serving on http://localhost:{port}  (and http://<your-LAN-IP>:{port} for phones)")
    app.run(host=host, port=port, debug=False)
