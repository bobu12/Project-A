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

# Best-effort LAN IP for phone access.
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -z "$IP" ] && IP="$(ipconfig getifaddr en0 2>/dev/null || true)"  # macOS

echo "================================================================"
echo " Stock scanner web app"
echo "   This laptop : http://localhost:5000"
[ -n "$IP" ] && echo "   Your phone  : http://$IP:5000   (same Wi-Fi network)"
echo "   Stop        : Ctrl-C"
echo "================================================================"

exec python app.py
