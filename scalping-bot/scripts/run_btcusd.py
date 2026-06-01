#!/usr/bin/env python3
"""Bitcoin (BTCUSD) bot entry point.

WARNING: EXPERIMENTAL / UNVALIDATED. The BTC backtest had only a tiny sample
(15-21 trades) on daily data - that is NOT enough to establish an edge. This
bot exists so you can DEMO-test the idea, not because it is proven. Do not risk
real money on it.

  python -m scripts.run_btcusd            # offline dry run (safe, anywhere)
  python -m scripts.run_btcusd --live      # DEMO trading on a Windows VPS
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.live_runner import main

if __name__ == "__main__":
    main("BTCUSD")
