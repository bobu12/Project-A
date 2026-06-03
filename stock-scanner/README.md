# 📈 NSE/BSE Stock Scanner

Two tools that share one data/indicator engine:

1. **Mobile web app** (`app.py`) — a phone-friendly page to run on-demand scans
   (RSI / SMA / volume / fundamentals) from your browser.
2. **Automated EMA-breakout scanner** (`run_scan.py` + `scheduler.py`) — runs
   **every 30 minutes during market hours**, finds **EMA-confluence breakouts**,
   and **emails** you the matches. A separate **daily mutual-fund check** runs
   once after close.

---

## 🤖 Automated EMA-breakout scanner (the 30-min automation)

### The setup it looks for

On the **daily** chart, a stock/ETF matches when **all** of these hold:

- Price is **near or under the 200 EMA** (under it, or within ±6% above).
- The **20, 50, 100 EMAs are clustered within ±6% of price** (a compressed base).
- **Breakout trigger:** the latest close **breaks the prior 20-day high** on
  **≥1.5× average volume**.

Tunable via flags / `ScanConfig` in `scanner_core.py` (`--confluence-pct`,
`--confluence-only` to drop the breakout trigger, `--equity` to change universe).

### Universe

- **Stocks + ETFs** for the 30-min scan: Nifty 500 (run `fetch_universe.py` to
  download the official list) **+ liquid NSE ETFs**. Falls back to a built-in
  Nifty 100 list if the CSV isn't downloaded.
- **Mutual funds** (`--mf`, daily only): MFs have **one NAV per day and no
  volume**, so the intraday breakout can't apply. The MF check approximates the
  setup on the **daily NAV series** (NAV near/under its 200-DMA with 20/50/100-DMA
  confluence) via the `mftool` library. Configure scheme codes in
  `data/mf_schemes.csv` or the `MF_SCHEMES` env var.

### Data provider

The scanner reads market data through a pluggable provider (`providers.py`):

- **`groww`** — **live, accurate NSE/BSE data** via the official
  [Groww API](https://groww.in/trade-api/docs/python-sdk). Recommended. Daily
  candles include today's forming bar, so every 30-min scan re-evaluates against
  a live price.
- **`yfinance`** — free fallback (delayed, occasionally flaky for NSE).

Selection is via `DATA_PROVIDER` (`groww`/`yfinance`); if blank it auto-picks
Groww when `GROWW_*` credentials are set, else yfinance. Override per run with
`--provider`.

**Groww credentials** (from Groww → Trade API → *Generate API Key*) go in `.env`
as environment variables only — **never paste them into code, commits, or chat**:

```
GROWW_ACCESS_TOKEN=...           # preferred, OR
GROWW_API_KEY=...                # key + secret (SDK generates the token)
GROWW_API_SECRET=...
GROWW_REQUEST_DELAY=0.25         # raise if you hit rate limits
```

### Setup

```bash
cd stock-scanner
pip install -r requirements.txt
python fetch_universe.py            # download Nifty 500 + ETF lists (optional)

cp .env.example .env                # then edit .env: Groww keys + SMTP details
set -a; source .env; set +a         # load provider + email + MF config into env
```

Email uses SMTP from environment variables only (nothing secret is committed).
For Gmail, create an **App Password** (Account → Security → App passwords) and use
that as `SMTP_PASS`.

### Run the automation — pick one

**A) Built-in scheduler** (simplest; keep it running on a laptop / always-on box / VM):

```bash
python scheduler.py
```

Runs the breakout scan every 30 min, Mon–Fri 09:15–15:30 IST, and the
mutual-fund check daily ~21:00 IST.

**B) cron** (no long-running process; times are IST — set the host TZ or adjust):

