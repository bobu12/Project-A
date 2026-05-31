"""
Central configuration for the scalping bot.

Everything you would normally tweak lives here. Values reflect the user's
stated account: $500 starting capital, 1:2000 leverage, 0.1 lot XAUUSD,
0.06 lot BTCUSD.

IMPORTANT: the cost numbers below are *modeled estimates* of Exness-style
spreads/commission. They are NOT pulled from a live feed. Real fills will
differ. Treat every result as indicative, not predictive.
"""

ACCOUNT = {
    "start_balance": 500.0,   # USD
    "leverage": 2000,         # 1:2000
    # Exness-style stop-out: positions force-closed when margin level is very
    # low. We approximate ruin as equity <= 0 (the backtest stops there).
}

# Per-symbol contract + cost model.
#   contract_size : units of the underlying per 1.0 lot
#   lots          : fixed position size requested by the user
#   spread        : modeled bid/ask spread in PRICE terms (USD)
#   commission    : modeled round-turn commission in USD per 1.0 lot
#   slippage      : modeled adverse slippage per side in PRICE terms (USD)
SYMBOLS = {
    "XAUUSD": {
        "contract_size": 100.0,   # 100 oz per lot -> 0.1 lot = 10 oz
        "lots": 0.10,
        "spread": 0.25,           # ~25 cents, typical gold spread
        "commission": 7.0,        # ~$3.5/side raw-spread account
        "slippage": 0.10,
        "timeframe": "M15",
        "close_only": False,      # we have real OHLC
        "data_file": "data/XAUUSD_m15.csv",
    },
    "BTCUSD": {
        "contract_size": 1.0,     # 1 BTC per lot -> 0.06 lot = 0.06 BTC
        "lots": 0.06,
        "spread": 12.0,
        "commission": 7.0,
        "slippage": 5.0,
        "timeframe": "D1",
        "close_only": True,       # CoinMetrics gives daily CLOSE only -> low fidelity
        "data_file": "data/BTCUSD_d1.csv",
    },
}

# Strategy parameter GRID searched by the daily/walk-forward re-optimizer.
# Kept deliberately small + logical (avoids the curve-fit trap).
PARAM_GRID = {
    "lookback":   [20, 40, 60],     # bars for the z-score mean/std
    "atr_period": [14],
    "entry_z":    [1.5, 2.0, 2.5],  # how stretched before we fade
    "sl_atr":     [1.5, 2.0],       # stop distance in ATRs
    "tp_atr":     [2.0, 3.0],       # target distance in ATRs (>= sl for >=1:1)
    "max_hold":   [48],             # bars before a time-stop exit
}

# Walk-forward windows (in bars). Re-optimize on `train`, trade `test`, roll on.
WALK_FORWARD = {
    "XAUUSD": {"train": 96 * 30, "test": 96 * 20},   # ~30d train / ~20d test (M15: 96 bars/day)
    "BTCUSD": {"train": 120,     "test": 60},        # ~120d train / ~60d test (D1)
}
