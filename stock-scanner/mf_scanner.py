"""
Mutual-fund check (runs ONCE per day, not every 30 min).

Mutual funds publish a single NAV per day — no intraday prices and no volume —
so the intraday breakout logic cannot apply. Instead this approximates the same
idea on the daily NAV series: flag schemes whose NAV is near/under its 200-day
moving average with the 20/50/100-day MAs clustered within +/- pct of NAV.

NAV history comes from the AMFI data via the `mftool` library (pip install mftool).
Configure which schemes to watch in data/mf_schemes.csv with a 'SchemeCode' column
(AMFI scheme codes), or set MF_SCHEMES env var to a comma-separated list.
"""

import csv
import os

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def watched_schemes():
    env = os.environ.get("MF_SCHEMES", "")
    codes = [c.strip() for c in env.split(",") if c.strip()]
    if codes:
        return codes
    path = os.path.join(DATA_DIR, "mf_schemes.csv")
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            col = next((c for c in (reader.fieldnames or []) if "code" in c.lower()), None)
            if col:
                codes = [(row.get(col) or "").strip() for row in reader]
    return [c for c in codes if c]


def _nav_history(code):
    """Return a NAV pandas Series (date-indexed) for a scheme, or None."""
    try:
        from mftool import Mftool
    except ImportError:
        print("[mf] mftool not installed — skipping mutual-fund scan "
              "(pip install mftool)")
        return None
    try:
        mf = Mftool()
        data = mf.get_scheme_historical_nav(code)  # dict with 'data': [{date,nav}]
        if not data or "data" not in data:
            return None
        rows = data["data"]
        s = pd.Series(
            {pd.to_datetime(r["date"], format="%d-%m-%Y"): float(r["nav"]) for r in rows}
        ).sort_index()
        return s
    except Exception as e:
        print(f"[mf] {code}: {e}")
        return None


def analyse_nav(series, confluence_pct=6.0, near200_pct=6.0):
    if series is None or len(series) < 200:
        return None
    nav = float(series.iloc[-1])
    ma20 = float(series.rolling(20).mean().iloc[-1])
    ma50 = float(series.rolling(50).mean().iloc[-1])
    ma100 = float(series.rolling(100).mean().iloc[-1])
    ma200 = float(series.rolling(200).mean().iloc[-1])

    max_dev = max(abs((m - nav) / nav * 100) for m in (ma20, ma50, ma100))
    confluence = max_dev <= confluence_pct
    near_under_200 = nav <= ma200 * (1 + near200_pct / 100)

    return {
        "nav": round(nav, 4),
        "ma200": round(ma200, 4),
        "maxDevPct": round(max_dev, 2),
        "matched": confluence and near_under_200,
    }


def scan_mutual_funds(confluence_pct=6.0, near200_pct=6.0):
    matches = []
    codes = watched_schemes()
    if not codes:
        return matches, {"watched": 0, "note": "no MF scheme codes configured"}
    for code in codes:
        m = analyse_nav(_nav_history(code), confluence_pct, near200_pct)
        if m and m["matched"]:
            m["schemeCode"] = code
            matches.append(m)
    matches.sort(key=lambda m: m["maxDevPct"])
    return matches, {"watched": len(codes), "matched": len(matches)}
