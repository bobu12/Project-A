"""
Download the official Nifty 500 constituents and the NSE ETF list into data/.

Run this once (on a machine with internet) before the first scan:
    python fetch_universe.py

The scanner falls back to a built-in Nifty 100 list if these files are absent,
so this step is optional but gives full coverage.
"""

import os
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SOURCES = {
    "nifty500.csv": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "etfs.csv": "https://archives.nseindia.com/content/equities/eq_etfseclist.csv",
}

# NSE archives reject requests without a browser-like User-Agent.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/csv,*/*",
}


def fetch(name, url):
    os.makedirs(DATA_DIR, exist_ok=True)
    dest = os.path.join(DATA_DIR, name)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
    with open(dest, "wb") as fh:
        fh.write(body)
    print(f"  wrote {dest} ({len(body)} bytes)")


def main():
    for name, url in SOURCES.items():
        try:
            print(f"Fetching {name} ...")
            fetch(name, url)
        except Exception as e:  # keep going; the scanner has a fallback
            print(f"  FAILED {name}: {e}")


if __name__ == "__main__":
    main()
