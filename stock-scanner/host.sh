#!/usr/bin/env bash
# Host the scanner web app from this laptop.
#   chmod +x host.sh && ./host.sh
# Open it on this laptop at http://localhost:5000 — and on your phone (same
# Wi-Fi) at the http://<LAN-IP>:5000 address printed below.
set -e
cd "$(dirname "$0")"

# Load credentials/config from .env if present (Groww keys, SMTP, etc.)
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

# Port: macOS reserves 5000 for AirPlay Receiver, so default to 8000 there.
if [ -z "$PORT" ]; then
  if [ "$(uname)" = "Darwin" ]; then PORT=8000; else PORT=5000; fi
fi
export PORT

# Best-effort LAN IP for phone access.
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -z "$IP" ] && IP="$(ipconfig getifaddr en0 2>/dev/null || true)"  # macOS

echo "================================================================"
echo " Stock scanner web app"
echo "   This laptop : http://localhost:$PORT"
[ -n "$IP" ] && echo "   Your phone  : http://$IP:$PORT   (same Wi-Fi network)"
echo "   Stop        : Ctrl-C"
echo "================================================================"

exec python app.py