```cron
# Breakout scan every 30 min during market hours, Mon-Fri
*/30 9-15 * * 1-5  cd /path/to/stock-scanner && set -a && . ./.env && set +a && python run_scan.py >> results/cron.log 2>&1
# Daily mutual-fund check at 21:00
0 21 * * 1-5       cd /path/to/stock-scanner && set -a && . ./.env && set +a && python run_scan.py --mf --confluence-only >> results/cron.log 2>&1
```

### One-off / manual run

```bash
python run_scan.py                  # 30-min stock + ETF scan, emails results
python run_scan.py --mf             # also run the daily mutual-fund check
python run_scan.py --confluence-only --equity nifty100   # looser, smaller universe
```

Each run also writes a timestamped CSV to `results/`.

---

## 📱 Mobile web app (on-demand scanner)

A phone-friendly stock scanner for **NSE-listed Indian stocks**. It screens a
universe (Nifty 50 / Nifty 100) on **technical**, **price/volume**, and
**fundamental** criteria and shows matches as tappable cards. Open it in your
phone's browser — no app install needed.

## What it screens

Two buttons:

- **Scan (RSI / volume / fundamentals):** RSI(14), SMA20 vs SMA50 trend, volume
  spike, 52-week proximity, plus P/E, market cap and price/volume filters.
- **EMA breakout scan (near 200 EMA):** the same EMA-confluence + breakout setup
  as the automation (price near/under 200 EMA, 20/50/100 EMAs within ±6%, close
  breaking the recent high on volume), run live via the configured data provider.

## Host it on your laptop

```bash
cd stock-scanner
pip install -r requirements.txt
cp .env.example .env          # optional: add Groww keys for live data on the EMA scan
./host.sh                     # or: python app.py
```

`host.sh` loads `.env` and prints both URLs:

- **On the laptop:** <http://localhost:5000>
- **On your phone (same Wi-Fi):** `http://<your-laptop-LAN-IP>:5000` —
  `host.sh` prints the exact address. On the phone, use **Share → Add to Home
  Screen** for an app-like icon.

> Keep the laptop awake / plugged in while you want the app reachable. The RSI
> scan works with no setup (yfinance); the **EMA breakout** button uses Groww if
> you've added keys to `.env`, otherwise yfinance.

**Want it reachable from anywhere (not just home Wi-Fi)?** Either run a tunnel
(`cloudflared tunnel --url http://localhost:5000` or `ngrok http 5000`) for a
temporary public URL, or deploy to [Render](https://render.com) /
[Railway](https://railway.app) (start command `python app.py`).

## Data source & note on this repo's sandbox

The automated scanner uses the **Groww API** for live NSE/BSE data (see *Data
provider* above), falling back to **Yahoo Finance via
[`yfinance`](https://github.com/ranaroussi/yfinance)** when Groww isn't
configured. The web app's **EMA breakout** button uses the same provider layer
(Groww if configured); its RSI scan uses yfinance. Tickers use the `.NS`
suffix for NSE and `.BO` for BSE (e.g. `RELIANCE.NS`).

> The Claude Code web sandbox blocks outbound finance hosts (Groww, Yahoo, NSE),
> so live scans only work when you run this on your own machine or a normal cloud
> host. The server, API, UI, the indicator/breakout engine, the Groww candle
> parsing, and provider selection were all verified offline; only the external
> network fetch is blocked inside the sandbox.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Flask backend: `/` (UI), `/api/scan`, `/api/scan-ema`, `/api/health` |
| `host.sh` | One-command laptop hosting (loads `.env`, prints phone URL) |
| `static/index.html` | Mobile-first single-page UI (RSI scan + EMA breakout scan) |
| `universe.py` | Ticker lists + CSV loader (edit to add your own) |
| `requirements.txt` | Python dependencies |

## Customising

- **Watchlist:** edit `universe.py` — add any NSE ticker with `.NS` (or `.BO` for
  BSE) and it's included in the dropdown universes.
- **Signals/thresholds:** the scoring lives in `analyse()` in `app.py`; filters
  in `passes()`.

> Educational tool, not investment advice. Verify data before acting on it.
