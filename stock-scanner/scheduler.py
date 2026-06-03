"""
Standalone scheduler — runs the breakout scan every 30 minutes during NSE/BSE
market hours, and the mutual-fund check once daily after close.

Run it and leave it running:
    python scheduler.py

Market hours: Mon-Fri, 09:15-15:30 IST. The mutual-fund check runs once per day
around 21:00 IST (after AMFI publishes NAVs).

For an alternative that doesn't need a long-running process, use cron instead
(see README). This loop is handy on a laptop / always-on box / cloud VM.
"""

import datetime as dt
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = dt.time(9, 15)
MARKET_CLOSE = dt.time(15, 30)
MF_HOUR = 21  # 9 PM IST daily mutual-fund check
SCAN_INTERVAL = 30 * 60  # seconds


def is_market_hours(now):
    if now.weekday() >= 5:  # Sat/Sun
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def run(*extra):
    cmd = [sys.executable, "run_scan.py", *extra]
    print(f"[{dt.datetime.now(IST):%Y-%m-%d %H:%M}] running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=sys.path[0] or ".")


def seconds_to_next_half_hour(now):
    minute = now.minute
    add = (30 - minute % 30) % 30 or 30
    nxt = (now + dt.timedelta(minutes=add)).replace(second=0, microsecond=0)
    return max(1, (nxt - now).total_seconds())


def main():
    print("Scheduler started. Breakout scan every 30 min during market hours; "
          "MF check daily ~21:00 IST. Ctrl-C to stop.")
    last_mf_date = None
    while True:
        now = dt.datetime.now(IST)

        if is_market_hours(now):
            run()  # 30-min stock + ETF breakout scan
        else:
            print(f"[{now:%H:%M}] market closed — skipping breakout scan")

        # Daily mutual-fund check, once per calendar day.
        if now.hour >= MF_HOUR and last_mf_date != now.date():
            run("--mf", "--confluence-only")  # MF: confluence on daily NAV, no intraday breakout
            last_mf_date = now.date()

        time.sleep(seconds_to_next_half_hour(dt.datetime.now(IST)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
