"""
Ticker universes for the scanner.

Loading order for the main equity universe:
  1. data/nifty500.csv  (run fetch_universe.py to download the official list)
  2. built-in Nifty 100 fallback (always available, no network needed)

NSE tickers use the .NS suffix; BSE uses .BO (yfinance convention).
"""

import csv
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

NIFTY50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "BAJFINANCE.NS",
    "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "NESTLEIND.NS", "BAJAJFINSV.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS",
    "TATAMOTORS.NS", "TATASTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "JSWSTEEL.NS",
    "M&M.NS", "COALINDIA.NS", "HINDALCO.NS", "GRASIM.NS", "INDUSINDBK.NS",
    "DRREDDY.NS", "CIPLA.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
    "BRITANNIA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "TATACONSUM.NS", "BPCL.NS",
    "SBILIFE.NS", "HDFCLIFE.NS", "TECHM.NS", "LTIM.NS", "SHRIRAMFIN.NS",
]

NIFTY_NEXT50 = [
    "ADANIGREEN.NS", "ADANIPOWER.NS", "AMBUJACEM.NS", "BANKBARODA.NS", "BERGEPAINT.NS",
    "BOSCHLTD.NS", "CHOLAFIN.NS", "COLPAL.NS", "DABUR.NS", "DLF.NS",
    "GAIL.NS", "GODREJCP.NS", "HAVELLS.NS", "ICICIGI.NS", "ICICIPRULI.NS",
    "IOC.NS", "IRCTC.NS", "JINDALSTEL.NS", "MARICO.NS", "MCDOWELL-N.NS",
    "MOTHERSON.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "PIDILITIND.NS", "PNB.NS",
    "SAIL.NS", "SIEMENS.NS", "SRF.NS", "TORNTPHARM.NS", "TRENT.NS",
    "TVSMOTOR.NS", "UNITDSPR.NS", "VBL.NS", "VEDL.NS", "ZOMATO.NS",
    "ZYDUSLIFE.NS", "AUROPHARMA.NS", "BANDHANBNK.NS", "BIOCON.NS", "CANBK.NS",
    "GMRINFRA.NS", "INDIGO.NS", "LICI.NS", "PAGEIND.NS", "PEL.NS",
    "PFC.NS", "RECLTD.NS", "TATAPOWER.NS", "UPL.NS", "YESBANK.NS",
]

NIFTY100 = NIFTY50 + NIFTY_NEXT50

# Liquid NSE ETFs — these trade intraday with OHLC + volume, so the breakout
# scan applies to them just like stocks.
ETFS = [
    "NIFTYBEES.NS", "BANKBEES.NS", "JUNIORBEES.NS", "GOLDBEES.NS", "SILVERBEES.NS",
    "ITBEES.NS", "CPSEETF.NS", "PSUBNKBEES.NS", "PVTBANKADD.NS", "ICICIB22.NS",
    "SETFNIF50.NS", "MON100.NS", "MAFANG.NS", "HDFCNIFTY.NS", "KOTAKNIFTY.NS",
    "AUTOBEES.NS", "PHARMABEES.NS", "CONSUMBEES.NS", "INFRABEES.NS", "MOM100.NS",
]


def _read_csv_symbols(path):
    """Read a 'Symbol' column from an NSE-style CSV and append .NS."""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        # NSE constituent CSVs use a 'Symbol' column.
        col = next((c for c in (reader.fieldnames or []) if c.strip().lower() == "symbol"), None)
        if col is None:
            return out
        for row in reader:
            sym = (row.get(col) or "").strip()
            if sym:
                out.append(sym if sym.endswith((".NS", ".BO")) else sym + ".NS")
    return out


def equity_universe(name="nifty500"):
    """Return the equity ticker list, preferring the downloaded CSV."""
    if name == "nifty50":
        return NIFTY50
    if name == "nifty100":
        return NIFTY100
    csv_syms = _read_csv_symbols(os.path.join(DATA_DIR, "nifty500.csv"))
    return csv_syms if csv_syms else NIFTY100  # graceful fallback


def etf_universe():
    csv_syms = _read_csv_symbols(os.path.join(DATA_DIR, "etfs.csv"))
    return csv_syms if csv_syms else ETFS


def stock_and_etf_universe(equity="nifty500"):
    """Combined, de-duplicated stock + ETF list for the 30-min scan."""
    seen, combined = set(), []
    for t in equity_universe(equity) + etf_universe():
        if t not in seen:
            seen.add(t)
            combined.append(t)
    return combined
