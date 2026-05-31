"""
Central configuration for the scalping bot.

Risk model (the important change): position size is no longer a fixed lot.
Each trade is sized so that hitting the initial stop loses at most
`risk_per_trade` of current equity (the user's "5% max SL"). Stops then move to
breakeven and trail once the trade is in profit. See backtester.py.

The cost numbers are *modeled estimates* of Exness-style spreads/commission,
NOT a live feed. Real fills differ and are usually worse.
"""

ACCOUNT = {
    "start_balance": 500.0,
    "leverage": 2000,
    "risk_per_trade": 0.05,   # <= 5% of equity risked to the initial stop (user request)
                              # NOTE: 1-2% is far safer; 5% is aggressive.
}

# Per-symbol contract, broker limits, and cost model.
SYMBOLS = {
    "XAUUSD": {
        "contract_size": 100.0,   # 100 oz per lot
        "min_lot": 0.01,
        "lot_step": 0.01,
        "spread": 0.25,
        "commission": 7.0,        # round-turn USD per 1.0 lot
        "slippage": 0.10,
        "timeframe": "H1",
        "close_only": False,      # real OHLC
        "data_file": "data/XAUUSD_h1.csv",
    },
    "BTCUSD": {
        "contract_size": 1.0,     # 1 BTC per lot
        "min_lot": 0.01,
        "lot_step": 0.01,
        "spread": 12.0,
        "commission": 7.0,
        "slippage": 5.0,
        "timeframe": "D1",
        "close_only": True,       # daily CLOSE only -> low fidelity
        "data_file": "data/BTCUSD_d1.csv",
    },
}

# Strategy + risk-management parameter GRID for the walk-forward re-optimizer.
#   sl_atr        : initial stop distance in ATRs (defines "R", the risk unit)
#   tp_atr        : take-profit distance in ATRs
#   be_trigger_R  : at this many R of profit, move stop to breakeven
#   trail_R       : once past breakeven, trail the stop this many R behind the
#                   best price reached (locks in profit as it runs)
PARAM_GRID = {
    "lookback":     [20, 40],
    "atr_period":   [14],
    "entry_z":      [1.5, 2.0, 2.5],
    "sl_atr":       [1.0, 1.5],      # tighter than before -> smaller R, more affordable size
    "tp_atr":       [3.0, 4.0],      # let winners run; trailing stop protects
    "be_trigger_R": [1.0],
    "trail_R":      [1.0, 1.5],
    "max_hold":     [48],
}

WALK_FORWARD = {
    "XAUUSD": {"train": 24 * 30, "test": 24 * 20},   # ~30d train / ~20d test (H1: 24 bars/day)
    "BTCUSD": {"train": 120,     "test": 60},        # ~120d / ~60d (D1)
}
