#!/usr/bin/env python3
"""Gold (XAUUSD) bot entry point.

This is the VALIDATED variant: breakout on H1 with a thin but genuine
out-of-sample edge (profit factor ~1.06). Not a money printer.

  python -m scripts.run_xauusd            # offline dry run (safe, anywhere)
  python -m scripts.run_xauusd --live      # DEMO trading on a Windows VPS
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.live_runner import main

if __name__ == "__main__":
    main("XAUUSD")
