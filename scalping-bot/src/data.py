"""Data loading. Reads the prepared real-history CSVs into clean DataFrames.

For live trading on a VPS you would replace `load_symbol` with a function that
calls MetaTrader5.copy_rates_* (see src/mt5_live.py). The backtester is
data-source agnostic: it just needs columns Date, open, high, low, close.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def load_symbol(cfg: dict) -> pd.DataFrame:
    """Load one symbol's history from its CSV.

    For close-only sources (BTC daily) we synthesise degenerate OHLC
    (open=high=low=close). This is flagged honestly: with only closes we
    cannot know intrabar highs/lows, so SL/TP can only trigger when a *close*
    crosses the level. That is lower fidelity and is documented in the report.
    """
    df = pd.read_csv(ROOT / cfg["data_file"])
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    if cfg["close_only"]:
        df["open"] = df["high"] = df["low"] = df["close"]
    return df[["Date", "open", "high", "low", "close"]]
