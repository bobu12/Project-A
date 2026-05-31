# Scalping Bot (XAUUSD / BTCUSD) — MT5 + Exness

A small, **honest** systematic-trading project: a z-score mean-reversion
strategy with ATR-based stops, a walk-forward re-optimizer (the real version of
"backtest daily and improve its own accuracy"), a cost-aware backtester, an
Excel reporter, and a live MT5/Exness execution module for a Windows VPS.

> **Read this first.** This is a learning/engineering tool, **not** financial
> advice and **not** a money-making system. No strategy here is claimed to have
> an edge. The backtest exists to find out — honestly — whether one survives
> realistic costs. Usually it does not. The included run **blew up the gold
> account** (see results). High win rate ≠ profit. Past results ≠ future.

## Results from the included real-data run

| Symbol | Data | Period | Trades | Win % | Net P/L | Final ($500 start) | Max DD | Ruined? |
|--------|------|--------|-------:|------:|--------:|-------------------:|-------:|:-------:|
| XAUUSD | real M15 OHLC | 2020-06 → 2022-03 | 32 | 25.0% | **−$547.91** | **−$47.91** | 106.9% | **YES** |
| BTCUSD | real daily close | 2024-05 → 2026-05 | 43 | 55.8% | +$3,570 | $4,070 | 74.6% | no |

The gold account was wiped out. The BTC line "profited" but (a) ran a **74.6%
drawdown** that would feel like ruin, and (b) is built on **daily-close-only**
data, which is too coarse to trust for a scalping decision. Neither result is a
reason to trade real money — they're a reason to forward-test on demo.

## Data provenance (all REAL, all with caveats)

- **XAUUSD** — `ejtraderLabs/historical-data` (GitHub), M15 OHLC. Series ends
  **2022-03**, so "last year" is the most recent real year reachable from this
  sandbox. Prices were stored ×100 and rescaled to USD/oz on import.
- **BTCUSD** — CoinMetrics community data (GitHub), **daily close only** (no
  OHLC, no intraday). SL/TP can therefore only trigger when a *daily close*
  crosses the level — low fidelity, flagged everywhere.
- Live APIs (Yahoo / Binance / Stooq) are geo-blocked in the sandbox, so
  calendar-recent intraday data could not be fetched here. On your VPS, the
  live module pulls real data straight from MT5.

## Layout

```
src/config.py      account, per-symbol costs/lots, param grid, walk-forward windows
src/data.py        load CSVs -> clean OHLC frame
src/strategy.py    z-score + ATR indicators and the entry signal
src/backtester.py  no-look-ahead backtest + walk-forward re-optimizer
src/report.py      metrics + Excel writer (Time/Buy-Sell/Entry/SL/Exit + summary)
src/mt5_live.py    LIVE execution on Windows VPS (DEMO_ONLY=True by default)
scripts/run_backtest.py   runs everything -> reports/backtest_report.xlsx
```

## Run the backtest

```bash
pip install -r requirements.txt
python -m scripts.run_backtest      # writes reports/backtest_report.xlsx
```

Tune costs, lots, the parameter grid, and walk-forward windows in
`src/config.py`.

## Going live (only after demo validation)

1. Windows machine or VPS with the **MT5 terminal** logged into Exness.
2. `pip install MetaTrader5`.
3. Put credentials in `secrets.env` (gitignored). Keep `DEMO_ONLY = True` in
   `src/mt5_live.py`.
4. Forward-test on **demo for weeks**. Compare demo fills to the backtest. If
   they disagree, the cost model is wrong — fix it before risking a cent.
5. Prefer **risk-based sizing** (`lots_for_risk`, ~0.5–1% per trade) over the
   fixed lots used in the backtest; fixed 0.10/0.06 lots on $500 is what blew
   the gold account.

## License / disclaimer

For education and engineering only. Trading derivatives with leverage can lose
more than your deposit. You are responsible for your own decisions.
