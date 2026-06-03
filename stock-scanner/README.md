# 📈 NSE Stock Scanner (mobile web app)

A phone-friendly stock scanner for **NSE-listed Indian stocks**. It screens a
universe (Nifty 50 / Nifty 100) on **technical**, **price/volume**, and
**fundamental** criteria and shows matches as tappable cards. Open it in your
phone's browser — no app install needed.

## What it screens

- **Technical:** RSI(14), SMA20 vs SMA50 trend (bullish/bearish), volume spike
  (today vs 20-day average), 52-week high/low proximity.
- **Price/volume:** price range, % change today, volume × average.
- **Fundamentals:** P/E, market cap, sector (fetched for the top matches; max P/E
  filter supported).

Default behaviour with no filters: scans the universe and lists the biggest
movers with all their signals. Tap **Filters** to narrow it down.

## Run it

```bash
cd stock-scanner
pip install -r requirements.txt
python app.py
```

The server listens on `0.0.0.0:5000`.

### Open from your phone

- **Same Wi-Fi as the machine running it:** find the machine's LAN IP
  (`ipconfig` / `ip addr`) and visit `http://<that-ip>:5000` on your phone.
- **From anywhere:** deploy to a small host so you get a public URL —
  [Render](https://render.com), [Railway](https://railway.app), or
  [PythonAnywhere](https://www.pythonanywhere.com) all run this as-is
  (start command: `python app.py`, or `gunicorn app:app` for production).
  Then bookmark the URL / "Add to Home Screen" on your phone for an app-like icon.

## Data source & note on this repo's sandbox

Market data comes from **Yahoo Finance via [`yfinance`](https://github.com/ranaroussi/yfinance)**
(free, no API key). NSE tickers use the `.NS` suffix (e.g. `RELIANCE.NS`).

> The Claude Code web sandbox blocks outbound finance hosts, so live scans only
> work when you run this on your own machine or a normal cloud host. The server,
> API, UI, and indicator logic were all verified; only the external fetch is
> blocked inside the sandbox.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Flask backend: `/` (UI), `/api/scan`, `/api/universes`, `/api/health` |
| `universe.py` | Nifty 50 / Nifty 100 ticker lists (edit to add your own) |
| `static/index.html` | Mobile-first single-page UI |
| `requirements.txt` | Python dependencies |

## Customising

- **Watchlist:** edit `universe.py` — add any NSE ticker with `.NS` (or `.BO` for
  BSE) and it's included in the dropdown universes.
- **Signals/thresholds:** the scoring lives in `analyse()` in `app.py`; filters
  in `passes()`.

> Educational tool, not investment advice. Verify data before acting on it.
