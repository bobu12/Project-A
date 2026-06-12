# Project-A — GCC Markets Dashboard

A lightweight, dependency-free web app that lists stocks across the major
**GCC (Gulf Cooperation Council) stock exchanges** and shows, per stock:

> Name · Code · CMP · Volume · Market Cap · Opening · Closing · Daily Open/Close ·
> Weekly Open/Close · Session High · Session Low · Day Volume

### Exchanges covered

| Country | Exchange | Currency |
|---|---|---|
| 🇸🇦 Saudi Arabia | Saudi Exchange (Tadawul) | SAR |
| 🇦🇪 UAE — Dubai | Dubai Financial Market (DFM) | AED |
| 🇦🇪 UAE — Abu Dhabi | Abu Dhabi Securities Exchange (ADX) | AED |
| 🇶🇦 Qatar | Qatar Stock Exchange (QSE) | QAR |
| 🇰🇼 Kuwait | Boursa Kuwait | KWD |
| 🇴🇲 Oman | Muscat Stock Exchange (MSX) | OMR |
| 🇧🇭 Bahrain | Bahrain Bourse | BHD |

## Run it

No build step, no npm. Either:

```bash
# open directly
open index.html            # macOS  (use 'xdg-open' on Linux)

# …or serve locally (recommended so live providers can fetch)
python3 -m http.server 8000
# then visit http://localhost:8000
```

Tab between exchanges, search by name/code, and click any column header to sort.

## Data sources — phased & modular

The app runs on **sample data** out of the box so it works offline with no
account. Open **⚙ Data source** to switch providers — the choice and any API key
are saved in your browser's `localStorage` (never committed to the repo).

Providers are kept as **separate modules** under `js/providers/`, each
self-registering with a shared framework, so adding/swapping a feed is a
self-contained file change:

```
js/providers/base.js        Framework: contract, registry, fallback, helpers
js/providers/mock.js        Phase 1 · sample data (default, offline)
js/providers/yahoo.js       Phase 1 · Yahoo Finance (free, no key)
js/providers/twelvedata.js  Phase 2 · Twelve Data live feed (API key)
js/providers/eodhd.js       Phase 2 · EODHD alternative (API key)
```

- **Phase 1** — free defaults (sample data + Yahoo Finance), no account needed.
- **Phase 2** — live paid feed via **Twelve Data** (Grow plan for GCC equities),
  with EODHD as a cheaper-coverage alternative. Select it under ⚙ Data source
  and paste your key; nothing is stored server-side or in git.

| Provider | Cost | GCC coverage | Notes |
|---|---|---|---|
| **Sample data** (default) | Free | All 7 (real ticker codes) | Offline, no key. |
| **Yahoo Finance** | Free | Saudi/Qatar/Kuwait solid; UAE/Oman/Bahrain partial | No key. Unofficial; may be blocked by browser CORS. |
| **EODHD** | ~$20/mo | Widest, incl. Tadawul | Cheapest official broad coverage; confirm exchange suffixes in your account. |
| **Twelve Data** (Grow) | $29/mo | Saudi (XSAU), Abu Dhabi (XADS), Qatar | Best real-time DX; GCC equities require the Grow plan or higher. |
| ICE / Refinitiv / Bloomberg | Enterprise | All 7, pro-grade | Overkill for this use case. |

**Recommendation:** use free **Sample/Yahoo** for development; if you need a paid
live feed, **EODHD (~$20/mo)** is the cheapest with the widest coverage, while
**Twelve Data Grow ($29/mo)** gives the best real-time developer experience for
Saudi/Abu Dhabi/Qatar.

> Figures shown by default are **illustrative**. Live providers may need minor
> per-account symbol-format tweaks (documented inline in `js/providers.js`).
> This project is not investment advice.

## Project layout

```
index.html        Dashboard shell (tabs, table, settings dialog)
css/styles.css    Dark, responsive styling
js/data.js        Sample dataset: real tickers + currency metadata per exchange
js/providers.js   Pluggable data layer: mock | yahoo | twelvedata | eodhd
js/app.js         Rendering, exchange switching, search, sortable columns
```

---

This dashboard is the application front end; the repository also contains the
original **AWS architecture** work (CloudFormation templates, RDS design, and
Lambda thumbnail/automation scripts) it was built alongside.
