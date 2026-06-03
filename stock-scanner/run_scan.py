"""
Run one scan and email the results. Designed to be invoked by cron or by
scheduler.py.

Usage:
    python run_scan.py                 # 30-min stock + ETF breakout scan
    python run_scan.py --mf            # also run the daily mutual-fund check
    python run_scan.py --confluence-only   # drop the breakout trigger
    python run_scan.py --equity nifty100   # smaller/faster universe

Email config comes from environment variables (see .env.example / notify.py).
"""

import argparse
import csv
import datetime as dt
import os

import providers
import scanner_core as sc
import universe
from notify import render_html, send_email

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

STOCK_COLUMNS = [
    ("Symbol", "symbol"), ("Price", "price"), ("% Chg", "pctChange"),
    ("200 EMA", "ema200"), ("Dist 200%", "distTo200Pct"),
    ("Max EMA dev%", "maxDevPct"), ("Vol x", "volRatio"),
]
MF_COLUMNS = [
    ("Scheme", "schemeCode"), ("NAV", "nav"), ("200 DMA", "ma200"),
    ("Max dev%", "maxDevPct"),
]


def save_csv(matches, prefix):
    if not matches:
        return None
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    path = os.path.join(RESULTS_DIR, f"{prefix}_{stamp}.csv")
    keys = list(matches[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(matches)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mf", action="store_true", help="also run daily mutual-fund check")
    ap.add_argument("--confluence-only", action="store_true", help="drop breakout trigger")
    ap.add_argument("--equity", default="nifty500", help="equity universe (nifty50/nifty100/nifty500)")
    ap.add_argument("--provider", default=None, help="data provider (groww/yfinance); auto if omitted")
    ap.add_argument("--confluence-pct", type=float, default=6.0)
    args = ap.parse_args()

    cfg = sc.ScanConfig(
        confluence_pct=args.confluence_pct,
        near200_pct=args.confluence_pct,
        require_breakout=not args.confluence_only,
    )

    tickers = universe.stock_and_etf_universe(args.equity)
    fetch, provider_name = providers.get_fetcher(args.provider)
    print(f"Scanning {len(tickers)} stocks/ETFs via {provider_name} ...")
    matches, stats = sc.scan(tickers, cfg, fetch_frames=fetch)
    print(f"  matched {stats['matched']} / scanned {stats['scanned']} (errors {stats['errors']})")
    save_csv(matches, "breakouts")

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"EMA-confluence breakouts ({now}) — {stats['matched']} hit(s)"
    html = render_html(title, matches, STOCK_COLUMNS)

    mf_matches = []
    if args.mf:
        import mf_scanner
        print("Running daily mutual-fund check ...")
        mf_matches, mf_stats = mf_scanner.scan_mutual_funds(args.confluence_pct, args.confluence_pct)
        print(f"  MF matched {len(mf_matches)} / watched {mf_stats.get('watched', 0)}")
        save_csv(mf_matches, "mf")
        html += "<br>" + render_html(
            f"Mutual funds near/under 200-DMA — {len(mf_matches)} hit(s)",
            mf_matches, MF_COLUMNS,
        )

    subject = f"[Scanner] {stats['matched']} breakout(s)" + (
        f" + {len(mf_matches)} MF" if args.mf else "")
    send_email(subject, html)


if __name__ == "__main__":
    main()
