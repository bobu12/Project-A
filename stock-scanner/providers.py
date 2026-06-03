"""
Data-provider layer. The scanner is provider-agnostic: a "fetcher" is any
callable that takes a list of tickers and returns {ticker: OHLCV DataFrame}
(or None per ticker on failure), with columns Open/High/Low/Close/Volume indexed
by date.

Two providers:
  * groww    — live, accurate NSE/BSE data via the official Groww API.
  * yfinance — free fallback (delayed) if Groww isn't configured.

Selection: DATA_PROVIDER env var ("groww"/"yfinance"); if unset, Groww is used
when GROWW_* credentials are present, otherwise yfinance.

Groww credentials come ONLY from environment variables — nothing is committed:
  GROWW_ACCESS_TOKEN              (preferred; or)
  GROWW_API_KEY + GROWW_API_SECRET
  GROWW_REQUEST_DELAY            (optional, seconds between calls; default 0.25)
"""

import datetime as dt
import os
import time

import pandas as pd

COLS = ["Open", "High", "Low", "Close", "Volume"]


# --------------------------------------------------------------------------- #
# yfinance
# --------------------------------------------------------------------------- #
def yfinance_frames(tickers, period="2y"):
    import scanner_core as sc  # reuse the bulk download helpers
    data = sc.fetch_prices(tickers, period=period)
    return {t: sc.ticker_frame(data, t) for t in tickers}


# --------------------------------------------------------------------------- #
# Groww
# --------------------------------------------------------------------------- #
class GrowwProvider:
    def __init__(self):
        from growwapi import GrowwAPI

        self.api = GrowwAPI(self._resolve_token(GrowwAPI))
        self.delay = float(os.environ.get("GROWW_REQUEST_DELAY", "0.25"))
        # Constants are SDK attributes; fall back to plain strings if names differ.
        self.EX_NSE = getattr(self.api, "EXCHANGE_NSE", "NSE")
        self.EX_BSE = getattr(self.api, "EXCHANGE_BSE", "BSE")
        self.SEG_CASH = getattr(self.api, "SEGMENT_CASH", "CASH")

    @staticmethod
    def _resolve_token(GrowwAPI):
        """Resolve a Groww access token from env vars. Three supported flows:

          1) GROWW_ACCESS_TOKEN  — paste a token (resets daily at 6 AM IST).
          2) GROWW_API_KEY + GROWW_TOTP_SECRET  — TOTP flow (RECOMMENDED for the
             unattended automation: regenerates the token automatically through
             the daily reset). GROWW_API_KEY is the "TOTP token" shown in Groww;
             GROWW_TOTP_SECRET is the base32 secret behind the QR code.
          3) GROWW_API_KEY + GROWW_API_SECRET  — static key+secret flow.
        """
        token = os.environ.get("GROWW_ACCESS_TOKEN")
        if token:
            return token

        api_key = os.environ.get("GROWW_API_KEY")
        totp_secret = os.environ.get("GROWW_TOTP_SECRET")
        if api_key and totp_secret:
            import pyotp
            otp = pyotp.TOTP(totp_secret).now()
            try:
                return GrowwAPI.get_access_token(api_key=api_key, totp=otp)
            except TypeError:  # SDK variant that names the OTP arg differently
                return GrowwAPI.get_access_token(api_key=api_key, secret=otp)

        secret = os.environ.get("GROWW_API_SECRET")
        if api_key and secret:
            return GrowwAPI.get_access_token(api_key=api_key, secret=secret)

        raise RuntimeError(
            "Groww not configured. Set one of: GROWW_ACCESS_TOKEN; or "
            "GROWW_API_KEY + GROWW_TOTP_SECRET (TOTP); or "
            "GROWW_API_KEY + GROWW_API_SECRET."
        )

    def _exchange_symbol(self, ticker):
        if ticker.endswith(".BO"):
            return self.EX_BSE, ticker[:-3]
        return self.EX_NSE, ticker.replace(".NS", "")

    def history(self, ticker, calendar_days=800):
        """Daily candles. ~800 calendar days ≈ 550 trading days (enough for 200 EMA).
        The latest (today's) candle reflects intraday movement, so each 30-min
        scan re-evaluates against a live close."""
        exchange, symbol = self._exchange_symbol(ticker)
        end = dt.datetime.now()
        start = end - dt.timedelta(days=calendar_days)
        resp = self.api.get_historical_candle_data(
            trading_symbol=symbol,
            exchange=exchange,
            segment=self.SEG_CASH,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            interval_in_minutes=1440,  # daily
        )
        candles = (resp or {}).get("candles") or []
        if not candles:
            return None
        df = pd.DataFrame(
            [c[:6] for c in candles],
            columns=["ts", "Open", "High", "Low", "Close", "Volume"],
        )
        df["dt"] = pd.to_datetime(df["ts"], unit="s")
        return df.set_index("dt")[COLS].astype(float).sort_index()

    def frames(self, tickers):
        out = {}
        for t in tickers:
            try:
                out[t] = self.history(t)
            except Exception as e:  # one bad symbol shouldn't kill the scan
                out[t] = None
                print(f"[groww] {t}: {e}")
            time.sleep(self.delay)
        return out


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def get_fetcher(name=None):
    """Return (fetch_callable, provider_name)."""
    name = (name or os.environ.get("DATA_PROVIDER") or "").lower()
    if not name:
        name = "groww" if (
            os.environ.get("GROWW_ACCESS_TOKEN") or os.environ.get("GROWW_API_KEY")
        ) else "yfinance"

    if name == "groww":
        provider = GrowwProvider()
        return provider.frames, "groww"
    return (lambda tickers: yfinance_frames(tickers)), "yfinance"
